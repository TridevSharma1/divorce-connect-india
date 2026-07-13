from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from ..database import get_db
from ..models import User, LawyerProfile, AdminPanelProfile, WithdrawRequest
from ..security import get_current_user

router = APIRouter()

async def check_verified_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.is_superuser:
        return current_user

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
            "office_city": lawyer.office_city,
            "bar_council_license": lawyer.bar_council_license,
            "gender": lawyer.gender,
            "bio": lawyer.bio,
            "consultation_fee": lawyer.consultation_fee,
            "mobile_number": lawyer.mobile_number,
            "profile_picture": lawyer.profile_picture,
            "state_bar_council": lawyer.state_bar_council,
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
            "custom_case_id": case.custom_id or f"CS-{case.id:05d}",
            "status": case.status,
            "updated_at": local_updated_at.strftime("%d %b, %Y · %H:%M") if local_updated_at else "",
            "client_name": client.first_name + " " + client.last_name,
            "client_id": client.id,
            "client_custom_id": client.custom_id or f"CLI-{client.id:05d}",
            "client_email": cu.email,
            "lawyer_name": lawyer.full_name,
            "lawyer_id": lawyer.id,
            "lawyer_custom_id": lawyer.custom_id or f"LW-{lawyer.id:05d}",
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


from sqlalchemy.orm import joinedload
from pydantic import BaseModel

class WithdrawAction(BaseModel):
    action: str  # 'approve' or 'reject'
    admin_notes: Optional[str] = None

@router.get("/withdrawals")
async def get_all_withdrawals(
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(WithdrawRequest)
        .options(joinedload(WithdrawRequest.lawyer).joinedload(LawyerProfile.user))
        .order_by(WithdrawRequest.created_at.desc())
    )
    reqs = res.scalars().all()
    out = []
    for r in reqs:
        out.append({
            "id": r.id,
            "lawyer_id": r.lawyer_id,
            "lawyer_name": r.lawyer.full_name if r.lawyer else "Unknown",
            "lawyer_email": r.lawyer.user.email if r.lawyer and r.lawyer.user else "Unknown",
            "amount": float(r.amount),
            "method": r.method,
            "method_details": r.method_details,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "admin_notes": r.admin_notes
        })
    return out

@router.post("/withdrawals/{withdraw_id}/action")
async def process_withdrawal_action(
    withdraw_id: int,
    action_data: WithdrawAction,
    current_user: User = Depends(check_verified_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(WithdrawRequest).where(WithdrawRequest.id == withdraw_id))
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    if req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Withdrawal request has already been processed")

    if action_data.action == "approve":
        req.status = "APPROVED"
    elif action_data.action == "reject":
        req.status = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    req.admin_notes = action_data.admin_notes
    await db.commit()
    return {"message": f"Withdrawal request status updated to {req.status}"}


