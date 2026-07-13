from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from pydantic import BaseModel


from ..database import get_db
from ..models import User, LawyerProfile, CaseRequest, CaseDocument, ClientProfile, CaseDocumentVerification, LawyerProfileUpdateRequest, WithdrawRequest
from ..security import get_current_user
from .cloudinary_utils import upload_to_cloudinary

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

    # Fetch real ready cases (verified documents awaiting lawyer acceptance)
    ready_cases_res = await db.execute(
        select(CaseRequest, ClientProfile, User)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .join(User, ClientProfile.user_id == User.id)
        .where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'DOCUMENTS_VERIFIED')
        .order_by(CaseRequest.updated_at.desc())
    )
    ready_rows = ready_cases_res.all()
    ready_data = []
    for req, client_p, client_user in ready_rows:
        ready_data.append({
            "id": req.id,
            "client_name": f"{client_p.first_name} {client_p.last_name}",
            "client_email": client_user.email,
            "created_at": req.created_at.strftime("%b %d, %Y") if req.created_at else "",
            "updated_at": req.updated_at.strftime("%b %d, %Y") if req.updated_at else "",
            "status": req.status,
            "workflow_stage": req.workflow_stage or "pending_review",
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
            "verified_documents": len(ready_data),
            "monthly_revenue": monthly_revenue,
            "yearly_revenue": yearly_revenue,
            "active_clients": active_cases,
            "completed_cases": completed_cases
        },
        "pending_requests": pending_data,
        "ready_cases": ready_data
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
        req.status = "DOCUMENTS_PENDING"
        req.workflow_stage = "DOCUMENT_VERIFICATION"
    elif action == "reject":
        req.status = "REJECTED"
        
    req.response_message = response_message
    await db.commit()
    return {"message": f"Request status updated to {req.status}"}


class WithdrawCreate(BaseModel):
    amount: float
    method: str
    method_details: str


@router.post("/withdraw")
async def request_withdrawal(
    withdrawal: WithdrawCreate,
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    # Fetch lawyer profile
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")

    consultation_fee = float(lawyer_profile.consultation_fee) if lawyer_profile.consultation_fee else 0.0

    # Calculate completed cases count
    completed_res = await db.execute(
        select(func.count()).select_from(CaseRequest)
        .where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'COMPLETED')
    )
    completed_count = completed_res.scalar() or 0
    total_earnings = consultation_fee * completed_count

    # Calculate total already withdrawn/pending
    withdrawn_res = await db.execute(
        select(func.sum(WithdrawRequest.amount)).where(
            WithdrawRequest.lawyer_id == lawyer_profile.id,
            WithdrawRequest.status.in_(["PENDING", "APPROVED"])
        )
    )
    total_withdrawn = float(withdrawn_res.scalar() or 0.0)

    available_balance = total_earnings - total_withdrawn

    if withdrawal.amount > available_balance:
        raise HTTPException(status_code=400, detail="Insufficient withdrawable balance")

    if withdrawal.amount <= 0:
        raise HTTPException(status_code=400, detail="Withdrawal amount must be greater than zero")

    # Create withdrawal request
    req = WithdrawRequest(
        lawyer_id=lawyer_profile.id,
        amount=withdrawal.amount,
        method=withdrawal.method,
        method_details=withdrawal.method_details,
        status="PENDING"
    )
    db.add(req)
    await db.commit()
    return {"message": "Withdrawal request submitted successfully", "id": req.id}


@router.get("/withdrawals")
async def get_lawyer_withdrawals(
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    # Fetch lawyer profile
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")

    res = await db.execute(
        select(WithdrawRequest)
        .where(WithdrawRequest.lawyer_id == lawyer_profile.id)
        .order_by(WithdrawRequest.created_at.desc())
    )
    reqs = res.scalars().all()
    out = []
    for r in reqs:
        out.append({
            "id": r.id,
            "amount": float(r.amount),
            "method": r.method,
            "method_details": r.method_details,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            "admin_notes": r.admin_notes
        })
    return out


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
    
    # Calculate total already withdrawn/pending
    withdrawn_res = await db.execute(
        select(func.sum(WithdrawRequest.amount)).where(
            WithdrawRequest.lawyer_id == lawyer_profile.id,
            WithdrawRequest.status.in_(["PENDING", "APPROVED"])
        )
    )
    total_withdrawn = float(withdrawn_res.scalar() or 0.0)

    available_balance = (consultation_fee * completed_count) - total_withdrawn
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
        select(CaseRequest, ClientProfile, User)
        .join(ClientProfile, CaseRequest.client_id == ClientProfile.id)
        .join(User, ClientProfile.user_id == User.id)
        .where(CaseRequest.lawyer_id == lawyer_profile.id)
        .order_by(CaseRequest.updated_at.desc())
    )
    rows = res.all()
    
    ready_cases = []
    active_cases = []
    completed_cases = []
    pending_verification = []
    rejected_cases = []
    
    for req, client_p, client_user in rows:
        case_data = {
            "id": req.id,
            "client_name": client_p.first_name + " " + client_p.last_name,
            "client_email": client_user.email,
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
        elif req.status == "COMPLETED":
            completed_cases.append(case_data)
        elif req.status in ["PENDING", "DOCUMENTS_PENDING", "DOCUMENTS_SUBMITTED"]:
            pending_verification.append(case_data)
        elif req.status == "REJECTED":
            rejected_cases.append(case_data)
            
    return {
        "ready_cases": ready_cases,
        "active_cases": active_cases,
        "completed_cases": completed_cases,
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
    import random
    if not lawyer_profile:
        # Create an empty profile row to avoid breaking on onboarding
        while True:
            candidate = f"ld:{random.randint(10000, 99999)}"
            check = await db.execute(select(LawyerProfile).where(LawyerProfile.custom_id == candidate))
            if not check.scalar_one_or_none():
                custom_id = candidate
                break
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
            office_city="",
            custom_id=custom_id
        )
        db.add(lawyer_profile)
        await db.commit()
        await db.refresh(lawyer_profile)
    elif not lawyer_profile.custom_id:
        while True:
            candidate = f"ld:{random.randint(10000, 99999)}"
            check = await db.execute(select(LawyerProfile).where(LawyerProfile.custom_id == candidate))
            if not check.scalar_one_or_none():
                lawyer_profile.custom_id = candidate
                break
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
        "profile_picture": lawyer_profile.profile_picture or "",
        "bar_council_license": lawyer_profile.bar_council_license or "",
        "custom_id": lawyer_profile.custom_id,
        "rating": lawyer_profile.rating,
        "verified": lawyer_profile.verified
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
    bar_council_license: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db)
):
    import datetime
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    profile = lawyer_profile_res.scalar_one_or_none()
    if not profile:
        profile = LawyerProfile(user_id=current_user.id)
        db.add(profile)
        
    license_url = profile.bar_council_license if profile else None
    if not license_url and (not bar_council_license or not bar_council_license.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bar Council License document is required."
        )

    if bar_council_license and bar_council_license.filename:
        content = await bar_council_license.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bar Council License document must be under 5 MB."
            )
        await bar_council_license.seek(0)
        license_url = await upload_to_cloudinary(bar_council_license, folder="bar_council_licenses")
        
    # Check if bar_registration_number is already registered to another lawyer
    if bar_registration_number:
        query = select(LawyerProfile).where(LawyerProfile.bar_registration_number == bar_registration_number)
        if profile.id is not None:
            query = query.where(LawyerProfile.id != profile.id)
        existing_bar_res = await db.execute(query)
        if existing_bar_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Bar Registration Number is already registered to another lawyer."
            )
        
    if profile.verified:
        # Check if there is already a pending update request
        pending_res = await db.execute(
            select(LawyerProfileUpdateRequest)
            .where(LawyerProfileUpdateRequest.lawyer_id == profile.id, LawyerProfileUpdateRequest.status == "PENDING")
        )
        if pending_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="You already have a profile update pending approval.")

        dob_parsed = None
        if date_of_birth:
            try:
                dob_parsed = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
                today = datetime.date.today()
                age = today.year - dob_parsed.year - ((today.month, today.day) < (dob_parsed.month, dob_parsed.day))
                if age < 18:
                    raise HTTPException(status_code=400, detail="You must be at least 18 years of age.")
            except HTTPException:
                raise
            except:
                pass
                
        pic_url = profile.profile_picture
        if profile_picture and profile_picture.filename:
            pic_url = await upload_to_cloudinary(profile_picture, folder="profile_pictures")

        update_request = LawyerProfileUpdateRequest(
            lawyer_id=profile.id,
            full_name=full_name,
            gender=gender,
            date_of_birth=dob_parsed,
            bar_registration_number=bar_registration_number,
            state_bar_council=state_bar_council,
            years_of_experience=years_of_experience,
            specialization=specialization,
            consultation_fee=consultation_fee,
            office_city=office_city,
            bio=bio,
            mobile_number=mobile_number,
            alternate_mobile_number=alternate_mobile_number,
            profile_picture=pic_url,
            bar_council_license=license_url,
            status="PENDING"
        )
        db.add(update_request)
        await db.commit()

        try:
            from ..notifications import create_and_broadcast_notification
            await create_and_broadcast_notification(
                db=db,
                user_id=current_user.id,
                title="Profile Update Submitted",
                message="Your profile update has been submitted and is pending verification.",
                url="/lawyer_profile/"
            )
            admin_res = await db.execute(select(User).where((User.is_staff == True) | (User.role == "admin")))
            for admin in admin_res.scalars().all():
                await create_and_broadcast_notification(
                    db=db,
                    user_id=admin.id,
                    title="Lawyer Update Request",
                    message=f"Lawyer {profile.full_name} has requested a profile update.",
                    url=f"/adminpanel/lawyer/update-request/{update_request.id}/"
                )
        except Exception as e:
            print("Notification error:", e)

        return {"message": "Profile update submitted successfully for admin approval."}

    # Initial setup path (Not Verified Yet)
    profile.full_name = full_name
    profile.gender = gender
    if date_of_birth:
        try:
            dob_parsed = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            today = datetime.date.today()
            age = today.year - dob_parsed.year - ((today.month, today.day) < (dob_parsed.month, dob_parsed.day))
            if age < 18:
                raise HTTPException(status_code=400, detail="You must be at least 18 years of age.")
            profile.date_of_birth = dob_parsed
        except HTTPException:
            raise
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
        profile.profile_picture = await upload_to_cloudinary(profile_picture, folder="profile_pictures")
    if license_url:
        profile.bar_council_license = license_url
        
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


