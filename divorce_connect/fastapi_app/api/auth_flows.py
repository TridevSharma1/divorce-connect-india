from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from pydantic import BaseModel, EmailStr
import uuid
import datetime
from datetime import timedelta

from ..database import get_db
from ..models import User, OTPCode, DeleteAccountToken
from ..security import get_current_user

router = APIRouter()

class EmailRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class AdminDeleteRequestSchema(BaseModel):
    reason: str

@router.post("/forgot-password")
async def forgot_password(req: EmailRequest, db: AsyncSession = Depends(get_db)):
    # In a real system, send OTP email here
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate OTP
    import random
    otp_code_str = str(random.randint(100000, 999999))
    new_otp = OTPCode(user_id=user.id, code=otp_code_str)
    db.add(new_otp)
    await db.commit()
    
    # TODO: Send email with OTP via background task
    return {"message": "OTP sent to email", "otp_debug": otp_code_str}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    from ..security import pwd_context
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    otp_res = await db.execute(
        select(OTPCode).where(
            OTPCode.user_id == user.id,
            OTPCode.code == req.otp,
            OTPCode.is_used == False
        )
    )
    otp_obj = otp_res.scalars().first()
    if not otp_obj:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Reset password
    user.password = pwd_context.hash(req.new_password)
    otp_obj.is_used = True
    await db.commit()
    
    return {"message": "Password reset successfully"}

@router.post("/request-delete")
async def request_delete(req: EmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token = str(uuid.uuid4())
    del_token = DeleteAccountToken(user_id=user.id, token=token)
    db.add(del_token)
    await db.commit()
    
    # TODO: send email with link /api/auth/confirm-delete?token={token}
    return {"message": "Deletion link sent", "token_debug": token}

@router.get("/confirm-delete")
async def confirm_delete(token: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DeleteAccountToken).where(DeleteAccountToken.token == token, DeleteAccountToken.is_used == False))
    del_token = res.scalars().first()
    
    if not del_token:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    user_res = await db.execute(select(User).where(User.id == del_token.user_id))
    user = user_res.scalars().first()
    if user:
        user.is_active = False
        del_token.is_used = True
        await db.commit()
        return {"message": "Account deactivated. It will be permanently deleted in 14 days. You can cancel deletion within this period."}
    return {"message": "Error"}

@router.post("/admin-delete-request")
async def admin_delete_request(req: AdminDeleteRequestSchema, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "adminpanel":
        raise HTTPException(status_code=403, detail="Not authorized")
    from ..models import AdminDeleteRequest
    
    del_req = AdminDeleteRequest(user_id=user.id, reason=req.reason)
    db.add(del_req)
    await db.commit()
    return {"message": "Deletion request submitted to superuser"}
