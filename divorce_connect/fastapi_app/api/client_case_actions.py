from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from ..database import get_db
from ..models import User, ClientProfile, CaseRequest, CaseDocument, LawyerProfile, CaseDocumentVerification
from ..security import get_current_user
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()

# ----- Client Endpoints -----

@router.get("/cases")
async def list_client_cases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Ensure user is a client and profile exists
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=403, detail="Only clients can view case requests")
    
    res = await db.execute(
        select(CaseRequest, LawyerProfile)
        .join(LawyerProfile, CaseRequest.lawyer_id == LawyerProfile.id)
        .where(CaseRequest.client_id == client.id)
    )
    cases = res.all()
    
    return [
        {
            "id": c.id,
            "lawyer_id": c.lawyer_id,
            "lawyer_name": l.full_name,
            "message": c.message,
            "status": c.status,
            "workflow_stage": c.workflow_stage,
            "documents_submitted_at": c.documents_submitted_at,
            "documents_verified_at": c.documents_verified_at,
            "created_at": c.created_at.strftime("%b %d, %Y") if c.created_at else "",
        }
        for c, l in cases
    ]

@router.get("/cases/{case_id}")
async def get_case_detail(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    is_admin = current_user.role == "admin" or current_user.is_staff
    
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer = lawyer_res.scalar_one_or_none()
    
    if not client and not lawyer and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view case details")
        
    query = select(CaseRequest).where(CaseRequest.id == case_id)
    if not is_admin:
        if client:
            query = query.where(CaseRequest.client_id == client.id)
        elif lawyer:
            query = query.where(CaseRequest.lawyer_id == lawyer.id)
        
    case_res = await db.execute(query)
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case request not found")
        
    # Fetch lawyer details
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == case.lawyer_id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    
    # Fetch client details
    client_profile_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
    client_profile = client_profile_res.scalar_one_or_none()

    lawyer_email = ""
    if lawyer_profile:
        lawyer_user_res = await db.execute(select(User).where(User.id == lawyer_profile.user_id))
        lawyer_user = lawyer_user_res.scalar_one_or_none()
        if lawyer_user:
            lawyer_email = lawyer_user.email

    client_email = ""
    if client_profile:
        client_user_res = await db.execute(select(User).where(User.id == client_profile.user_id))
        client_user = client_user_res.scalar_one_or_none()
        if client_user:
            client_email = client_user.email

    # Fetch attached documents
    docs_res = await db.execute(select(CaseDocument).where(CaseDocument.case_request_id == case.id))
    docs = docs_res.scalars().all()
    return {
        "id": case.id,
        "lawyer_id": case.lawyer_id,
        "message": case.message,
        "status": case.status,
        "workflow_stage": case.workflow_stage,
        "is_lawyer": lawyer is not None,
        "created_at": case.created_at,
        "lawyer_details": {
            "full_name": lawyer_profile.full_name if lawyer_profile else "Unassigned",
            "specialization": lawyer_profile.specialization if lawyer_profile else "",
            "office_city": lawyer_profile.office_city if lawyer_profile else "",
            "consultation_fee": float(lawyer_profile.consultation_fee) if lawyer_profile and lawyer_profile.consultation_fee else 0.0,
            "years_of_experience": lawyer_profile.years_of_experience if lawyer_profile else 0,
            "rating": lawyer_profile.rating if lawyer_profile else 0.0,
            "profile_picture": lawyer_profile.profile_picture if lawyer_profile else "",
            "email": lawyer_email,
            "mobile_number": lawyer_profile.mobile_number if lawyer_profile else "",
        } if lawyer_profile else None,
        "client_details": {
            "first_name": client_profile.first_name if client_profile else "Client",
            "last_name": client_profile.last_name if client_profile else "",
            "mobile_number": client_profile.mobile_number if client_profile else "",
            "email": client_email,
        } if client_profile else None,
        "documents": [
            {
                "id": d.id,
                "document_type": d.document_type,
                "document_file": d.document_file,
                "uploaded_at": d.uploaded_at,
                "verification_status": (await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == d.id))).scalar_one_or_none().status if (await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == d.id))).scalar_one_or_none() else "PENDING",
                "rejection_reason": (await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == d.id))).scalar_one_or_none().rejection_reason if (await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == d.id))).scalar_one_or_none() else None
            }
            for d in docs
        ],
    }

