from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import os
import shutil
import datetime

from ..database import get_db
from ..models import User, LawyerProfile, CaseRequest, ClientProfile, LawyerRating
from ..security import get_current_user

router = APIRouter()

@router.get("/lawyers")
async def list_verified_lawyers(
    specialization: Optional[str] = None,
    office_city: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(LawyerProfile).where(LawyerProfile.verified == True)
    if specialization:
        query = query.where(LawyerProfile.specialization == specialization)
    if office_city:
        query = query.where(LawyerProfile.office_city.ilike(f"%{office_city}%"))
        
    res = await db.execute(query)
    lawyers = res.scalars().all()
    
    return [
        {
            "id": lawyer.id,
            "full_name": lawyer.full_name,
            "specialization": lawyer.specialization,
            "years_of_experience": lawyer.years_of_experience,
            "rating": lawyer.rating,
            "rating_count": lawyer.rating_count,
            "consultation_fee": float(lawyer.consultation_fee) if lawyer.consultation_fee else 0.0,
            "office_city": lawyer.office_city,
            "profile_picture": lawyer.profile_picture,
            "bio": lawyer.bio
        }
        for lawyer in lawyers
    ]

@router.get("/lawyers/{lawyer_id}")
async def get_lawyer_details(
    lawyer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")
        
    # Check if this client already has a case request with this lawyer
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    case_request = None
    has_rated = False
    if client:
        req_res = await db.execute(
            select(CaseRequest).where(CaseRequest.client_id == client.id, CaseRequest.lawyer_id == lawyer_id)
        )
        req = req_res.scalar_one_or_none()
        if req:
            case_request = {
                "id": req.id,
                "status": req.status,
                "workflow_stage": req.workflow_stage,
                "response_message": req.response_message
            }
        
        rating_exists_res = await db.execute(
            select(LawyerRating).where(LawyerRating.client_id == client.id, LawyerRating.lawyer_id == lawyer_id)
        )
        has_rated = rating_exists_res.scalar_one_or_none() is not None
        
    reviews_res = await db.execute(
        select(LawyerRating, ClientProfile)
        .join(ClientProfile, LawyerRating.client_id == ClientProfile.id)
        .where(LawyerRating.lawyer_id == lawyer_id)
        .order_by(LawyerRating.created_at.desc())
        .limit(10)
    )
    reviews_list = [
        {
            "id": r.id,
            "score": r.score,
            "review_text": r.review_text,
            "created_at": r.created_at.strftime("%d %b %Y"),
            "client_name": f"{c.first_name} {c.last_name}"
        }
        for r, c in reviews_res.all()
    ]

    return {
        "id": lawyer.id,
        "full_name": lawyer.full_name,
        "gender": lawyer.gender or "other",
        "date_of_birth": lawyer.date_of_birth.strftime("%Y-%m-%d") if lawyer.date_of_birth else "",
        "mobile_number": lawyer.mobile_number or "",
        "alternate_mobile_number": lawyer.alternate_mobile_number or "",
        "specialization": lawyer.specialization,
        "years_of_experience": lawyer.years_of_experience,
        "rating": lawyer.rating,
        "rating_count": lawyer.rating_count,
        "consultation_fee": float(lawyer.consultation_fee) if lawyer.consultation_fee else 0.0,
        "office_city": lawyer.office_city,
        "profile_picture": lawyer.profile_picture,
        "bio": lawyer.bio,
        "state_bar_council": lawyer.state_bar_council,
        "bar_registration_number": lawyer.bar_registration_number,
        "case_request": case_request,
        "has_rated": has_rated,
        "reviews": reviews_list
    }

@router.post("/lawyers/{lawyer_id}/hire")
async def hire_lawyer(
    lawyer_id: int,
    message: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find client profile associated with current user
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Only clients can hire lawyers. Please complete client profile.")
        
    # Check if lawyer exists
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = lawyer_res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")
        
    # Create Case Request
    new_request = CaseRequest(
        client_id=client.id,
        lawyer_id=lawyer.id,
        message=message,
        status="PENDING",
        workflow_stage="request_sent"
    )
    
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    
    return {"message": "Hire request sent successfully", "request_id": new_request.id}

@router.get("/profile")
async def get_client_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    profile = res.scalar_one_or_none()
    if not profile:
        # Create a default profile on the fly if missing
        profile = ClientProfile(
            user_id=current_user.id,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            gender="other",
            marital_status="single",
            mobile_number=""
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "gender": profile.gender,
        "marital_status": profile.marital_status,
        "mobile_number": profile.mobile_number,
        "alternate_mobile_number": profile.alternate_mobile_number or "",
        "address": profile.address or "",
        "pincode": profile.pincode or "",
        "date_of_birth": profile.date_of_birth.strftime("%Y-%m-%d") if profile.date_of_birth else "",
        "profile_picture": profile.profile_picture,
        "email": current_user.email
    }

@router.post("/profile")
async def update_client_profile(
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    marital_status: str = Form(...),
    mobile_number: str = Form(...),
    alternate_mobile_number: str | None = Form(None),
    address: str | None = Form(None),
    pincode: str | None = Form(None),
    date_of_birth: str | None = Form(None),
    profile_picture: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    profile = res.scalar_one_or_none()
    if not profile:
        profile = ClientProfile(user_id=current_user.id)
        db.add(profile)
        
    profile.first_name = first_name
    profile.last_name = last_name
    profile.gender = gender
    profile.marital_status = marital_status
    profile.mobile_number = mobile_number
    profile.alternate_mobile_number = alternate_mobile_number or ""
    profile.address = address or ""
    profile.pincode = pincode or ""
    
    if date_of_birth and date_of_birth.strip():
        try:
            profile.date_of_birth = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except Exception:
            pass
            
    if profile_picture and profile_picture.filename:
        os.makedirs("media/profile_pictures", exist_ok=True)
        file_location = f"media/profile_pictures/{current_user.id}_{profile_picture.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(profile_picture.file, file_object)
        profile.profile_picture = f"/media/profile_pictures/{current_user.id}_{profile_picture.filename}"
        
    current_user.first_name = first_name
    current_user.last_name = last_name
    
    await db.commit()
    return {"message": "Profile updated successfully"}

@router.post("/deactivate")
async def deactivate_client_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    profile = res.scalar_one_or_none()
    if profile:
        profile.is_deleted = True
        
    current_user.is_active = False
    await db.commit()
    return {"message": "Account deactivated successfully"}


@router.post("/lawyers/{lawyer_id}/rate")
async def rate_lawyer(
    lawyer_id: int,
    rating: int = Form(...),
    review_text: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find client
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Only clients can rate lawyers.")

    # Check if lawyer exists
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = lawyer_res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    # Check if already rated
    rating_exists_res = await db.execute(
        select(LawyerRating).where(LawyerRating.client_id == client.id, LawyerRating.lawyer_id == lawyer_id)
    )
    if rating_exists_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already rated this lawyer.")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")

    # Add rating
    new_rating = LawyerRating(
        lawyer_id=lawyer.id,
        client_id=client.id,
        score=rating,
        review_text=review_text
    )
    db.add(new_rating)

    # Recalculate average rating and rating_count
    current_total = (lawyer.rating * lawyer.rating_count) if lawyer.rating_count else 0
    lawyer.rating_count = (lawyer.rating_count or 0) + 1
    lawyer.rating = (current_total + rating) / lawyer.rating_count

    await db.commit()
    return {"message": "Rating submitted successfully", "average_rating": lawyer.rating}


