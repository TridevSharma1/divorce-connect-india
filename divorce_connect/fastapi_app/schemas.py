from pydantic import BaseModel, EmailStr
from typing import Optional
import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    username: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime.datetime
    role: str
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None

    class Config:
        from_attributes = True

# --- Notification Schemas ---
class NotificationBase(BaseModel):
    title: str
    message: str
    url: Optional[str] = None

class NotificationCreate(NotificationBase):
    pass



class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True
