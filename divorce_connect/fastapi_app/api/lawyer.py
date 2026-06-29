from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from typing import Dict, Any

from ..database import get_db
from ..models import User, LawyerProfile, CaseRequest, CaseDocument, ClientProfile
from ..security import get_current_user

router = APIRouter()

@router.get("/dashboard")
async def get_lawyer_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    
    if not lawyer_profile:
        return {
            "is_complete": False,
            "is_verified": False,
            "has_pending_update": False,
            "profile": {
                "full_name": current_user.first_name + " " + current_user.last_name,
                "get_specialization_display": "Specialization not set",
                "office_city": "City not set",
                "rating_summary": "0.0 (0 reviews)",
                "consultation_fee": 0.0,
                "profile_picture": None
            },
            "stats": {
                "total_cases": 0,
                "active_cases": 0,
                "pending_requests": 0,
                "verified_documents": 0,
                "monthly_revenue": 0,
                "yearly_revenue": 0,
                "active_clients": 0,
                "completed_cases": 0
            },
            "pending_requests": [],
            "ready_cases": []
        }

    total_cases_res = await db.execute(select(func.count()).select_from(CaseRequest).where(CaseRequest.lawyer_id == lawyer_profile.id))
    total_cases = total_cases_res.scalar()
    active_cases_res = await db.execute(select(func.count()).select_from(CaseRequest).where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'ACTIVE'))
    active_cases = active_cases_res.scalar()
    completed_cases_res = await db.execute(select(func.count()).select_from(CaseRequest).where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'COMPLETED'))
    completed_cases = completed_cases_res.scalar()
    pending_requests_res = await db.execute(select(CaseRequest).where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'PENDING'))
    pending_requests = pending_requests_res.scalars().all()
    
    fee = lawyer_profile.consultation_fee or 0.0
    monthly_revenue = active_cases * float(fee)
    yearly_revenue = (active_cases + completed_cases) * float(fee)

    pending_data = []
    for req in pending_requests:
        client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == req.client_id))
        client = client_res.scalar_one_or_none()
        client_name = f"{client.first_name} {client.last_name}" if client else f"Client #{req.client_id}"
        pending_data.append({
            "id": req.id,
            "client_name": client_name,
            "created_at": req.created_at.strftime("%d %b %Y") if req.created_at else "",
            "message": req.message
        })

    return {
        "is_complete": lawyer_profile.is_profile_complete,
        "is_verified": lawyer_profile.verified,
        "has_pending_update": False,
        "profile": {
            "full_name": lawyer_profile.full_name,
            "get_specialization_display": lawyer_profile.specialization,
            "office_city": lawyer_profile.office_city,
            "rating_summary": f"{lawyer_profile.rating} ({lawyer_profile.rating_count} reviews)",
            "consultation_fee": float(fee),
            "profile_picture": lawyer_profile.profile_picture
        },
        "stats": {
            "total_cases": total_cases,
            "active_cases": active_cases,
            "pending_requests": len(pending_requests),
            "verified_documents": 0,
            "monthly_revenue": monthly_revenue,
            "yearly_revenue": yearly_revenue,
            "active_clients": active_cases,
            "completed_cases": completed_cases
        },
        "pending_requests": pending_data,
        "ready_cases": []
    }
