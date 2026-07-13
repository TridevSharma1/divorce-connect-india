from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import datetime

from ..database import get_db
from ..models import User, ClientProfile, LawyerProfile, CaseRequest, LawyerRating
from ..security import get_current_user
from .cloudinary_utils import upload_to_cloudinary

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
            "custom_id": lawyer.custom_id,
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

@router.get("/lawyers/active")
async def get_active_lawyers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(LawyerProfile)
        .where(LawyerProfile.verified == True, LawyerProfile.is_profile_complete == True, LawyerProfile.is_deleted == False)
        .order_by(LawyerProfile.full_name)
    )
    lawyers = res.scalars().all()
    return [
        {
            "id": l.id,
            "full_name": l.full_name,
            "custom_id": l.custom_id,
            "specialization": l.specialization,
            "specialization_display": l.get_specialization_display
        }
        for l in lawyers
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
            select(CaseRequest)
            .where(
                CaseRequest.client_id == client.id,
                CaseRequest.lawyer_id == lawyer_id,
                CaseRequest.status.in_([
                    "PENDING",
                    "DOCUMENTS_PENDING",
                    "DOCUMENTS_SUBMITTED",
                    "DOCUMENTS_VERIFIED",
                    "ACCEPTED",
                    "ACTIVE"
                ])
            )
            .order_by(CaseRequest.updated_at.desc())
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
        "custom_id": lawyer.custom_id,
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
    if not client or not client.first_name or not client.last_name or not client.gender or not client.marital_status or not client.mobile_number or not client.date_of_birth or not client.address or not client.pincode:
        raise HTTPException(status_code=400, detail="profile_incomplete")
        
    # Check if lawyer exists
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer_id))
    lawyer = lawyer_res.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    # Prevent duplicate active/pending requests for the same lawyer
    existing_req_res = await db.execute(
        select(CaseRequest)
        .where(
            CaseRequest.client_id == client.id,
            CaseRequest.lawyer_id == lawyer.id,
            CaseRequest.status.in_([
                "PENDING",
                "DOCUMENTS_PENDING",
                "DOCUMENTS_SUBMITTED",
                "DOCUMENTS_VERIFIED",
                "ACCEPTED",
                "ACTIVE"
            ])
        )
        .order_by(CaseRequest.updated_at.desc())
    )
    existing_request = existing_req_res.scalar_one_or_none()
    if existing_request:
        raise HTTPException(status_code=400, detail="existing_request")
        
    # Create Case Request
    import random
    while True:
        candidate = f"ci:{random.randint(10000, 99999)}"
        check = await db.execute(select(CaseRequest).where(CaseRequest.custom_id == candidate))
        if not check.scalar_one_or_none():
            custom_id = candidate
            break

    new_request = CaseRequest(
        client_id=client.id,
        lawyer_id=lawyer.id,
        message=message,
        status="PENDING",
        workflow_stage="request_sent",
        custom_id=custom_id
    )
    
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)

    try:
        from ..notifications import create_and_broadcast_notification
        # Notify client
        await create_and_broadcast_notification(
            db=db,
            user_id=current_user.id,
            title="Hire Request Sent",
            message=f"Your hire request has been sent to {lawyer.full_name}.",
            url="/client_dashboard/"
        )
        # Notify lawyer
        await create_and_broadcast_notification(
            db=db,
            user_id=lawyer.user_id,
            title="New Hire Request",
            message=f"You have received a new case request from {client.first_name} {client.last_name}.",
            url="/lawyer_dashboard/"
        )
    except Exception:
        pass
    
    return {"message": "Hire request sent successfully", "request_id": new_request.id}

