from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from ..database import get_db
from ..models import User, ClientProfile, LawyerProfile, CaseRequest, CaseDocument, CaseDocumentVerification
from ..security import get_current_user

router = APIRouter()

REQUIRED_DOC_TYPES = [
    "Aadhaar", "PAN", "Marriage Certificate", "Address Proof", 
    "Income Proof", "Passport", "Affidavits", "Court Notices"
]

@router.post("/hire")
async def hire_lawyer(lawyer_id: int = Form(...), message: str = Form(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can hire lawyers")
    
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user.id))
    client = client_res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client profile not found")
        
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = lawyer_res.scalars().first()
    if not lawyer or not lawyer.verified:
        raise HTTPException(status_code=400, detail="Invalid or unverified lawyer")
        
    case = CaseRequest(
        client_id=client.id,
        lawyer_id=lawyer.id,
        message=message,
        status="PENDING",
        workflow_stage="Case Created"
    )
    db.add(case)
    await db.commit()
    return {"message": "Lawyer hire request sent", "case_id": case.id}

@router.post("/{case_id}/respond")
async def lawyer_respond_case(case_id: int, action: str = Form(...), response_msg: str = Form(""), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "lawyer":
        raise HTTPException(status_code=403, detail="Only lawyers can respond to case requests")
        
    lp_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
    lp = lp_res.scalars().first()
    
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.lawyer_id == lp.id))
    case = case_res.scalars().first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    if action == "ACCEPT":
        case.status = "ACCEPTED"
        case.workflow_stage = "Document Verification"
    elif action == "REJECT":
        case.status = "REJECTED"
        case.workflow_stage = "Completed"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    case.response_message = response_msg
    await db.commit()
    return {"message": f"Case {action.lower()}ed"}

import cloudinary.uploader
@router.post("/{case_id}/documents")
async def upload_document(case_id: int, document_type: str = Form(...), file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can upload case documents")
        
    if document_type not in REQUIRED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type")
        
    # Check if case belongs to user
    cp_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user.id))
    cp = cp_res.scalars().first()
    
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.client_id == cp.id))
    case = case_res.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Upload to Cloudinary
    result = cloudinary.uploader.upload(file.file, resource_type="auto")
    file_url = result.get("secure_url")
    
    doc = CaseDocument(case_request_id=case.id, document_type=document_type, document_file=file_url)
    db.add(doc)
    await db.commit()
    return {"message": "Document uploaded successfully", "url": file_url}

@router.post("/documents/{case_id}/verify")
async def verify_documents(case_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "adminpanel":
        raise HTTPException(status_code=403, detail="Only admin panel users can verify documents")
        
    # Check if all 8 docs are uploaded
    docs_res = await db.execute(select(CaseDocument).where(CaseDocument.case_request_id == case_id))
    docs = docs_res.scalars().all()
    uploaded_types = set(d.document_type for d in docs)
    
    missing = set(REQUIRED_DOC_TYPES) - uploaded_types
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required documents: {', '.join(missing)}")
        
    # Verify all
    for d in docs:
        ver = CaseDocumentVerification(document_id=d.id, status="VERIFIED", verified_by_id=user.id)
        db.add(ver)
        
    # Update case status
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == case_id))
    case = case_res.scalars().first()
    case.status = "LAWYER HIRED"
    case.workflow_stage = "Lawyer Assigned"
    import datetime
    case.documents_verified_at = datetime.datetime.utcnow()
    
    await db.commit()
    return {"message": "All documents verified. Case assigned to lawyer."}

@router.put("/{case_id}/stage")
async def update_workflow_stage(case_id: int, stage: str = Form(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "lawyer":
        raise HTTPException(status_code=403, detail="Only lawyers can update workflow stage")
        
    lp_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
    lp = lp_res.scalars().first()
    
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.lawyer_id == lp.id))
    case = case_res.scalars().first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    valid_stages = ["Case Created", "Document Verification", "Lawyer Assigned", "Petition Drafted", "Petition Filed", "First Motion", "Second Motion", "Decree Issued", "Completed"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail="Invalid stage")
        
    case.workflow_stage = stage
    import datetime
    case.workflow_stage_updated_at = datetime.datetime.utcnow()
    
    await db.commit()
    return {"message": "Workflow stage updated successfully"}
