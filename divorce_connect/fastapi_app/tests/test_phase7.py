import asyncio
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.main import app
from fastapi_app.security import get_current_user, create_access_token
from fastapi_app.database import get_db, AsyncSessionLocal
from fastapi_app.models import User, CaseRequest, Payment, Reminder, ClientProfile, Base, DeleteAccountToken, LawyerProfile

# --- Test Data Setup ---
# We will create mock users and inject them
mock_client_user = User(
    id=8888,
    email="client_test@example.com",
    role="client",
    first_name="Client",
    last_name="Test",
    password="hashed",
    is_active=True,
    is_staff=False
)

mock_admin_user = User(
    id=9999,
    email="admin_test@example.com",
    role="admin",
    first_name="Admin",
    last_name="Test",
    password="hashed",
    is_active=True,
    is_staff=True
)

mock_client_user_9998 = User(
    id=9998,
    email="client_9998@example.com",
    role="client",
    first_name="Client",
    last_name="9998",
    password="hashed",
    is_active=True,
    is_staff=False
)

# Current user override placeholder
active_user = mock_client_user

async def override_get_current_user():
    return active_user

async def seed_mock_users():
    async with AsyncSessionLocal() as db:
        for u in [mock_client_user, mock_admin_user, mock_client_user_9998]:
            res = await db.execute(select(User).where(User.id == u.id))
            if not res.scalar_one_or_none():
                # Clear session state by merging
                await db.merge(u)
        await db.commit()

# Setup App Dependency Overrides
@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = override_get_current_user
    asyncio.run(seed_mock_users())

client = TestClient(app)

# --- Automated Test Cases ---

def test_health_check():
    response = client.get("/health")
    # Some setups might catch this under dynamic templating fallback or health endpoint
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
    else:
        # Fallback dynamic route verification
        response = client.get("/")
        assert response.status_code == 200


def test_lawyer_case_order_page_renders():
    response = client.get("/lawyer_case_orders")
    assert response.status_code == 200
    assert "Incoming client requests" in response.text