@router.post("/cases/{case_id}/accept")
async def lawyer_accept_case(
    case_id: int,
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
        
    case_res = await db.execute(
        select(CaseRequest).where(CaseRequest.id == case_id, CaseRequest.lawyer_id == lawyer_profile.id)
    )
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found or not assigned to you")
        
    if case.status != "DOCUMENTS_VERIFIED":
        raise HTTPException(status_code=400, detail="Case cannot be accepted. Documents must be verified first.")
        
    case.status = "ACCEPTED"
    case.workflow_stage = "LAWYER_ASSIGNED"
    
    await db.commit()
    
    # Notify client
    try:
        from ..notifications import create_and_broadcast_notification
        from .client_actions import ClientProfile
        client_profile_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
        client_profile = client_profile_res.scalar_one_or_none()
        if client_profile:
            await create_and_broadcast_notification(
                db=db,
                user_id=client_profile.user_id,
                title="Case Accepted",
                message=f"Lawyer {lawyer_profile.full_name} has accepted your case and verified your documents.",
                url=f"/client_case_detail/?case_id={case.id}"
            )
    except Exception as e:
        print("Failed to notify client:", e)
        
    return {"status": "success", "message": "Case accepted successfully"}


@router.get("/clients")
async def get_clients_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "lawyer":
        raise HTTPException(status_code=400, detail="Only lawyer users can fetch clients list.")
        
    # Fetch all clients
    result = await db.execute(select(ClientProfile).order_by(ClientProfile.first_name))
    clients = result.scalars().all()
    
    return [
        {
            "id": client.id,
            "full_name": f"{client.first_name} {client.last_name}".strip(),
            "custom_id": client.custom_id
        }
        for client in clients
    ]


@router.post("/report-client")
async def submit_client_report(
    client: int = Form(...),
    reason: str = Form(...),
    description: str = Form(...),
    evidence: List[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "lawyer":
        raise HTTPException(status_code=400, detail="Only lawyer users can submit reports.")
        
    from ..models import TrustReport, Notification
    
    # Verify client exists
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == client))
    client_profile = client_res.scalar_one_or_none()
    if not client_profile:
        raise HTTPException(status_code=404, detail="Client profile not found.")
        
    client_user_res = await db.execute(select(User).where(User.id == client_profile.user_id))
    client_user = client_user_res.scalar_one_or_none()
    
    # Find reporter (lawyer profile)
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found.")
        
    # Create TrustReport first to generate the report ID
    report = TrustReport(
        reporter_id=current_user.id,
        reported_client_id=client_profile.id,
        reason=reason,
        description=description,
        evidence=None,
        status="PENDING"
    )
    db.add(report)
    await db.flush() # Populate report.id

    # Handle multiple evidence files
    if evidence:
        import io
        import zipfile
        import datetime
        from pathlib import Path
        
        valid_files = [f for f in evidence if f.filename and len(f.filename.strip()) > 0]
        if valid_files:
            zip_buffer = io.BytesIO()
            total_size = 0
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file in valid_files:
                    file_content = await file.read()
                    file_size = len(file_content)
                    if file_size > 5 * 1024 * 1024:
                        raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds the 5MB size limit.")
                    total_size += file_size
                    if file_size > 0:
                        zip_file.writestr(file.filename, file_content)
            
            if total_size > 0:
                zip_buffer.seek(0)
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"report_{report.id}_{now_str}.zip"
                upload_dir = Path("media/report_evidence")
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                with open(file_path, "wb") as f:
                    f.write(zip_buffer.getvalue())
                report.evidence = f"report_evidence/{filename}"
                db.add(report)
    
    formatted_report_id = f"ri::{report.id:05d}"
    
    # Create notifications
    lawyer_notification = Notification(
        user_id=current_user.id,
        title="Report Submitted",
        message=f"Your report against {client_profile.first_name} {client_profile.last_name} has been received and is under review. Report ID: {formatted_report_id}",
        url="/lawyers/dashboard/"
    )
    db.add(lawyer_notification)
    
    if client_user:
        client_notification = Notification(
            user_id=client_user.id,
            title="A report has been filed against you",
            message=f"Lawyer {lawyer_profile.full_name} has submitted a report. Admin will review and take action. Report ID: {formatted_report_id}",
            url="/dashboard/"
        )
        db.add(client_notification)
        
    # Notify all admin users
    admin_users_res = await db.execute(select(User).where(User.is_staff == True, User.is_active == True))
    admin_users = admin_users_res.scalars().all()
    for admin in admin_users:
        admin_notification = Notification(
            user_id=admin.id,
            title="New Trust Report Filed",
            message=f"Lawyer {lawyer_profile.full_name} reported Client {client_profile.first_name} {client_profile.last_name}. Report ID: {formatted_report_id}",
            url=f"/adminpanel/reports/{report.id}/"
        )
        db.add(admin_notification)
        
    await db.commit()
    
    # Send email notifications
    from utils.email_utils import send_report_submitted_email, send_client_reported_notification_email
    
    # 1. Send confirmation email to reporting lawyer
    try:
        send_report_submitted_email(
            reporter_name=lawyer_profile.full_name,
            reporter_email=current_user.email,
            reported_name=f"{client_profile.first_name} {client_profile.last_name}",
            report_reason=reason,
            report_id=formatted_report_id
        )
    except Exception:
        pass

    # 2. Send warning email to reported client
    if client_user:
        try:
            send_client_reported_notification_email(
                client_name=f"{client_profile.first_name} {client_profile.last_name}",
                client_email=client_user.email,
                report_reason=reason,
                report_description=description,
                report_id=formatted_report_id
            )
        except Exception:
            pass
        
    return {"status": "success", "message": "Report submitted successfully"}


# --- Lawyer Settings ---

class SettingsUpdatePayload(BaseModel):
    vacationMode: bool
    workingHours: dict
    emailAlerts: bool
    smsAlerts: bool
    twoFactorAuth: bool

@router.get("/settings")
async def get_lawyer_settings(
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")

    import json
    wh = {}
    if lawyer_profile.working_hours:
        try:
            wh = json.loads(lawyer_profile.working_hours)
        except Exception:
            pass
            
    # Default values if not set
    if not wh:
        wh = {
            "monday": {"enabled": True, "start": "09:00", "end": "17:00"},
            "tuesday": {"enabled": True, "start": "09:00", "end": "17:00"},
            "wednesday": {"enabled": True, "start": "09:00", "end": "17:00"},
            "thursday": {"enabled": True, "start": "09:00", "end": "17:00"},
            "friday": {"enabled": True, "start": "09:00", "end": "17:00"}
        }

    return {
        "vacationMode": lawyer_profile.vacation_mode,
        "workingHours": wh,
        "emailAlerts": True,
        "smsAlerts": False,
        "twoFactorAuth": False
    }

@router.post("/settings")
async def save_lawyer_settings(
    payload: SettingsUpdatePayload,
    current_user: User = Depends(check_verified_lawyer),
    db: AsyncSession = Depends(get_db)
):
    lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    lawyer_profile = lawyer_profile_res.scalar_one_or_none()
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")

    import json
    lawyer_profile.vacation_mode = payload.vacationMode
    lawyer_profile.working_hours = json.dumps(payload.workingHours)
    await db.commit()
    return {"message": "Settings updated successfully"}
