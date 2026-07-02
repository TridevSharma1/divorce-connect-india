from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Dict, Any

from ..database import get_db
from ..models import User, ProfileEditRequest
from ..security import get_current_user

router = APIRouter()

class ProfileEditRequestSchema(BaseModel):
    requested_data: Dict[str, Any]

@router.post("/edit-request")
async def submit_edit_request(req: ProfileEditRequestSchema, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role not in ["lawyer", "adminpanel"]:
        raise HTTPException(status_code=403, detail="Only lawyers and admin panel users can submit edit requests")
    
    # Check if there's already a pending request
    res = await db.execute(select(ProfileEditRequest).where(ProfileEditRequest.user_id == user.id, ProfileEditRequest.status == "PENDING"))
    existing = res.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending edit request")
    
    edit_req = ProfileEditRequest(user_id=user.id, requested_data=req.requested_data)
    db.add(edit_req)
    await db.commit()
    return {"message": "Edit request submitted for approval"}

class ApproveEditSchema(BaseModel):
    request_id: int
    action: str # "APPROVE" or "REJECT"

@router.post("/approve-edit")
async def approve_edit_request(req: ApproveEditSchema, admin: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if admin.role not in ["adminpanel", "superadmin", "staff"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    res = await db.execute(select(ProfileEditRequest).where(ProfileEditRequest.id == req.request_id))
    edit_req = res.scalars().first()
    if not edit_req:
        raise HTTPException(status_code=404, detail="Edit request not found")
        
    if req.action == "APPROVE":
        edit_req.status = "APPROVED"
        # In a real scenario, we would apply `edit_req.requested_data` to the respective profile model (LawyerProfile / AdminPanelProfile)
        # We will keep old data active until here, and now it gets overwritten.
        
        # Example logic for lawyer profile:
        from ..models import LawyerProfile, AdminPanelProfile
        user_res = await db.execute(select(User).where(User.id == edit_req.user_id))
        target_user = user_res.scalars().first()
        if target_user:
            if target_user.role == "lawyer":
                prof_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == target_user.id))
                prof = prof_res.scalars().first()
                if prof:
                    for k, v in edit_req.requested_data.items():
                        if hasattr(prof, k):
                            setattr(prof, k, v)
            elif target_user.role == "adminpanel":
                prof_res = await db.execute(select(AdminPanelProfile).where(AdminPanelProfile.user_id == target_user.id))
                prof = prof_res.scalars().first()
                if prof:
                    for k, v in edit_req.requested_data.items():
                        if hasattr(prof, k):
                            setattr(prof, k, v)
    elif req.action == "REJECT":
        edit_req.status = "REJECTED"
        
    await db.commit()
    return {"message": f"Edit request {req.action.lower()}d"}