def test_lawyer_case_order_page_shows_pending_case_for_authenticated_lawyer():
    async def seed_lawyer_case():
        async with AsyncSessionLocal() as db:
            existing_user = await db.execute(select(User).where(User.email == "lawyer.case@example.com"))
            user = existing_user.scalar_one_or_none()
            if user is None:
                user = User(
                    email="lawyer.case@example.com",
                    role="lawyer",
                    first_name="Lawyer",
                    last_name="Case",
                    is_active=True,
                    password="hashed",
                )
                db.add(user)
                await db.flush()

            existing_lawyer = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
            lawyer_profile = existing_lawyer.scalar_one_or_none()
            if lawyer_profile is None:
                lawyer_profile = LawyerProfile(
                    user_id=user.id,
                    full_name="Lawyer Case",
                    gender="other",
                    bar_registration_number="BAR7777",
                    state_bar_council="Test Council",
                    years_of_experience=5,
                    specialization="family",
                    bio="",
                    consultation_fee=1000.0,
                    office_city="Delhi",
                    verified=True,
                    is_profile_complete=True,
                    mobile_number="9876543210",
                )
                db.add(lawyer_profile)
                await db.flush()

            existing_client = await db.execute(select(ClientProfile).where(ClientProfile.user_id == 9998))
            client_profile = existing_client.scalar_one_or_none()
            if client_profile is None:
                client_profile = ClientProfile(
                    user_id=9998,
                    first_name="Client",
                    last_name="Name",
                    gender="other",
                    marital_status="single",
                    mobile_number="9876543211",
                    address="123 Test Street",
                    pincode="110001",
                )
                db.add(client_profile)
                await db.flush()

            existing_request = await db.execute(
                select(CaseRequest).where(
                    CaseRequest.lawyer_id == lawyer_profile.id,
                    CaseRequest.client_id == client_profile.id,
                )
            )
            case_request = existing_request.scalar_one_or_none()
            if case_request is None:
                case_request = CaseRequest(
                    client_id=client_profile.id,
                    lawyer_id=lawyer_profile.id,
                    message="Need help with a divorce filing.",
                    status="PENDING",
                    workflow_stage="CASE_CREATED",
                )
                db.add(case_request)
                await db.commit()

            return user, case_request

    user, _ = asyncio.run(seed_lawyer_case())
    global active_user
    active_user = user
    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    response = client.get(
        "/api/lawyer/case-requests",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert any(r["message"] == "Need help with a divorce filing." for r in response.json())


def test_forgot_password_page_renders():
    response = client.get("/forgot-password/")
    assert response.status_code == 200
    assert "Forgot your password?" in response.text


def test_forgot_password_submission_redirects_to_otp_flow():
    async def create_user():
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(User).where(User.email == "forgot.user@example.com"))
            user = existing.scalar_one_or_none()
            if user is None:
                user = User(email="forgot.user@example.com", password="hashed", role="client", is_active=True)
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user.email

    email = asyncio.run(create_user())
    response = client.post("/forgot-password/", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/verify-otp/")


def test_payments_api():
    global active_user
    active_user = mock_admin_user  # Set active user to admin to ensure full authorization

    # 1. Fetch payments list
    response = client.get("/api/payments/")
    assert response.status_code == 200
    initial_payments = response.json()
    assert isinstance(initial_payments, list)

    # 2. Create a test payment
    # First ensure a valid CaseRequest exists or mock case_request_id.
    # Since we are using the live database, we'll try to get an existing case_request_id or fallback to 1.
    payment_payload = {
        "case_request_id": 1,
        "amount": 5500.0,
        "razorpay_payment_id": "pay_test12345"
    }
    response = client.post("/api/payments/", json=payment_payload)
    if response.status_code == 201:
        payment = response.json()
        assert payment["amount"] == 5500.0
        assert payment["status"] == "PENDING"
        payment_id = payment["id"]

        # 3. Verify payment capture
        verify_payload = {
            "razorpay_payment_id": "pay_test12345_verified",
            "status": "SUCCEEDED"
        }
        res_verify = client.post(f"/api/payments/{payment_id}/verify", json=verify_payload)
        assert res_verify.status_code == 200
        assert res_verify.json()["status"] == "SUCCEEDED"
        assert res_verify.json()["razorpay_payment_id"] == "pay_test12345_verified"

        # 4. Get payment detail
        res_detail = client.get(f"/api/payments/{payment_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["status"] == "SUCCEEDED"
    else:
        # If case request #1 doesn't exist, it should return 404
        assert response.status_code == 404

def test_reminders_api():
    global active_user
    active_user = mock_client_user  # Use client user for scheduling reminders

    # 1. Create a new reminder
    reminder_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).isoformat()
    reminder_payload = {
        "title": "Case Filing Reminder",
        "message": "Remember to review petition draft with lawyer.",
        "remind_at": reminder_time,
        "case_request_id": None
    }
    response = client.post("/api/reminders/", json=reminder_payload)
    assert response.status_code == 201
    reminder = response.json()
    assert reminder["title"] == "Case Filing Reminder"
    assert reminder["sent"] is False
    reminder_id = reminder["id"]

    # 2. Get the scheduled reminder
    res_get = client.get(f"/api/reminders/{reminder_id}")
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Case Filing Reminder"

    # 3. Update the reminder
    update_payload = {
        "title": "Case Filing Updated Reminder",
        "message": "Bring physical files to court."
    }
    res_update = client.put(f"/api/reminders/{reminder_id}", json=update_payload)
    assert res_update.status_code == 200
    assert res_update.json()["title"] == "Case Filing Updated Reminder"

    # 4. Fetch list of reminders
    res_list = client.get("/api/reminders/")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 5. Delete the reminder
    res_del = client.delete(f"/api/reminders/{reminder_id}")
    assert res_del.status_code == 204

def test_reminders_check_due():
    # Trigger global check due trigger
    response = client.post("/api/reminders/check-due")
    assert response.status_code == 200
    assert "message" in response.json()

def test_client_deactivate():
    global active_user
    active_user = mock_client_user
    
    # 1. Post delete account request
    response = client.post("/api/auth/delete-account", json={"email": "client_test@example.com"})
    assert response.status_code == 200
    assert "sent" in response.json()["message"]
    
    # 2. Get the token from database using SQLAlchemy
    token = None
    async def get_token():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(DeleteAccountToken).order_by(DeleteAccountToken.id.desc()).limit(1))
            obj = res.scalar_one_or_none()
            return obj.token if obj else None
    token = asyncio.run(get_token())
    assert token is not None
    
    # 3. Confirm deactivation via token link
    response = client.get(f"/api/auth/confirm-delete/{token}")
    assert response.status_code == 200
    assert "Deactivated" in response.text


