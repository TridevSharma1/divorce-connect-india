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
    # Ensure user is a client
    if not hasattr(current_user, "client_profile"):
        raise HTTPException(status_code=403, detail="Only clients can view case requests")
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client profile not found")
    
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
    # Fetch attached documents
    docs_res = await db.execute(select(CaseDocument).where(CaseDocument.case_request_id == case.id))
    docs = docs_res.scalars().all()
    return {
        "id": case.id,
        "lawyer_id": case.lawyer_id,
        "message": case.message,
        "status": case.status,
        "workflow_stage": case.workflow_stage,
        "documents": [
            {
                "id": d.id,
                "document_type": d.document_type,
                "document_file": d.document_file,
                "uploaded_at": d.uploaded_at,
            }
            for d in docs
        ],
        "created_at": case.created_at,
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
    # Create DB record
    new_doc = CaseDocument(
        case_request_id=case.id,
        document_type=document_type,
        document_file=filename,
    )
    db.add(new_doc)
    # Update case request timestamp
    case.documents_submitted_at = case.documents_submitted_at or case.created_at
    await db.commit()
    await db.refresh(new_doc)
    return {"message": "Document uploaded", "document_id": new_doc.id}

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