@router.post("/cases/{case_id}/documents")
async def upload_case_document(
    case_id: int,
    document_type: str = Query(...),  # document type from query parameter
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify ownership
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client profile not found")
    case_res = await db.execute(
        select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.client_id == client.id)
    )
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case request not found")
    # Save file to static/uploads (ensure directory exists)
    import os, shutil, uuid
    upload_dir = os.path.join(os.getcwd(), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # Update or Create DB record
    existing_doc_res = await db.execute(
        select(CaseDocument).where(
            CaseDocument.case_request_id == case.id,
            CaseDocument.document_type == document_type
        )
    )
    existing_doc = existing_doc_res.scalar_one_or_none()
    
    if existing_doc:
        existing_doc.document_file = filename
        # Reset verification status
        ver_res = await db.execute(
            select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == existing_doc.id)
        )
        ver = ver_res.scalar_one_or_none()
        if ver:
            ver.status = "PENDING"
            ver.rejection_reason = None
            ver.verified_at = None
            ver.verified_by_id = None
        else:
            new_ver = CaseDocumentVerification(
                document_id=existing_doc.id,
                status="PENDING"
            )
            db.add(new_ver)
        ret_doc = existing_doc
    else:
        new_doc = CaseDocument(
            case_request_id=case.id,
            document_type=document_type,
            document_file=filename,
        )
        db.add(new_doc)
        await db.flush()
        
        new_ver = CaseDocumentVerification(
            document_id=new_doc.id,
            status="PENDING"
        )
        db.add(new_ver)
        ret_doc = new_doc

    # Update case request timestamp and status
    import datetime
    case.documents_submitted_at = datetime.datetime.utcnow().replace(tzinfo=None)
    # If case was rejected previously, reset to PENDING / DOCUMENTS_SUBMITTED so admin reviews it again
    if case.status in ["REJECTED", "DOCUMENTS_PENDING"]:
        case.status = "DOCUMENTS_SUBMITTED"
        
    await db.commit()
    return {"message": "Document uploaded", "document_id": ret_doc.id}

# ----- Admin Endpoints -----

@router.get("/admin/documents/pending")
async def list_pending_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify admin role
    if not (current_user.is_staff or current_user.role == "admin"):
        raise HTTPException(status_code=403, detail="Only admins can view pending documents")
    res = await db.execute(
        select(CaseDocument, CaseRequest).where(
            CaseDocument.case_request_id == CaseRequest.id,
            CaseRequest.documents_verified_at == None  # noqa: E711
        )
    )
    rows = res.all()
    pending = []
    for doc, case in rows:
        pending.append({
            "document_id": doc.id,
            "case_id": case.id,
            "lawyer_id": case.lawyer_id,
            "client_id": case.client_id,
            "document_type": doc.document_type,
            "document_file": doc.document_file,
            "uploaded_at": doc.uploaded_at,
        })
    return pending

class VerifyDocumentRequest(BaseModel):
    action: str
    rejection_reason: Optional[str] = None

@router.post("/admin/documents/{doc_id}/verify")
async def verify_document(
    doc_id: int,
    req_body: VerifyDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not (current_user.is_staff or current_user.role == "admin"):
        raise HTTPException(status_code=403, detail="Only admins can verify documents")
    doc_res = await db.execute(select(CaseDocument).where(CaseDocument.id == doc_id))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Update parent case request verification timestamp if all docs for that case are approved
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == doc.case_request_id))
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Parent case request not found")
        
    ver_res = await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == doc_id))
    ver = ver_res.scalar_one_or_none()
    if not ver:
        ver = CaseDocumentVerification(document_id=doc_id)
        db.add(ver)
        
    import datetime
    if req_body.action == "approve":
        ver.status = "VERIFIED"
        ver.rejection_reason = None
        ver.verified_at = datetime.datetime.utcnow()
        ver.verified_by_id = current_user.id
        
        # Check if all case documents are approved
        all_docs_res = await db.execute(select(CaseDocument).where(CaseDocument.case_request_id == case.id))
        all_docs = all_docs_res.scalars().all()
        
        all_approved = True
        for d in all_docs:
            if d.id == doc_id:
                continue
            d_ver_res = await db.execute(select(CaseDocumentVerification).where(CaseDocumentVerification.document_id == d.id))
            d_ver = d_ver_res.scalar_one_or_none()
            if not d_ver or d_ver.status != "VERIFIED":
                all_approved = False
                break
                
        if all_approved:
            case.documents_verified_at = datetime.datetime.utcnow()
            case.workflow_stage = "documents_verified"
    else:
        ver.status = "REJECTED"
        ver.rejection_reason = req_body.rejection_reason
        ver.verified_at = datetime.datetime.utcnow()
        ver.verified_by_id = current_user.id
        case.workflow_stage = "documents_rejected"
        
    await db.commit()
    return {"message": f"Document {req_body.action}d", "case_id": case.id}

