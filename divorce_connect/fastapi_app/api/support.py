from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from ..database import get_db
from ..models import User, UserReport, BugReport, ContactRequest
from ..security import get_current_user

router = APIRouter()

class UserReportSchema(BaseModel):
    reported_user_id: int
    reason: str
    proof_file_url: Optional[str] = None

@router.post("/report-user")
async def report_user(req: UserReportSchema, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role not in ["client", "lawyer"]:
        raise HTTPException(status_code=403, detail="Only clients and lawyers can report each other")
        
    report = UserReport(
        reporter_id=user.id,
        reported_user_id=req.reported_user_id,
        reason=req.reason,
        proof_file_url=req.proof_file_url
    )
    db.add(report)
    await db.commit()
    return {"message": "Report submitted successfully"}

class BugReportSchema(BaseModel):
    issue_text: str

@router.post("/report-bug")
async def report_bug(req: BugReportSchema, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "adminpanel":
        raise HTTPException(status_code=403, detail="Only admin panel users can report bugs to superusers")
        
    bug = BugReport(reporter_id=user.id, issue_text=req.issue_text)
    db.add(bug)
    await db.commit()
    
    # In a real scenario, trigger a Taskiq background task to send email to superusers
    
    return {"message": "Bug reported successfully"}

class ContactFormSchema(BaseModel):
    name: str
    email: EmailStr
    message: str

@router.post("/contact")
async def submit_contact(req: ContactFormSchema, db: AsyncSession = Depends(get_db)):
    contact = ContactRequest(name=req.name, email=req.email, message=req.message)
    db.add(contact)
    await db.commit()
    return {"message": "Contact request submitted"}
