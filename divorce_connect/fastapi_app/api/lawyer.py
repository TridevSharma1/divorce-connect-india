from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Dict, Any

from ..database import get_db
from ..models import User, LawyerProfile, CaseRequest, CaseDocument, ClientProfile
from ..security import get_current_user

router = APIRouter()

async def check_verified_lawyer(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(
        select(LawyerProfile).where(LawyerProfile.user_id == current_user.id)
    )
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()

    if lawyer_profile:
        if current_user.role != "lawyer":
            current_user.role = "lawyer"
            await db.commit()
    elif current_user.role == "lawyer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not lawyer_profile or not lawyer_profile.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lawyer account not verified by admin or superuser"
        )
    return current_user

@router.get("/dashboard")
async def get_lawyer_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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

@router.get("/case-requests")
async def list_case_requests(
    current_user: User = Depends(check_verified_admin if False else check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
        
    requests_res = await db.execute(
        select(CaseRequest)
        .where(CaseRequest.lawyer_id == lawyer_profile.id)
        .order_by(CaseRequest.created_at.desc())
    )
    requests = requests_res.scalars().all()
    
    data = []
    for req in requests:
        client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == req.client_id))
        client = client_res.scalar_one_or_none()
        client_name = f"{client.first_name} {client.last_name}" if client else f"Client #{req.client_id}"
        data.append({
            "id": req.id,
            "client_name": client_name,
            "message": req.message,
            "status": req.status,
            "workflow_stage": req.workflow_stage,
            "created_at": req.created_at.strftime("%d %b %Y") if req.created_at else ""
        })
    return data

@router.post("/case-requests/{request_id}/respond")
async def respond_case_request(
    request_id: int,
    action: str, # "accept" or "reject"
    response_message: str = "",
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
        
    req_res = await db.execute(
        select(CaseRequest).where(CaseRequest.id == request_id, CaseRequest.lawyer_id == lawyer_profile.id)
    )
    req = req_res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Case request not found")
        
    if action == "accept":
        req.status = "ACTIVE"
        req.workflow_stage = "document_upload"
    elif action == "reject":
        req.status = "REJECTED"
        
    req.response_message = response_message
    await db.commit()
    return {"message": f"Request status updated to {req.status}"}

@router.get("/earnings")
async def get_lawyer_earnings(
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
        
    consultation_fee = float(lawyer_profile.consultation_fee) if lawyer_profile.consultation_fee else 0.0
    
    # Completed count
    completed_res = await db.execute(
        select(func.count()).select_from(CaseRequest)
        .where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'COMPLETED')
    )
    completed_count = completed_res.scalar() or 0
    
    # Accepted count
    accepted_res = await db.execute(
        select(func.count()).select_from(CaseRequest)
        .where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'ACCEPTED')
    )
    accepted_count = accepted_res.scalar() or 0
    
    total_generated = consultation_fee * (completed_count + accepted_count)
    available_balance = consultation_fee * completed_count
    escrow_balance = consultation_fee * accepted_count
    
    import datetime
    now = datetime.datetime.utcnow()
    chart_bars = []
    max_amount = 0.0
    months_data = []
    
    for offset in range(5, -1, -1):
        target_date = now - datetime.timedelta(days=30 * offset)
        month_label = target_date.strftime("%b")
        month_cases = 0
        if offset == 0:
            month_cases = completed_count + accepted_count
        else:
            month_cases = 0
        month_amount = month_cases * consultation_fee
        months_data.append({
            "label": month_label,
            "amount": month_amount
        })
        if month_amount > max_amount:
            max_amount = month_amount
            
    for item in months_data:
        height_pct = int((item["amount"] / max_amount * 100)) if max_amount > 0 else 0
        if item["amount"] > 0 and height_pct < 10:
            height_pct = 10
        chart_bars.append({
            "label": item["label"],
            "amount": item["amount"],
            "height_pct": height_pct,
            "is_current": item["label"] == now.strftime("%b")
        })
        
    # Query recent transactions
    tx_res = await db.execute(
        select(CaseRequest, ClientProfile)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .where(CaseRequest.lawyer_id == lawyer_profile.id)
        .order_by(CaseRequest.updated_at.desc())
        .limit(10)
    )
    tx_list = tx_res.all()
    
    transactions = []
    for c, client_p in tx_list:
        transactions.append({
            "date": c.updated_at.strftime("%b %d, %Y") if c.updated_at else "",
            "client_name": client_p.first_name + " " + client_p.last_name,
            "consultation_type": "Lawyer Consultation",
            "amount": consultation_fee,
            "status_label": c.status.title(),
            "status_dot_class": "bg-green-500" if c.status in ["COMPLETED", "ACCEPTED"] else "bg-gray-400"
        })
        
    return {
        "totals": {
            "total_earnings": total_generated,
            "escrow_balance": escrow_balance,
            "available_balance": available_balance,
            "monthly_generated": chart_bars[-1]["amount"] if chart_bars else 0.0,
        },
        "chart_bars": chart_bars,
        "transactions": transactions,
        "transactions_total": len(transactions)
    }

