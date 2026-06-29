import os

models_path = r'd:\Software Setup\C\Django_Projects\PROJECT99\divorce-connect-india\divorce_connect\fastapi_app\models.py'
with open(models_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix imports
if 'Integer' not in content:
    content = content.replace('from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text', 'from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, Float, DECIMAL, Date')

append_str = '''
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

class CaseDocument(Base):
    __tablename__ = "lawyers_casedocument"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_request_id: Mapped[int] = mapped_column(ForeignKey("lawyers_caserequest.id"))
    document_type: Mapped[str] = mapped_column(String(20))
    document_file: Mapped[str] = mapped_column(String(100))
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
'''

if 'ClientProfile' not in content:
    with open(models_path, 'w', encoding='utf-8') as f:
        f.write(content + append_str)
    print("Models appended.")
else:
    print("Models already exist.")
