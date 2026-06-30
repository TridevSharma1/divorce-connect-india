import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from fastapi_app.main import app
from fastapi_app.database import get_db
from fastapi_app.models import User, OTPCode, LawyerProfile

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_otp_registration_and_login_flow():
    # Use random email to avoid duplicate entries
    import random
    test_email = f"otp_test_{random.randint(10000, 99999)}@example.com"
    password = "SuperSecurePassword123"
    
    # 1. Register User (Step 1)
    reg_payload = {
        "email": test_email,
        "password": password,
        "first_name": "OTP",
        "last_name": "Tester",
        "role": "client"
    }
    
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 201
    reg_data = response.json()
    assert reg_data["message"] == "Registration successful, OTP sent"
    assert reg_data["email"] == test_email
    assert reg_data["redirect"] == "/verify-register-otp/"
    
    # Fetch the OTP from the database directly since it was created
    async for db in get_db():
        user_res = await db.execute(select(User).where(User.email == test_email))
        user = user_res.scalar_one_or_none()
        assert user is not None
        assert user.is_active is False  # Inactive initially
        
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == user.id, OTPCode.is_used == False))
        otp_obj = otp_res.scalars().first()
        assert otp_obj is not None
        code = otp_obj.code
        break
        
    # 2. Verify Registration OTP (Step 2)
    verify_payload = {
        "email": test_email,
        "otp": code
    }
    response = client.post("/api/auth/verify-register-otp", json=verify_payload)
    assert response.status_code == 200
    verify_data = response.json()
    assert "access_token" in verify_data
    assert verify_data["token_type"] == "bearer"
    assert verify_data["role"] == "client"
    
    # Assert user is now active in DB
    async for db in get_db():
        user_res = await db.execute(select(User).where(User.email == test_email))
        user = user_res.scalar_one_or_none()
        assert user.is_active is True
        
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == user.id, OTPCode.code == code))
        otp_obj = otp_res.scalars().first()
        assert otp_obj.is_used is True
        break

    # 3. Login User (Step 1)
    login_form = {
        "username": test_email,
        "password": password
    }
    response = client.post("/api/auth/token", data=login_form)
    assert response.status_code == 200
    login_data = response.json()
    assert login_data["message"] == "OTP sent"
    assert login_data["email"] == test_email
    assert login_data["redirect"] == "/verify-otp/"
    
    # Fetch login OTP from DB
    async for db in get_db():
        user_res = await db.execute(select(User).where(User.email == test_email))
        user = user_res.scalar_one_or_none()
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == user.id, OTPCode.is_used == False))
        otp_obj = otp_res.scalars().first()
        login_code = otp_obj.code
        break
        
    # 4. Verify Login OTP (Step 2)
    verify_payload = {
        "email": test_email,
        "otp": login_code
    }
    response = client.post("/api/auth/verify-otp", json=verify_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

def test_otp_templates_rendering():
    response = client.get("/verify-otp/")
    assert response.status_code == 200
    assert "Check Your Email" in response.text
    
    response = client.get("/verify-register-otp/")
    assert response.status_code == 200
    assert "Verify Your Email" in response.text

@pytest.mark.anyio
async def test_admin_profile_verification_check():
    import random
    test_email = f"admin_test_{random.randint(10000, 99999)}@example.com"
    password = "SuperSecurePassword123"
    
    # 1. Register Admin User
    reg_payload = {
        "email": test_email,
        "password": password,
        "first_name": "Admin",
        "last_name": "Tester",
        "role": "admin"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 201
    
    # Get OTP
    async for db in get_db():
        user_res = await db.execute(select(User).where(User.email == test_email))
        user = user_res.scalar_one_or_none()
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == user.id, OTPCode.is_used == False))
        otp_obj = otp_res.scalars().first()
        code = otp_obj.code
        break
        
    # Verify OTP to activate admin
    verify_payload = {"email": test_email, "otp": code}
    response = client.post("/api/auth/verify-register-otp", json=verify_payload)
    assert response.status_code == 200
    token_data = response.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Try to access restricted routes (should return 403 because unverified)
    response = client.get("/api/admin/lawyers/pending", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin account not verified by superuser"
    
    # 3. Submit Admin Profile (this triggers notification)
    profile_data = {
        "full_name": "Admin Tester",
        "gender": "male",
        "date_of_birth": "1990-01-01",
        "mobile_number": "9876543210"
    }
    response = client.post("/api/admin/profile", data=profile_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Admin profile updated successfully"
    
    # Check that a notification was created for the admin user
    from fastapi_app.models import Notification
    async for db in get_db():
        notif_res = await db.execute(select(Notification).where(Notification.user_id == user.id))
        notifs = notif_res.scalars().all()
        assert len(notifs) > 0
        assert any(n.title == "Profile Verification Pending" for n in notifs)
        break

@pytest.mark.anyio
async def test_lawyer_profile_verification_check():
    import random
    test_email = f"lawyer_test_{random.randint(10000, 99999)}@example.com"
    admin_email = f"admin_test_{random.randint(10000, 99999)}@example.com"
    password = "SuperSecurePassword123"
    
    # 1. Register and verify Admin User
    admin_reg = {
        "email": admin_email,
        "password": password,
        "first_name": "Admin",
        "last_name": "Tester",
        "role": "admin"
    }
    response = client.post("/api/auth/register", json=admin_reg)
    assert response.status_code == 201
    
    # Get Admin OTP
    async for db in get_db():
        admin_user_res = await db.execute(select(User).where(User.email == admin_email))
        admin_user = admin_user_res.scalar_one_or_none()
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == admin_user.id, OTPCode.is_used == False))
        otp_obj = otp_res.scalars().first()
        admin_otp = otp_obj.code
        break
        
    response = client.post("/api/auth/verify-register-otp", json={"email": admin_email, "otp": admin_otp})
    assert response.status_code == 200
    admin_token = response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Fill admin profile to make them verified
    admin_profile_data = {
        "full_name": "Admin User",
        "gender": "male",
        "date_of_birth": "1990-01-01",
        "mobile_number": "9876543210"
    }
    response = client.post("/api/admin/profile", data=admin_profile_data, headers=admin_headers)
    assert response.status_code == 200
    
    # Manually approve admin user by setting is_verified_by_superuser = True
    async for db in get_db():
        from fastapi_app.models import AdminPanelProfile
        ap_res = await db.execute(select(AdminPanelProfile).where(AdminPanelProfile.user_id == admin_user.id))
        ap = ap_res.scalar_one_or_none()
        ap.is_verified_by_superuser = True
        await db.commit()
        break
        
    # Check Admin Dashboard pending count
    response = client.get("/api/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    stats = response.json()["stats"]
    initial_pending = stats["pending_count"]

    # 2. Register Lawyer User
    reg_payload = {
        "email": test_email,
        "password": password,
        "first_name": "Lawyer",
        "last_name": "Tester",
        "role": "lawyer"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 201
    
    # Get Lawyer OTP
    async for db in get_db():
        user_res = await db.execute(select(User).where(User.email == test_email))
        user = user_res.scalar_one_or_none()
        otp_res = await db.execute(select(OTPCode).where(OTPCode.user_id == user.id, OTPCode.is_used == False))
        otp_obj = otp_res.scalars().first()
        code = otp_obj.code
        break
        
    # Verify OTP to activate lawyer
    verify_payload = {"email": test_email, "otp": code}
    response = client.post("/api/auth/verify-register-otp", json=verify_payload)
    assert response.status_code == 200
    token_data = response.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check Admin Dashboard pending count (should STILL be initial_pending because lawyer hasn't filled profile details yet)
    response = client.get("/api/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["pending_count"] == initial_pending
    
    # Try to access lawyer restricted routes (should return 403 because unverified)
    response = client.get("/api/lawyer/earnings", headers=headers)
    assert response.status_code == 403
    
    # 3. Submit Lawyer Profile
    lawyer_profile_data = {
        "full_name": "Lawyer Tester",
        "gender": "male",
        "date_of_birth": "1985-05-05",
        "bar_registration_number": f"BAR-{random.randint(10000, 99999)}",
        "state_bar_council": "Delhi Bar Council",
        "years_of_experience": 10,
        "specialization": "divorce",
        "consultation_fee": 1500.0,
        "office_city": "Delhi",
        "bio": "Expert divorce lawyer with 10 years of experience.",
        "mobile_number": "9999999999"
    }
    response = client.post("/api/lawyer/profile", data=lawyer_profile_data, headers=headers)
    assert response.status_code == 200
    
    # 4. Check Admin Dashboard pending count (should now be initial_pending + 1 because profile is completed!)
    response = client.get("/api/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["pending_count"] == initial_pending + 1
    
    # Check that a pending verification notification was created for the admin user
    from fastapi_app.models import Notification
    async for db in get_db():
        notif_res = await db.execute(select(Notification).where(Notification.user_id == admin_user.id))
        notifs = notif_res.scalars().all()
        assert len(notifs) > 0
        assert any(n.title == "Lawyer Verification Pending" for n in notifs)
        break

    # Get lawyer profile ID
    async for db in get_db():
        lawyer_profile_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
        lawyer_p = lawyer_profile_res.scalar_one_or_none()
        lawyer_profile_id = lawyer_p.id
        break

    # Approve lawyer via Admin verify endpoint
    response = client.post(f"/api/admin/lawyers/{lawyer_profile_id}/verify?action=approve", headers=admin_headers)
    assert response.status_code == 200

    # Verify that the lawyer received the 'Account Approved' notification
    async for db in get_db():
        notif_res = await db.execute(select(Notification).where(Notification.user_id == user.id))
        notifs = notif_res.scalars().all()
        assert len(notifs) > 0
        assert any(n.title == "Account Approved" for n in notifs)
        break
