import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, Float, DECIMAL, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "accounts_baseuser"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Role-based access: superadmin, staff, client, lawyer
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="client")
    # Optional field for Razorpay customer id
    razorpay_customer_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    password: Mapped[str] = mapped_column(String(128))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    date_joined: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    last_login: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "accounts_notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class OTPCode(Base):
    __tablename__ = "accounts_otpcode"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(6))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", backref="otp_codes")


class ClientProfile(Base):
    __tablename__ = "clients_clientprofile"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id", ondelete="CASCADE"), unique=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    gender: Mapped[str] = mapped_column(String(10))
    date_of_birth: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    marital_status: Mapped[str] = mapped_column(String(20))
    mobile_number: Mapped[str] = mapped_column(String(13))
    alternate_mobile_number: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    date_of_join: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    
    user = relationship("User", backref="client_profile")


class LawyerProfile(Base):
    __tablename__ = "lawyers_lawyerprofile"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str] = mapped_column(String(10))
    date_of_birth: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    bar_registration_number: Mapped[str] = mapped_column(String(50), unique=True)
    state_bar_council: Mapped[str] = mapped_column(String(100))
    years_of_experience: Mapped[int] = mapped_column(Integer)
    specialization: Mapped[str] = mapped_column(String(50))
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_total: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_profile_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    mobile_number: Mapped[str] = mapped_column(String(13))
    alternate_mobile_number: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bio: Mapped[str] = mapped_column(Text)
    consultation_fee: Mapped[Optional[float]] = mapped_column(DECIMAL, nullable=True)
    office_city: Mapped[str] = mapped_column(String(100))
    date_joined: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    
    user = relationship("User", backref="lawyer_profile")


class AdminPanelProfile(Base):
    __tablename__ = "adminpanel_adminpanelprofile"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str] = mapped_column(String(10))
    date_of_birth: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    mobile_number: Mapped[str] = mapped_column(String(13))
    alternate_mobile_number: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_profile_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified_by_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    date_of_join: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    user = relationship("User", backref="admin_profile")


class CaseRequest(Base):
    __tablename__ = "lawyers_caserequest"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients_clientprofile.id"))
    lawyer_id: Mapped[int] = mapped_column(ForeignKey("lawyers_lawyerprofile.id"))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    response_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_stage: Mapped[str] = mapped_column(String(30))
    documents_submitted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    documents_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    workflow_stage_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    custom_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)


class CaseMessage(Base):
    __tablename__ = "lawyers_casemessage"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("lawyers_caserequest.id"))
    sender_type: Mapped[str] = mapped_column(String(10))
    sender_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts_baseuser.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    attachment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class CaseDocument(Base):
    __tablename__ = "lawyers_casedocument"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_request_id: Mapped[int] = mapped_column(ForeignKey("lawyers_caserequest.id"))
    document_type: Mapped[str] = mapped_column(String(20))
    document_file: Mapped[str] = mapped_column(String(100))
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

class CaseDocumentVerification(Base):
    __tablename__ = "lawyers_casedocumentverification"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("lawyers_casedocument.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts_baseuser.id"), nullable=True)

    document = relationship("CaseDocument", backref="verification")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_request_id: Mapped[int] = mapped_column(ForeignKey("lawyers_caserequest.id"))
    amount: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    case_request: Mapped["CaseRequest"] = relationship("CaseRequest", backref="payments")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id"))
    case_request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lawyers_caserequest.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(Text)
    remind_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user: Mapped["User"] = relationship("User", backref="reminders")
    case_request: Mapped[Optional["CaseRequest"]] = relationship("CaseRequest", backref="reminders")


class DeleteAccountToken(Base):
    __tablename__ = "accounts_deleteaccounttoken"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_baseuser.id"))

    user: Mapped["User"] = relationship("User")


class LawyerRating(Base):
    __tablename__ = "lawyers_lawyerrating"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    review_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients_clientprofile.id"))
    lawyer_id: Mapped[int] = mapped_column(ForeignKey("lawyers_lawyerprofile.id"))


class LawyerProfileUpdateRequest(Base):
    __tablename__ = "lawyers_lawyerprofileupdaterequest"
    id: Mapped[int] = mapped_column(primary_key=True)
    lawyer_id: Mapped[int] = mapped_column(ForeignKey("lawyers_lawyerprofile.id", ondelete="CASCADE"))
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    date_of_birth: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    years_of_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consultation_fee: Mapped[Optional[float]] = mapped_column(DECIMAL, nullable=True)
    office_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mobile_number: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    alternate_mobile_number: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


