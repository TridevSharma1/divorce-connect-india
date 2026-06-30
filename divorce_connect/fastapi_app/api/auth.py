from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
import uuid
import datetime
import logging

from ..database import get_db
from ..models import User, ClientProfile, LawyerProfile, AdminPanelProfile, OTPCode
from ..schemas import Token, UserCreate, UserResponse
from ..security import (
    verify_password, create_access_token, create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, pwd_context,
    get_current_user
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_current_user_details(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the currently logged in user based on the JWT token.
    """
    role = "client"
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == current_user.id))
    if lawyer_res.scalar_one_or_none():
        role = "lawyer"
    else:
        admin_res = await db.execute(select(AdminPanelProfile).where(AdminPanelProfile.user_id == current_user.id))
        if admin_res.scalar_one_or_none():
            role = "admin"
        else:
            client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == current_user.id))
            if client_res.scalar_one_or_none():
                role = "client"

    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "role": role
    }

def render_email_template(template_name: str, context: dict) -> str:
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIRS = [
        BASE_DIR / "templates",
        BASE_DIR / "clients" / "templates",
        BASE_DIR / "lawyers" / "templates",
        BASE_DIR / "adminpanel" / "templates",
        BASE_DIR / "accounts" / "templates",
    ]
    dirs = [str(d) for d in TEMPLATES_DIRS if d.exists()]
    env = Environment(loader=FileSystemLoader(dirs))
    template = env.get_template(template_name)
    return template.render(context)

async def generate_otp_for_user(user_id: int, db: AsyncSession) -> str:
    import random
    import string
    # Invalidate existing OTP codes for this user
    await db.execute(
        update(OTPCode)
        .where(OTPCode.user_id == user_id, OTPCode.is_used == False)
        .values(is_used=True)
    )
    
    code = "".join(random.choices(string.digits, k=6))
    new_otp = OTPCode(
        user_id=user_id,
        code=code,
        created_at=datetime.datetime.utcnow(),
        is_used=False
    )
    db.add(new_otp)
    await db.commit()
    return code

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user in the database.
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = pwd_context.hash(user_in.password)
    new_user = User(
        email=user_in.email,
        password=hashed_password,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        is_active=False,  # Inactive until OTP verified
        is_staff=(user_in.role == 'admin')
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    if user_in.role == 'client':
        profile = ClientProfile(
            user_id=new_user.id,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            gender='other',
            marital_status='single',
            mobile_number=''
        )
        db.add(profile)
    elif user_in.role == 'lawyer':
        profile = LawyerProfile(
            user_id=new_user.id,
            full_name=f"{user_in.first_name} {user_in.last_name}",
            gender='other',
            bar_registration_number=f"PENDING-{new_user.id}",
            state_bar_council='',
            years_of_experience=0,
            specialization='other',
            mobile_number='',
            bio='',
            office_city=''
        )
        db.add(profile)
    elif user_in.role == 'admin':
        profile = AdminPanelProfile(
            user_id=new_user.id,
            full_name=f"{user_in.first_name} {user_in.last_name}",
            gender='other',
            mobile_number=''
        )
        db.add(profile)

    await db.commit()
    await db.refresh(new_user)

    # Generate OTP
    otp_code = await generate_otp_for_user(new_user.id, db)

    # Send Email
    try:
        from ..notifications import send_email
        html_body = render_email_template(
            "emails/register_otp_email.html",
            {
                "user_name": new_user.get_full_name(),
                "otp_code": otp_code,
            }
        )
        send_email(
            to_address=new_user.email,
            subject="✉️ Verify Your Email — DivorceConnect India",
            html_body=html_body,
            purpose="auth"
        )
    except Exception as e:
        logger.error(f"Failed to dispatch register OTP email: {e}")

    return {
        "message": "Registration successful, OTP sent",
        "email": new_user.email,
        "redirect": "/verify-register-otp/"
    }

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user, generate OTP, and send via email.
    """
    # Assuming form_data.username contains the email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Generate OTP code
    otp_code = await generate_otp_for_user(user.id, db)
    
    # Send Email
    try:
        from ..notifications import send_email
        now_local = datetime.datetime.utcnow()
        html_body = render_email_template(
            "emails/otp_email.html",
            {
                "user_name": user.get_full_name(),
                "otp_code": otp_code,
                "login_time": now_local.strftime("%d %b %Y, %I:%M %p"),
            }
        )
        send_email(
            to_address=user.email,
            subject="🔐 Your Login OTP — DivorceConnect India",
            html_body=html_body,
            purpose="auth"
        )
    except Exception as e:
        logger.error(f"Failed to dispatch login OTP email: {e}")

    return {
        "message": "OTP sent",
        "email": user.email,
        "redirect": "/verify-otp/"
    }


@router.post("/token/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Take a refresh token and return a new access token.
    Replaces DRF's TokenRefreshView.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    user_id = user.id if user else None
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email, "user_id": user_id}, expires_delta=access_token_expires
    )
    # Return the same refresh token or generate a new one
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


class DeleteAccountRequest(BaseModel):
    email: EmailStr


@router.post("/delete-account")
async def delete_account_request(
    payload: DeleteAccountRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if payload.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address you entered does not match your registered account email."
        )
        
    token_str = str(uuid.uuid4())
    
    # Save token in database
    from ..models import DeleteAccountToken
    new_token = DeleteAccountToken(
        token=token_str,
        user_id=current_user.id,
        is_used=False,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_token)
    await db.commit()
    
    # Send email
    from ..notifications import send_email
    confirm_url = f"http://{request.url.netloc}/api/auth/confirm-delete/{token_str}"
    
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
        <h2 style="color: #dc2626; text-align: center;">DivorceConnect India</h2>
        <p>Hello {current_user.first_name},</p>
        <p>We received a request to permanently deactivate and delete your account.</p>
        <p>To confirm this deactivation and delete your account data, click the button below within 30 minutes:</p>
        <p style="text-align: center;">
            <a href="{confirm_url}" style="background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">Confirm Deactivation & Deletion</a>
        </p>
        <p style="color: #666; font-size: 0.9em; margin-top: 20px;">If you did not request this, please ignore this email or contact support.</p>
    </div>
    """
    
    try:
        send_email(
            current_user.email,
            "⚠️ Confirm Account Deactivation",
            html_body
        )
    except Exception as e:
        pass
        
    return {"message": "A deletion confirmation link has been sent to your email. Please check your inbox and click the link within 30 minutes."}


@router.get("/confirm-delete/{token}", response_class=HTMLResponse)
async def confirm_delete_account(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    from ..models import DeleteAccountToken, ClientProfile, LawyerProfile, User
    
    # Query token
    res = await db.execute(select(DeleteAccountToken).where(DeleteAccountToken.token == token, DeleteAccountToken.is_used == False))
    token_obj = res.scalar_one_or_none()
    
    if not token_obj:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invalid Deactivation Link</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
            <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl text-center border-t-4 border-red-600">
                <h1 class="text-2xl font-bold text-gray-900 mb-2">Invalid or Expired Link</h1>
                <p class="text-sm text-gray-600 mb-6">This deletion link is invalid, has expired, or has already been used.</p>
                <a href="/" class="inline-block bg-gray-900 text-white font-semibold px-6 py-3 rounded-xl hover:bg-gray-800 transition">Go to Homepage</a>
            </div>
        </body>
        </html>
        """
        
    # Check if expired (30 minutes)
    now = datetime.datetime.utcnow()
    if (now - token_obj.created_at).total_seconds() > 1800:
        token_obj.is_used = True
        await db.commit()
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Deactivation Link Expired</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
            <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl text-center border-t-4 border-red-600">
                <h1 class="text-2xl font-bold text-gray-900 mb-2">Deactivation Link Expired</h1>
                <p class="text-sm text-gray-600 mb-6">This deletion link has expired. Please request account deactivation again.</p>
                <a href="/" class="inline-block bg-gray-900 text-white font-semibold px-6 py-3 rounded-xl hover:bg-gray-800 transition">Go to Homepage</a>
            </div>
        </body>
        </html>
        """
        
    # Mark token as used
    token_obj.is_used = True
    
    # Soft delete profiles
    # ClientProfile
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == token_obj.user_id))
    client_prof = client_res.scalar_one_or_none()
    if client_prof:
        client_prof.is_deleted = True
        
    # LawyerProfile
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == token_obj.user_id))
    lawyer_prof = lawyer_res.scalar_one_or_none()
    if lawyer_prof:
        lawyer_prof.is_deleted = True
        
    # Deactivate User
    user_res = await db.execute(select(User).where(User.id == token_obj.user_id))
    user_obj = user_res.scalar_one_or_none()
    if user_obj:
        user_obj.is_active = False
        
    await db.commit()
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Account Deactivated</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl text-center border-t-4 border-emerald-600">
            <h1 class="text-2xl font-bold text-gray-900 mb-2">Account Successfully Deactivated</h1>
            <p class="text-sm text-gray-600 mb-6">Your profile and account listings have been soft-deleted. We're sorry to see you go.</p>
            <a href="/" class="inline-block bg-emerald-600 text-white font-semibold px-6 py-3 rounded-xl hover:bg-emerald-700 transition">Go to Homepage</a>
        </div>
    </body>
    </html>
    """

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

@router.post("/verify-otp")
async def verify_otp(
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp_res = await db.execute(
        select(OTPCode)
        .where(OTPCode.user_id == user.id, OTPCode.is_used == False, OTPCode.code == payload.otp.strip())
        .order_by(OTPCode.created_at.desc())
    )
    otp_obj = otp_res.scalars().first()
    
    if not otp_obj:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    now = datetime.datetime.utcnow()
    created_at = otp_obj.created_at
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
        
    if now > created_at + datetime.timedelta(minutes=10):
        raise HTTPException(status_code=400, detail="This OTP has expired. Please request a new one.")
        
    otp_obj.is_used = True
    user.is_active = True
    await db.commit()
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, expires_delta=access_token_expires
    )
    
    try:
        from ..notifications import send_email
        html_body = render_email_template(
            "emails/welcome_back_email.html",
            {
                "user_name": user.get_full_name(),
                "user_email": user.email,
                "login_time": now.strftime("%d %b %Y, %I:%M %p"),
            }
        )
        send_email(
            to_address=user.email,
            subject="👋 Welcome Back — DivorceConnect India",
            html_body=html_body,
            purpose="auth"
        )
    except Exception as e:
        logger.error(f"Failed to send welcome back email: {e}")
        
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/verify-register-otp")
async def verify_register_otp(
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp_res = await db.execute(
        select(OTPCode)
        .where(OTPCode.user_id == user.id, OTPCode.is_used == False, OTPCode.code == payload.otp.strip())
        .order_by(OTPCode.created_at.desc())
    )
    otp_obj = otp_res.scalars().first()
    
    if not otp_obj:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    now = datetime.datetime.utcnow()
    created_at = otp_obj.created_at
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
        
    if now > created_at + datetime.timedelta(minutes=10):
        raise HTTPException(status_code=400, detail="This OTP has expired. Please request a new one.")
        
    otp_obj.is_used = True
    user.is_active = True
    await db.commit()

    try:
        from ..notifications import create_and_broadcast_notification
        await create_and_broadcast_notification(
            db=db,
            user_id=user.id,
            title="Registration Successful",
            message="Welcome to DivorceConnect India! Your account is active and verified.",
            url="/"
        )
    except Exception:
        pass
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, expires_delta=access_token_expires
    )
    
    try:
        from ..notifications import send_email
        role_labels = {
            "client": "Client Account",
            "lawyer": "Lawyer Account",
            "admin": "Admin Account",
        }
        html_body = render_email_template(
            "emails/registration_email.html",
            {
                "user_name": user.get_full_name(),
                "role_label": role_labels.get(user.role, "User Account"),
            }
        )
        send_email(
            to_address=user.email,
            subject="🎉 Welcome to DivorceConnect India — Registration Successful",
            html_body=html_body,
            purpose="auth"
        )
    except Exception as e:
        logger.error(f"Failed to send registration email: {e}")
        
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }

