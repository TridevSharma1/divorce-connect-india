import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from ..database import get_db
from ..models import User, CaseRequest, Payment, ClientProfile, LawyerProfile
from ..security import get_current_user
from ..notifications import manager, send_email

router = APIRouter()

# --- Schemas ---
class PaymentCreate(BaseModel):
    case_request_id: int
    amount: float
    razorpay_payment_id: Optional[str] = None

class PaymentVerify(BaseModel):
    razorpay_payment_id: str
    status: str  # "SUCCEEDED" or "FAILED"

class PaymentResponse(BaseModel):
    id: int
    case_request_id: int
    amount: float
    currency: str
    razorpay_payment_id: Optional[str]
    status: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# --- Endpoints ---

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify CaseRequest exists and user has authorization
    result = await db.execute(select(CaseRequest).where(CaseRequest.id == payment_in.case_request_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case request not found")

    # Access client profile to check ownership
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
    client = client_res.scalar_one_or_none()
    
    # Allow if user is either the client who made the request, the lawyer assigned, or an admin
    is_client_user = client and client.user_id == current_user.id
    
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == case.lawyer_id))
    lawyer = lawyer_res.scalar_one_or_none()
    is_lawyer_user = lawyer and lawyer.user_id == current_user.id
    
    if not (is_client_user or is_lawyer_user or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Not authorized to create payment for this case")

    # Create Payment
    payment = Payment(
        case_request_id=payment_in.case_request_id,
        amount=payment_in.amount,
        currency="INR",
        razorpay_payment_id=payment_in.razorpay_payment_id,
        status="PENDING"
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # Broadcast notification to both Client and Lawyer via WebSocket
    msg = f"New pending payment of INR {payment.amount} created for Case Request #{case.id}"
    if client:
        await manager.send_personal_message(msg, user_id=client.user_id)
    if lawyer:
        await manager.send_personal_message(msg, user_id=lawyer.user_id)

    return payment


@router.post("/{payment_id}/verify", response_model=PaymentResponse)
async def verify_payment(
    payment_id: int,
    verification: PaymentVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch Payment
    res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    # Fetch Case Request
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == payment.case_request_id))
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Associated Case Request not found")

    # Update Payment status
    payment.status = "SUCCEEDED" if verification.status.upper() == "SUCCEEDED" else "FAILED"
    if verification.razorpay_payment_id:
        payment.razorpay_payment_id = verification.razorpay_payment_id
    
    await db.commit()
    await db.refresh(payment)

    # Fetch user accounts to send notifications/emails
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
    client = client_res.scalar_one_or_none()
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == case.lawyer_id))
    lawyer = lawyer_res.scalar_one_or_none()

    # Real-time WebSocket notifications
    status_msg = f"Payment #{payment.id} for Case Request #{case.id} was {payment.status}!"
    if client:
        await manager.send_personal_message(status_msg, user_id=client.user_id)
        # Fetch client's User details to get email
        user_res = await db.execute(select(User).where(User.id == client.user_id))
        client_user = user_res.scalar_one_or_none()
        if client_user and client_user.email:
            # Send Email Notification
            email_body = f"""
            <html>
                <body>
                    <h2>Payment Status Update</h2>
                    <p>Dear {client.first_name},</p>
                    <p>Your payment of <b>INR {payment.amount}</b> for Case Request #{case.id} has been processed.</p>
                    <p>Status: <b>{payment.status}</b></p>
                    <p>Razorpay Transaction ID: {payment.razorpay_payment_id or 'N/A'}</p>
                    <br>
                    <p>Regards,</p>
                    <p>DivorceConnect India Team</p>
                </body>
            </html>
            """
            send_email(to_address=client_user.email, subject="Payment Status Update - DivorceConnect", html_body=email_body)

    if lawyer:
        await manager.send_personal_message(status_msg, user_id=lawyer.user_id)

    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_details(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    # Authorize if admin, or user is client/lawyer for the case
    case_res = await db.execute(select(CaseRequest).where(CaseRequest.id == payment.case_request_id))
    case = case_res.scalar_one_or_none()
    if case and not current_user.is_staff:
        client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == case.client_id))
        client = client_res.scalar_one_or_none()
        lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == case.lawyer_id))
        lawyer = lawyer_res.scalar_one_or_none()
        
        is_owner = (client and client.user_id == current_user.id) or (lawyer and lawyer.user_id == current_user.id)
        if not is_owner:
            raise HTTPException(status_code=403, detail="Not authorized to view payment details")

    return payment


@router.get("/", response_model=List[PaymentResponse])
async def list_payments(
    case_id: Optional[int] = Query(None, alias="case_id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.is_staff:
        # Admin can view all payments or filter
        if case_id:
            query = select(Payment).where(Payment.case_request_id == case_id)
        else:
            query = select(Payment)
    else:
        # Client or Lawyer sees their payments
        client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
        client = client_res.scalar_one_or_none()
        
        lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
        lawyer = lawyer_res.scalar_one_or_none()

        conditions = []
        if client:
            # Subquery for client's cases
            cases_res = await db.execute(select(CaseRequest.id).where(CaseRequest.client_id == client.id))
            client_case_ids = [r for r in cases_res.scalars().all()]
            conditions.append(Payment.case_request_id.in_(client_case_ids))
        if lawyer:
            # Subquery for lawyer's cases
            cases_res = await db.execute(select(CaseRequest.id).where(CaseRequest.lawyer_id == lawyer.id))
            lawyer_case_ids = [r for r in cases_res.scalars().all()]
            conditions.append(Payment.case_request_id.in_(lawyer_case_ids))

        if not conditions:
            return []

        from sqlalchemy import or_
        query = select(Payment).where(or_(*conditions))
        if case_id:
            query = query.where(Payment.case_request_id == case_id)

    res = await db.execute(query)
    return res.scalars().all()
