from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from ..database import get_db
from ..models import User, LawyerProfile, AdminPanelProfile
from ..security import get_current_user

router = APIRouter()

async def check_verified_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not (current_user.is_staff or current_user.role == "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    admin_profile_res = await db.execute(
        select(AdminPanelProfile).where(AdminPanelProfile.user_id == current_user.id)
    )
    admin_profile = admin_profile_res.scalar_one_or_none()
    if not admin_profile or not admin_profile.is_verified_by_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account not verified by superuser"
        )
    return current_user

@router.get("/lawyers/pending")
async def list_pending_lawyers(
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(LawyerProfile)
        .where(LawyerProfile.verified == False, LawyerProfile.is_profile_complete == True)
    )
    lawyers = res.scalars().all()
    
    return [
        {
            "id": lawyer.id,
            "full_name": lawyer.full_name,
            "specialization": lawyer.specialization,
            "bar_registration_number": lawyer.bar_registration_number,
            "years_of_experience": lawyer.years_of_experience,
            "office_city": lawyer.office_city
        }
        for lawyer in lawyers
    ]

@router.post("/lawyers/{lawyer_id}/verify")
async def verify_lawyer(
    lawyer_id: int,
    action: str, # "approve" or "reject"
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")
        
    if action == "approve":
        lawyer.verified = True
        try:
            from ..notifications import create_and_broadcast_notification
            await create_and_broadcast_notification(
                db=db,
                user_id=lawyer.user_id,
                title="Account Approved",
                message="Congratulations! Your lawyer profile has been verified and approved by admin.",
                url="/lawyer_dashboard/"
            )
        except Exception:
            pass
    elif action == "reject":
        lawyer.verified = False
        try:
            from ..notifications import create_and_broadcast_notification
            await create_and_broadcast_notification(
                db=db,
                user_id=lawyer.user_id,
                title="Account Rejected",
                message="Your profile verification was rejected. Please edit your details and re-submit.",
                url="/lawyer_profile_edit/"
            )
        except Exception:
            pass
        
    await db.commit()
    return {"message": f"Lawyer status updated to {action}"}

from ..models import CaseRequest, ClientProfile, LawyerProfile, User
from sqlalchemy.orm import aliased
@router.get("/cases")
async def list_cases_for_admin(
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    ClientUser = aliased(User)
    LawyerUser = aliased(User)
    
    res = await db.execute(
        select(CaseRequest, ClientProfile, LawyerProfile, ClientUser, LawyerUser)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .join(ClientUser, ClientProfile.user_id == ClientUser.id)
        .join(LawyerProfile, CaseRequest.lawyer_id == LawyerProfile.id)
        .join(LawyerUser, LawyerProfile.user_id == LawyerUser.id)
        .order_by(CaseRequest.updated_at.desc())
    )
    rows = res.all()
    
    import datetime
    local_tz_offset = datetime.timedelta(hours=5, minutes=30)
    cases = []
    for case, client, lawyer, cu, lu in rows:
        local_updated_at = case.updated_at + local_tz_offset if case.updated_at else None
        cases.append({
            "id": case.id,
            "status": case.status,
            "updated_at": local_updated_at.strftime("%d %b, %Y · %H:%M") if local_updated_at else "",
            "client_name": client.first_name + " " + client.last_name,
            "client_id": client.id,
            "client_email": cu.email,
            "lawyer_name": lawyer.full_name,
            "lawyer_id": lawyer.id,
            "lawyer_email": lu.email
        })
    return cases

from ..models import CaseDocumentVerification, CaseDocument
from sqlalchemy import func
@router.get("/documents/verification-list")
async def get_document_verification_list(
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    # 1. Calculate total pending documents
    pending_count_res = await db.execute(
        select(func.count(CaseDocumentVerification.id))
        .where(CaseDocumentVerification.status == 'PENDING')
    )
    total_pending = pending_count_res.scalar() or 0

    # 2. Query all CaseRequests with their client, lawyer
    res = await db.execute(
        select(CaseRequest, ClientProfile, LawyerProfile)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .join(LawyerProfile, CaseRequest.lawyer_id == LawyerProfile.id)
        .order_by(CaseRequest.documents_submitted_at.desc())
    )
    rows = res.all()

    cases_with_pending_docs = []
    
    doc_types = {
        'aadhaar': 'Aadhaar Card',
        'pan': 'PAN Card',
        'marriage_cert': 'Marriage Certificate',
        'address_proof': 'Address Proof',
        'income_proof': 'Income Proof',
        'passport': 'Passport',
        'affidavit': 'Affidavits',
    }

    for case, client, lawyer in rows:
        docs_res = await db.execute(
            select(CaseDocument)
            .where(CaseDocument.case_request_id == case.id)
        )
        docs = docs_res.scalars().all()
        
        if not docs:
            continue
            
        case_docs = []
        def normalize_document_file_url(file_path: str) -> str:
            if not file_path:
                return "#"
            if file_path.startswith("http://") or file_path.startswith("https://") or file_path.startswith("//"):
                return file_path
            if file_path.startswith("/"):
                return file_path
            if file_path.startswith("media/") or file_path.startswith("static/"):
                return f"/{file_path}"
            return f"/static/uploads/{file_path}"

        for doc in docs:
            ver_res = await db.execute(
                select(CaseDocumentVerification)
                .where(CaseDocumentVerification.document_id == doc.id)
            )
            ver = ver_res.scalar_one_or_none()
            
            if not ver:
                ver = CaseDocumentVerification(
                    document_id=doc.id,
                    status='PENDING'
                )
                db.add(ver)
                await db.commit()
                await db.refresh(ver)
            
            import datetime
            local_tz_offset = datetime.timedelta(hours=5, minutes=30)
            local_uploaded_at = doc.uploaded_at + local_tz_offset if doc.uploaded_at else None
            pdf_url = normalize_document_file_url(doc.document_file)
            case_docs.append({
                "id": doc.id,
                "document_type": doc.document_type,
                "document_type_display": doc_types.get(doc.document_type, doc.document_type.capitalize()),
                "uploaded_at": local_uploaded_at.strftime("%b %d, %Y · %H:%M") if local_uploaded_at else "",
                "document_file_url": pdf_url if doc.document_file else "#",
                "verification": {
                    "status": ver.status,
                    "rejection_reason": ver.rejection_reason or ""
                }
            })
        
        local_submitted_at = case.documents_submitted_at + local_tz_offset if case.documents_submitted_at else None
        local_created_at = case.created_at + local_tz_offset if case.created_at else None
        cases_with_pending_docs.append({
            "case_request": {
                "id": case.id,
                "client": {
                    "get_full_name": f"{client.first_name} {client.last_name}"
                },
                "lawyer": {
                    "full_name": lawyer.full_name
                },
                "documents_submitted_at": local_submitted_at.strftime("%b %d, %Y · %H:%M") if local_submitted_at else (local_created_at.strftime("%b %d, %Y · %H:%M") if local_created_at else "")
            },
            "documents": case_docs
        })

    return {
        "total_pending": total_pending,
        "cases_with_pending_docs": cases_with_pending_docs
    }