@router.get("/cases")
async def get_lawyer_cases(
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
        
    res = await db.execute(
        select(CaseRequest, ClientProfile)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .where(CaseRequest.lawyer_id == lawyer_profile.id)
        .order_by(CaseRequest.updated_at.desc())
    )
    rows = res.all()
    
    ready_cases = []
    active_cases = []
    pending_verification = []
    rejected_cases = []
    
    for req, client_p in rows:
        case_data = {
            "id": req.id,
            "client_name": client_p.first_name + " " + client_p.last_name,
            "client_email": client_p.email,
            "created_at": req.created_at.strftime("%b %d, %Y") if req.created_at else "",
            "updated_at": req.updated_at.strftime("%b %d, %Y") if req.updated_at else "",
            "status": req.status,
            "workflow_stage": req.workflow_stage or "pending_review",
            "message": req.message
        }
        if req.status == "DOCUMENTS_VERIFIED":
            ready_cases.append(case_data)
        elif req.status in ["ACCEPTED", "ACTIVE"]:
            active_cases.append(case_data)
        elif req.status in ["PENDING", "DOCUMENTS_PENDING", "DOCUMENTS_SUBMITTED"]:
            pending_verification.append(case_data)
        elif req.status == "REJECTED":
            rejected_cases.append(case_data)
            
    return {
        "ready_cases": ready_cases,
        "active_cases": active_cases,
        "pending_verification": pending_verification,
        "rejected_cases": rejected_cases
    }

@router.get("/profile")
async def get_lawyer_profile_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        # Create an empty profile row to avoid breaking on onboarding
        lawyer_profile = LawyerProfile(
            user_id=current_user.id,
            full_name=current_user.first_name + " " + current_user.last_name,
            gender="",
            bar_registration_number=f"PENDING-{current_user.id}",
            state_bar_council="",
            years_of_experience=0,
            specialization="",
            mobile_number="",
            bio="",
            office_city=""
        )
        db.add(lawyer_profile)
        await db.commit()
        await db.refresh(lawyer_profile)
        
    return {
        "full_name": lawyer_profile.full_name,
        "gender": lawyer_profile.gender,
        "date_of_birth": lawyer_profile.date_of_birth.isoformat() if lawyer_profile.date_of_birth else "",
        "bar_registration_number": lawyer_profile.bar_registration_number,
        "state_bar_council": lawyer_profile.state_bar_council,
        "years_of_experience": lawyer_profile.years_of_experience,
        "specialization": lawyer_profile.specialization,
        "consultation_fee": float(lawyer_profile.consultation_fee) if lawyer_profile.consultation_fee else 0.0,
        "office_city": lawyer_profile.office_city,
        "bio": lawyer_profile.bio,
        "mobile_number": lawyer_profile.mobile_number,
        "alternate_mobile_number": lawyer_profile.alternate_mobile_number or "",
        "profile_picture": lawyer_profile.profile_picture or ""
    }

from fastapi import UploadFile, File, Form
from typing import Optional
@router.post("/profile")
async def update_lawyer_profile_endpoint(
    current_user: User = Depends(get_current_user),
    full_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str | None = Form(None),
    bar_registration_number: str = Form(...),
    state_bar_council: str = Form(...),
    years_of_experience: int = Form(...),
    specialization: str = Form(...),
    consultation_fee: float | None = Form(None),
    office_city: str = Form(...),
    bio: str = Form(...),
    mobile_number: str = Form(...),
    alternate_mobile_number: str | None = Form(None),
    profile_picture: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db)
):
    import datetime
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    profile = lawyer_profile_res.scalar_one_or_none()
    if not profile:
        profile = LawyerProfile(user_id=current_user.id)
        db.add(profile)
        
    profile.full_name = full_name
    profile.gender = gender
    if date_of_birth:
        try:
            profile.date_of_birth = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except:
            pass
    profile.bar_registration_number = bar_registration_number
    profile.state_bar_council = state_bar_council
    profile.years_of_experience = years_of_experience
    profile.specialization = specialization
    profile.consultation_fee = consultation_fee
    profile.office_city = office_city
    profile.bio = bio
    profile.mobile_number = mobile_number
    profile.alternate_mobile_number = alternate_mobile_number
    profile.is_profile_complete = True
    
    # Handle image upload
    if profile_picture and profile_picture.filename:
        import os
        os.makedirs("media/profile_pictures", exist_ok=True)
        file_location = f"media/profile_pictures/lawyer_{current_user.id}_{profile_picture.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await profile_picture.read())
        profile.profile_picture = f"/media/profile_pictures/lawyer_{current_user.id}_{profile_picture.filename}"
        
    await db.commit()

    try:
        from ..notifications import create_and_broadcast_notification
        # 1. Notify the lawyer
        await create_and_broadcast_notification(
            db=db,
            user_id=current_user.id,
            title="Profile Submitted",
            message="Your profile has been submitted and is pending verification.",
            url="/lawyer_dashboard/"
        )
        # 2. Notify all admins
        admins_res = await db.execute(
            select(User).where((User.role == "admin") | (User.is_staff == True))
        )
        admins = admins_res.scalars().all()
        for admin in admins:
            await create_and_broadcast_notification(
                db=db,
                user_id=admin.id,
                title="Lawyer Verification Pending",
                message=f"Lawyer {profile.full_name} has submitted their profile and is pending verification.",
                url="/admin_dashboard/"
            )
    except Exception:
        pass
        
    return {"message": "Profile updated successfully"}