@router.get("/profile")
async def get_client_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    profile = res.scalar_one_or_none()
    import random
    if not profile:
        # Create a default profile on the fly if missing
        while True:
            candidate = f"cl:{random.randint(10000, 99999)}"
            check = await db.execute(select(ClientProfile).where(ClientProfile.custom_id == candidate))
            if not check.scalar_one_or_none():
                custom_id = candidate
                break
        profile = ClientProfile(
            user_id=current_user.id,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            gender="other",
            marital_status="single",
            mobile_number="",
            custom_id=custom_id
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    elif not profile.custom_id:
        while True:
            candidate = f"cl:{random.randint(10000, 99999)}"
            check = await db.execute(select(ClientProfile).where(ClientProfile.custom_id == candidate))
            if not check.scalar_one_or_none():
                profile.custom_id = candidate
                break
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
        "email": current_user.email,
        "custom_id": profile.custom_id
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
            dob_parsed = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            today = datetime.date.today()
            age = today.year - dob_parsed.year - ((today.month, today.day) < (dob_parsed.month, dob_parsed.day))
            if age < 18:
                raise HTTPException(status_code=400, detail="You must be at least 18 years of age.")
            profile.date_of_birth = dob_parsed
        except HTTPException:
            raise
        except Exception:
            pass
            
    if profile_picture and profile_picture.filename:
        profile.profile_picture = await upload_to_cloudinary(profile_picture, folder="profile_pictures")
        
    current_user.first_name = first_name
    current_user.last_name = last_name
    
    await db.commit()

    try:
        from ..notifications import create_and_broadcast_notification
        await create_and_broadcast_notification(
            db=db,
            user_id=current_user.id,
            title="Profile Updated",
            message="Your profile has been successfully updated.",
            url="/client_profile/"
        )
    except Exception:
        pass
    
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



@router.post("/report-lawyer")
async def submit_trust_report(
    lawyer: int = Form(...),
    reason: str = Form(...),
    description: str = Form(...),
    evidence: List[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    import zipfile
    import io
    import uuid
    from pathlib import Path
    from ..models import TrustReport, Notification

    # Find client profile associated with current user
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
    client = client_res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Only client users can submit reports.")

    # Find reported lawyer profile
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == lawyer))
    reported_lawyer = lawyer_res.scalar_one_or_none()
    if not reported_lawyer:
        raise HTTPException(status_code=404, detail="Lawyer profile not found.")

    # Fetch lawyer user
    lawyer_user_res = await db.execute(select(User).where(User.id == reported_lawyer.user_id))
    reported_lawyer_user = lawyer_user_res.scalar_one_or_none()

    # Create TrustReport first to generate the report ID
    report = TrustReport(
        reporter_id=current_user.id,
        reported_lawyer_id=reported_lawyer.id,
        reason=reason,
        description=description,
        evidence=None,
        status="PENDING"
    )
    db.add(report)
    await db.flush() # Populate report.id

    # Process evidence files: zip them together
    if evidence:
        # Check if there's actually files uploaded (filename could be empty)
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
                import datetime
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"report_{report.id}_{now_str}.zip"
                upload_dir = Path("media/report_evidence")
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                with open(file_path, "wb") as f:
                    f.write(zip_buffer.getvalue())
                report.evidence = f"report_evidence/{filename}" # Relative to media directory as Django expects
                db.add(report)

    # Create notifications
    formatted_report_id = f"ri::{report.id:05d}"

    client_notification = Notification(
        user_id=current_user.id,
        title="Report Submitted",
        message=f"Your report against {reported_lawyer.full_name} has been received and is under review. Report ID: {formatted_report_id}",
        url="/client_dashboard/"
    )
    db.add(client_notification)

    if reported_lawyer_user:
        lawyer_notification = Notification(
            user_id=reported_lawyer_user.id,
            title="A report has been filed against you",
            message=f"An anonymous client has submitted a report. Admin will review and take action. Report ID: {formatted_report_id}",
            url="/lawyers/dashboard/"
        )
        db.add(lawyer_notification)

    # Notify all admin users
    admin_users_res = await db.execute(select(User).where(User.is_staff == True, User.is_active == True))
    admin_users = admin_users_res.scalars().all()
    for admin in admin_users:
        admin_notification = Notification(
            user_id=admin.id,
            title="New Trust Report Filed",
            message=f"Client {client.first_name} {client.last_name} reported Lawyer {reported_lawyer.full_name}. Report ID: {formatted_report_id}",
            url=f"/adminpanel/reports/{report.id}/"
        )
        db.add(admin_notification)

    await db.commit()

    # Send emails
    from utils.email_utils import send_report_submitted_email, send_lawyer_reported_notification_email
    
    # 1. Send confirmation to client
    try:
        send_report_submitted_email(
            reporter_name=f"{client.first_name} {client.last_name}",
            reporter_email=current_user.email,
            reported_name=reported_lawyer.full_name,
            report_reason=reason,
            report_id=formatted_report_id
        )
    except Exception:
        pass

    # 2. Send notice to the reported lawyer (without client details)
    if reported_lawyer_user:
        try:
            send_lawyer_reported_notification_email(
                lawyer_name=reported_lawyer.full_name,
                lawyer_email=reported_lawyer_user.email,
                report_reason=reason,
                report_description=description,
                report_id=formatted_report_id
            )
        except Exception:
            pass

    return {"message": "Report submitted successfully"}