from fastapi import Form, UploadFile, File
from ..models import CaseMessage

@router.get("/cases/{case_id}/messages")
async def get_case_messages(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify ownership
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer = lawyer_res.scalar_one_or_none()
    
    if not client and not lawyer:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    query = select(CaseRequest).where(CaseRequest.id == case_id)
    if client:
        query = query.where(CaseRequest.client_id == client.id)
    elif lawyer:
        query = query.where(CaseRequest.lawyer_id == lawyer.id)
        
    case_res = await db.execute(query)
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    messages_res = await db.execute(
        select(CaseMessage).where(CaseMessage.case_id == case.id).order_by(CaseMessage.created_at.asc())
    )
    messages = messages_res.scalars().all()
    
    return [
        {
            "id": m.id,
            "sender_type": m.sender_type,
            "sender_user_id": m.sender_user_id,
            "text": m.text,
            "attachment": m.attachment,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in messages
    ]

@router.post("/cases/{case_id}/messages")
async def send_case_message(
    case_id: int,
    text: str = Form(""),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify ownership
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer = lawyer_res.scalar_one_or_none()
    
    if not client and not lawyer:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    query = select(CaseRequest).where(CaseRequest.id == case_id)
    if client:
        query = query.where(CaseRequest.client_id == client.id)
    elif lawyer:
        query = query.where(CaseRequest.lawyer_id == lawyer.id)
        
    case_res = await db.execute(query)
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Handle file attachment
    filename = None
    if file and file.filename:
        import os, shutil, uuid
        upload_dir = os.path.join(os.getcwd(), "media", "chat_attachments")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Save exact relative path for media compatibility
        filename = f"chat_attachments/{filename}"

    new_msg = CaseMessage(
        case_id=case.id,
        sender_type="CLIENT" if client else "LAWYER",
        sender_user_id=current_user.id,
        text=text,
        attachment=filename,
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)
    
    # Broadcast message to WebSocket
    try:
        from ..notifications import manager
        recipient_id = None
        if client:
            lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == case.lawyer_id))
            lawyer_p = lawyer_profile_res.scalar_one_or_none()
            if lawyer_p:
                recipient_id = lawyer_p.user_id
        elif lawyer:
            client_profile_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
            client_p = client_profile_res.scalar_one_or_none()
            if client_p:
                recipient_id = client_p.user_id
                
        if recipient_id:
            await manager.send_personal_message(
                f"Chat: New message on Case #{case.id}",
                user_id=recipient_id
            )
    except Exception as e:
        print("Failed to send WebSocket message:", e)
        
    return {
        "id": new_msg.id,
        "sender_type": new_msg.sender_type,
        "sender_user_id": new_msg.sender_user_id,
        "text": new_msg.text,
        "attachment": new_msg.attachment,
        "created_at": new_msg.created_at.isoformat() if new_msg.created_at else "",
    }

class UpdateStageRequest(BaseModel):
    stage: str

@router.post("/cases/{case_id}/stage")
async def update_case_stage(
    case_id: int,
    req_body: UpdateStageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer = lawyer_res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=403, detail="Only the assigned lawyer can change status")
        
    case_res = await db.execute(
        select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.lawyer_id == lawyer.id)
    )
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found or not assigned to you")
        
    valid_stages = [
        "CASE_CREATED",
        "DOCUMENT_VERIFICATION",
        "LAWYER_ASSIGNED",
        "PETITION_DRAFTED",
        "PETITION_FILED",
        "FIRST_MOTION",
        "SECOND_MOTION",
        "DECREE_ISSUED",
        "COMPLETED",
    ]
    
    if req_body.stage not in valid_stages:
        raise HTTPException(status_code=400, detail="Invalid workflow stage")
        
    case.workflow_stage = req_body.stage
    import datetime
    case.workflow_stage_updated_at = datetime.datetime.utcnow()
    
    if req_body.stage == "COMPLETED":
        case.status = "COMPLETED"
    else:
        case.status = "ACCEPTED"
        
    await db.commit()
    
    # Notify client
    try:
        from ..notifications import create_and_broadcast_notification
        client_profile_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
        client_profile = client_profile_res.scalar_one_or_none()
        if client_profile:
            stage_display = req_body.stage.replace("_", " ").title()
            await create_and_broadcast_notification(
                db=db,
                user_id=client_profile.user_id,
                title="Case Progress",
                message=f"Your case status has been updated to: {stage_display}",
                url=f"/client_case_detail/?case_id={case.id}"
            )
    except Exception as e:
        print("Failed to notify client:", e)
        
    return {"status": "success", "workflow_stage": case.workflow_stage}
