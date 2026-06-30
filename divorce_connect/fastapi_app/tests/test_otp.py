import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from fastapi_app.main import app
from fastapi_app.database import get_db
from fastapi_app.models import User, OTPCode

client = TestClient(app)

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
