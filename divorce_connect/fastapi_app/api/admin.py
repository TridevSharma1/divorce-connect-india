from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Dict, Any

from ..database import get_db
from ..models import User, AdminPanelProfile, LawyerProfile, CaseRequest, CaseDocument
from ..security import get_current_user

router = APIRouter()

@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    
    if not current_user.is_staff:
        raise HTTPException(status_code=403, detail="Not authorized to access admin dashboard")

    admin_profile_res = await db.execute(select(AdminPanelProfile).where(AdminPanelProfile.user_id == current_user.id))
    admin_profile = admin_profile_res.scalar_one_or_none()
    
    # Simple default if missing
    is_complete = getattr(admin_profile, 'is_profile_complete', False) if admin_profile else False
    is_verified = getattr(admin_profile, 'is_verified_by_superuser', False) if admin_profile else False
    full_name = getattr(admin_profile, 'full_name', f"{current_user.first_name} {current_user.last_name}") if admin_profile else f"{current_user.first_name} {current_user.last_name}"
    gender = getattr(admin_profile, 'gender', 'Not specified') if admin_profile else 'Not specified'
    dob = admin_profile.date_of_birth.strftime("%d %b %Y") if admin_profile and admin_profile.date_of_birth else 'Not specified'
    profile_picture = getattr(admin_profile, 'profile_picture', None) if admin_profile else None
    
    # Global stats
    pending_lawyers_count_res = await db.execute(select(func.count()).select_from(LawyerProfile).where(LawyerProfile.verified == False))
    pending_lawyers_count = pending_lawyers_count_res.scalar()
    active_cases_count_res = await db.execute(select(func.count()).select_from(CaseRequest).where(CaseRequest.status == 'ACTIVE'))
    active_cases_count = active_cases_count_res.scalar()
    pending_case_requests_res = await db.execute(select(func.count()).select_from(CaseRequest).where(CaseRequest.status == 'PENDING'))
    pending_case_requests = pending_case_requests_res.scalar()
    # Assume 1 document verification for simplicity right now
    pending_docs = 0

    return {
        "is_complete": is_complete,
        "is_verified": is_verified,
        "profile": {
            "full_name": full_name,
            "email": current_user.email,
            "gender_display": gender,
            "date_of_birth": dob,
            "profile_picture": profile_picture
        },
        "stats": {
            "pending_count": pending_lawyers_count,
            "active_cases_count": active_cases_count,
            "pending_case_requests_count": pending_case_requests,
            "pending_documents_count": pending_docs,
            "flagged_accounts_count": 0,
            "pending_reports_count": 0
        },
        "pending_lawyer_requests": [],
        "pending_documents": [],
        "pending_reports": []
    }
