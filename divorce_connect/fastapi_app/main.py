from contextlib import asynccontextmanager
from types import SimpleNamespace
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query, status, Depends, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from jose import JWTError, jwt
from .security import SECRET_KEY, ALGORITHM

from .database import engine
from .models import Base
from .broker import broker
from .api import auth, notifs, lawyer, admin, admin_actions, client_actions, client_case_actions, payments, reminders, superuser
from .notifications import manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths for Templates and Static files (mapping to the existing Django paths)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIRS = [
    BASE_DIR / "templates",
    BASE_DIR / "templates" / "accounts",
    BASE_DIR / "templates" / "accounts" / "emails",
    BASE_DIR / "templates" / "clients",
    BASE_DIR / "templates" / "lawyers",
    BASE_DIR / "templates" / "adminpanel",
]
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"

templates = Jinja2Templates(directory=[str(d) for d in TEMPLATES_DIRS if d.exists()])

import re
import jinja2
from urllib.parse import quote

class DjangoToJinjaFileSystemLoader(jinja2.FileSystemLoader):
    def get_source(self, environment, template):
        contents, filename, uptodate = super().get_source(environment, template)
        # Double quotes
        contents = re.sub(r'\|([a-zA-Z_][a-zA-Z0-9_]*):"([^"]*)"', r'|\1("\2")', contents)
        # Single quotes
        contents = re.sub(r"\|([a-zA-Z_][a-zA-Z0-9_]*):'([^']*)'", r"|\1('\2')", contents)
        # No quotes (allow dots)
        contents = re.sub(r'\|([a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z0-9_\.-]+)', r'|\1(\2)', contents)
        # {% empty %}
        contents = re.sub(r'\{%\s*empty\s*%\}', r'{% else %}', contents)
        # {% widthratio ... %}
        contents = re.sub(
            r'\{%\s*widthratio\s+(\S+)\s+(\S+)\s+(\S+)\s*%\}',
            r'{{ ((\1 | float / \2 | float) * \3) | int }}',
            contents
        )
        # Django forloop variables to Jinja2 loop variables translation
        contents = re.sub(r'forloop\.counter0', r'loop.index0', contents)
        contents = re.sub(r'forloop\.counter', r'loop.index', contents)
        contents = re.sub(r'forloop\.first', r'loop.first', contents)
        contents = re.sub(r'forloop\.last', r'loop.last', contents)
        # Django-only tags that FastAPI/Jinja needs to understand
        contents = re.sub(r'\{\%\s*load\s+static\s*\%\}', '', contents)
        contents = re.sub(r'\{\%\s*static\s+(["\'])(.*?)\1\s*\%\}', r"{{ url_for('static', path='\2') }}", contents)
        contents = re.sub(r'\{\%\s*csrf_token\s*\%\}', r'{{ csrf_token }}', contents)
        return contents, filename, uptodate

templates.env.loader = DjangoToJinjaFileSystemLoader([str(d) for d in TEMPLATES_DIRS if d.exists()])

def jinja_date_filter(value, format_str=""):
    if not value:
        return ""
    import datetime
    if isinstance(value, str):
        return value
    if not isinstance(value, (datetime.date, datetime.datetime)):
        return str(value)
    django_to_python = {
        "d M, Y · H:i": "%d %b, %Y · %H:%M",
        "d M, Y": "%d %b, %Y",
        "M d, Y": "%b %d, %Y",
        "F d, Y": "%B %d, %Y",
        "Y-m-d": "%Y-%m-%d",
    }
    fmt = django_to_python.get(format_str, "%b %d, %Y")
    return value.strftime(fmt)

def jinja_floatformat_filter(value, decimal_places=0):
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimal_places}f}"
    except:
        return str(value)

def jinja_pluralize_filter(value, suffix="s"):
    try:
        count = int(value)
        return "" if count == 1 else suffix
    except:
        return suffix

templates.env.filters['date'] = jinja_date_filter
templates.env.filters['floatformat'] = jinja_floatformat_filter
templates.env.filters['pluralize'] = jinja_pluralize_filter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Event: Connect to NATS via Taskiq broker
    logger.info("Starting up FastAPI application...")
    
    # In a real production setup with Alembic, you would not create tables here.
    # But for scaffolding, we'll create the tables synchronously or via async engine.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    if not broker.is_worker_process:
        logger.info("Connecting to NATS broker...")
        await broker.startup()
        
    yield
    
    # Shutdown Event: Disconnect from NATS
    logger.info("Shutting down FastAPI application...")
    if not broker.is_worker_process:
        logger.info("Disconnecting from NATS broker...")
        await broker.shutdown()
        
app = FastAPI(
    title="DivorceConnect Complete Async Architecture",
    description="Modern Async API and Frontend replacement via FastAPI + NATS + Taskiq",
    version="2.0.0",
    lifespan=lifespan,
    debug=True
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static and Media files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Include API Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(notifs.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(lawyer.router, prefix="/api/lawyer", tags=["Lawyer"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(admin_actions.router, prefix="/api/admin", tags=["Admin Actions"])
app.include_router(client_actions.router, prefix="/api/client", tags=["Client Actions"])
app.include_router(client_case_actions.router, prefix="/api/client", tags=["Client Case Actions"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(reminders.router, prefix="/api/reminders", tags=["Reminders"])
app.include_router(superuser.router, prefix="/api/superuser", tags=["Superuser"])

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket, 
    user_id: int, 
    token: str | None = Query(None)
):
    if not token:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if not email or token_type != "access":
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive, listen for messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

# --- Fallback Server-side Logout ---
from fastapi.responses import HTMLResponse, RedirectResponse
@app.get("/logout")
@app.get("/logout/")
async def logout_page(request: Request):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logging out...</title>
        <script>
            localStorage.removeItem("access_token");
            window.location.href = "/login/";
        </script>
    </head>
    <body>
        <p>Logging you out, please wait...</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/superuser_login/", tags=["Frontend"])
@app.get("/superuser_login", tags=["Frontend"])
async def superuser_login_page(request: Request):
    """
    Renders the dedicated Superuser Login page.
    """
    return templates.TemplateResponse(request, "superuser_login.html")


# --- Frontend Template Routes ---
from fastapi import HTTPException
import jinja2

@app.get("/superuser_dashboard/", tags=["Frontend"])
@app.get("/superuser_dashboard", tags=["Frontend"])
async def superuser_dashboard_page(request: Request):
    """
    Renders the native FastAPI Superuser Panel.
    Auth is handled client-side via JWT (localStorage token).
    The API routes at /api/superuser/* enforce is_superuser=True.
    """
    return templates.TemplateResponse(request, "superuser_dashboard.html")


@app.get("/", tags=["Frontend"])
async def landing_page(request: Request):
    """
    Renders the main landing page.
    """
    return templates.TemplateResponse(request, "index.html")

@app.api_route("/{page_path:path}", methods=["GET", "POST"], tags=["Frontend"])
async def dynamic_page(request: Request, page_path: str):
    """
    Catch-all router to automatically render any HTML template by its URL path.
    For example, /login/ -> login.html
    /client_dashboard/ -> client_dashboard.html
    """
    # Remove trailing slash if present for easier handling
    if page_path.endswith("/"):
        page_path = page_path[:-1]

    if "adminpanel/reports" in page_path:
        parts = page_path.strip("/").split("/")
        report_id = int(parts[-1])
        
        from sqlalchemy import select
        from .database import AsyncSessionLocal
        from .models import TrustReport, User, ClientProfile, LawyerProfile, Notification
        
        async with AsyncSessionLocal() as db:
            report_res = await db.execute(select(TrustReport).where(TrustReport.id == report_id))
            report = report_res.scalar_one_or_none()
            if not report:
                raise HTTPException(status_code=404, detail="Trust report not found")
                
            reporter_res = await db.execute(select(User).where(User.id == report.reporter_id))
            reporter_user = reporter_res.scalar_one_or_none()
            
            reported_client = None
            if report.reported_client_id:
                client_res = await db.execute(select(ClientProfile).where(ClientProfile.id == report.reported_client_id))
                reported_client = client_res.scalar_one_or_none()
                if reported_client:
                    cl_user_res = await db.execute(select(User).where(User.id == reported_client.user_id))
                    reported_client.user = cl_user_res.scalar_one_or_none()
                
            reported_lawyer = None
            if report.reported_lawyer_id:
                lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == report.reported_lawyer_id))
                reported_lawyer = lawyer_res.scalar_one_or_none()
                if reported_lawyer:
                    lw_user_res = await db.execute(select(User).where(User.id == reported_lawyer.user_id))
                    reported_lawyer.user = lw_user_res.scalar_one_or_none()

            if request.method == "POST":
                form = await request.form()
                action = form.get("action")
                notes = (form.get("admin_notes") or "").strip()
                
                report.admin_notes = notes
                
                if action == "approve":
                    report.status = "APPROVED"
                elif action == "warn":
                    report.status = "WARNED"
                elif action == "ban":
                    report.status = "BANNED"
                    if reported_client:
                        reported_client.is_deleted = True
                        db.add(reported_client)
                    if reported_lawyer:
                        reported_lawyer.is_deleted = True
                        db.add(reported_lawyer)
                elif action == "reject":
                    report.status = "REJECTED"
                    
                db.add(report)
                await db.commit()
                return RedirectResponse(url="/admin_dashboard/", status_code=303)
                
            # Attach for Django-style template queries
            report.reporter = reporter_user
            report.reported_client = reported_client
            report.reported_lawyer = reported_lawyer
            report.formatted_id = f"ri::{report.id:05d}"
            
            context = {
                "request": request,
                "report": report
            }
            template_name = "trust_report_detail.html"
            return templates.TemplateResponse(request, template_name, context)

    if "adminpanel/lawyer/update-request" in page_path:
        parts = page_path.strip("/").split("/")
        req_id = int(parts[-1])
        
        from sqlalchemy import select
        from .database import AsyncSessionLocal
        from .models import LawyerProfile, LawyerProfileUpdateRequest, User
        
        async with AsyncSessionLocal() as db:
            update_req_res = await db.execute(select(LawyerProfileUpdateRequest).where(LawyerProfileUpdateRequest.id == req_id))
            update_request = update_req_res.scalar_one_or_none()
            if not update_request:
                raise HTTPException(status_code=404, detail="Update request not found")
                
            lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.id == update_request.lawyer_id))
            lawyer = lawyer_res.scalar_one_or_none()
            if not lawyer:
                raise HTTPException(status_code=404, detail="Lawyer profile not found")

            if request.method == "POST":
                form = await request.form()
                action = form.get("action")
                notes = form.get("notes") or ""
                rejection_reason = form.get("rejection_reason") or ""
                
                if action == "approve":
                    if update_request.full_name:
                        lawyer.full_name = update_request.full_name
                    if update_request.gender:
                        lawyer.gender = update_request.gender
                    if update_request.date_of_birth:
                        lawyer.date_of_birth = update_request.date_of_birth
                    if update_request.bar_registration_number:
                        lawyer.bar_registration_number = update_request.bar_registration_number
                    if update_request.state_bar_council:
                        lawyer.state_bar_council = update_request.state_bar_council
                    if update_request.years_of_experience is not None:
                        lawyer.years_of_experience = update_request.years_of_experience
                    if update_request.specialization:
                        lawyer.specialization = update_request.specialization
                    if update_request.bio:
                        lawyer.bio = update_request.bio
                    if update_request.consultation_fee is not None:
                        lawyer.consultation_fee = update_request.consultation_fee
                    if update_request.office_city:
                        lawyer.office_city = update_request.office_city
                    if update_request.mobile_number:
                        lawyer.mobile_number = update_request.mobile_number
                    if update_request.alternate_mobile_number:
                        lawyer.alternate_mobile_number = update_request.alternate_mobile_number
                    if update_request.profile_picture:
                        lawyer.profile_picture = update_request.profile_picture
                        
                    db.add(lawyer)
                    update_request.status = "APPROVED"
                    update_request.admin_notes = notes
                    db.add(update_request)
                    await db.commit()
                    
                    try:
                        from .notifications import create_and_broadcast_notification
                        await create_and_broadcast_notification(
                            db=db,
                            user_id=lawyer.user_id,
                            title="Profile Update Approved",
                            message="Your lawyer profile update request has been approved and applied.",
                            url="/lawyer_profile/"
                        )
                    except Exception:
                        pass
                        
                    return RedirectResponse(url="/admin_dashboard/", status_code=303)
                    
                elif action == "reject":
                    update_request.status = "REJECTED"
                    update_request.admin_notes = notes or rejection_reason
                    db.add(update_request)
                    await db.commit()
                    
                    try:
                        from .notifications import create_and_broadcast_notification
                        await create_and_broadcast_notification(
                            db=db,
                            user_id=lawyer.user_id,
                            title="Profile Update Rejected",
                            message=f"Your profile update request was rejected. Reason: {notes or rejection_reason}",
                            url="/lawyer_profile_edit/"
                        )
                    except Exception:
                        pass
                        
                    return RedirectResponse(url="/admin_dashboard/", status_code=303)
            
            class SimpleUser:
                email = ""
            user_res = await db.execute(select(User).where(User.id == lawyer.user_id))
            user_obj = user_res.scalar_one_or_none() or SimpleUser()
            context = {
                "request": request,
                "lawyer": lawyer,
                "update_request": update_request,
                "user_obj": user_obj
            }

        template_name = "lawyer_update_request_detail.html"
        return templates.TemplateResponse(request, template_name, context)

    if page_path in ["forgot-password", "forgot_password"]:
        if request.method == "POST":
            form = await request.form()
            email = (form.get("email") or "").strip().lower()
            if not email:
                return RedirectResponse(url="/forgot-password/?error=missing-email", status_code=303)

            from sqlalchemy import select
            from .database import AsyncSessionLocal
            from .models import User
            from .api.auth import generate_otp_for_user

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
                if not user:
                    return RedirectResponse(url="/forgot-password/?error=not-found", status_code=303)

                await generate_otp_for_user(user.id, db)

            return RedirectResponse(url=f"/verify-otp/?email={quote(email)}&purpose=password_reset", status_code=303)

        template_name = "forgot_password.html"
    elif page_path in ["reset-password", "reset_password"]:
        if request.method == "POST":
            form = await request.form()
            email = (form.get("email") or request.query_params.get("email", "") or "").strip().lower()
            new_password = (form.get("new_password") or "").strip()
            confirm_password = (form.get("confirm_password") or "").strip()
            if not email or not new_password or not confirm_password:
                return RedirectResponse(url=f"/reset-password/?email={quote(email)}&error=missing-fields", status_code=303)
            if new_password != confirm_password:
                return RedirectResponse(url=f"/reset-password/?email={quote(email)}&error=match", status_code=303)

            from sqlalchemy import select
            from .database import AsyncSessionLocal
            from .models import User
            from .security import pwd_context

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
                if user:
                    user.password = pwd_context.hash(new_password)
                    db.add(user)
                    await db.commit()

            return RedirectResponse(url="/login/?reset=success", status_code=303)
        template_name = "reset_password.html"
    
    # Map the client profile paths to the actual template file name
    elif page_path in ["verify-otp", "verify_otp"]:
        template_name = "verify_otp.html"
    elif page_path in ["verify-register-otp", "verify_register_otp"]:
        template_name = "verify_register_otp.html"
    elif page_path in ["client_profile", "profile/edit"]:
        template_name = "edit_profile_client.html"
    elif page_path in ["lawyer_profile", "lawyers/profile"]:
        template_name = "lawyers/profile_lawyer.html"
    elif page_path in ["delete-account", "api/auth/delete-account"]:
        template_name = "request_delete_account.html"
    elif page_path in ["lawyer_earnings", "earnings"]:
        template_name = "earning_dashboard.html"
    elif page_path in ["lawyer_case_orders", "case-orders"]:
        template_name = "case_order.html"
    elif page_path in ["lawyer_case_detail", "lawyer-case-detail"]:
        query_str = f"?{request.query_params}" if request.query_params else ""
        return RedirectResponse(url=f"/client_case_detail/{query_str}", status_code=307)
    elif page_path in ["lawyer_case_status", "case-status"]:
        template_name = "case_status.html"
    elif page_path in ["lawyer_settings", "settings"]:
        template_name = "account_settings.html"
    elif page_path in ["lawyer_billing", "billing"]:
        template_name = "billing_payment.html"
    elif page_path in ["lawyer_profile_edit", "profile/edit", "lawyers/profile/edit"]:
        template_name = "lawyer_profile_edit.html"
    elif page_path in ["lawyer_support", "support"]:
        template_name = "support_lawyer.html"
    elif page_path in ["lawyer_report_client", "report-client"]:
        template_name = "report_client.html"
    elif page_path in ["admin_pending_cases", "pending-cases"]:
        template_name = "pending_cases_list.html"
    elif page_path in ["case_documents_verification_list", "case-documents-verification", "adminpanel/documents/verify"]:
        template_name = "case_documents_verification_list.html"
    elif page_path in ["admin_profile", "admin-profile"]:
        template_name = "profile_admin.html"
    elif page_path in ["admin_profile_edit", "admin-profile-edit"]:
        template_name = "admin_profile_edit.html"
    elif not page_path.endswith(".html"):
        template_name = f"{page_path}.html"
    else:
        template_name = page_path
        
    try:
        context = {"request": request, "email": request.query_params.get("email", "")}
        if template_name == "case_order.html":
            from .database import AsyncSessionLocal
            from sqlalchemy import select
            from .models import User, LawyerProfile, CaseRequest, ClientProfile
            from .security import get_current_user
            from fastapi import Depends

            token = request.headers.get("authorization", "")
            if token.startswith("Bearer "):
                token_value = token.split(" ", 1)[1]
                from jose import jwt
                try:
                    payload = jwt.decode(token_value, SECRET_KEY, algorithms=[ALGORITHM])
                    email = payload.get("sub")
                    if email:
                        async with AsyncSessionLocal() as db:
                            user_result = await db.execute(select(User).where(User.email == email))
                            user = user_result.scalar_one_or_none()
                            if user:
                                lawyer_result = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
                                lawyer_profile = lawyer_result.scalar_one_or_none()
                                if lawyer_profile and lawyer_profile.verified and lawyer_profile.is_profile_complete:
                                    requests_result = await db.execute(
                                        select(CaseRequest)
                                        .where(CaseRequest.lawyer_id == lawyer_profile.id, CaseRequest.status == 'PENDING')
                                        .order_by(CaseRequest.created_at.desc())
                                    )
                                    pending_requests = []
                                    for case_request in requests_result.scalars().all():
                                        client_result = await db.execute(select(ClientProfile).where(ClientProfile.id == case_request.client_id))
                                        client_profile = client_result.scalar_one_or_none()
                                        client_name = f"{client_profile.first_name} {client_profile.last_name}".strip() if client_profile else f"Client #{case_request.client_id}"
                                        display_name = SimpleNamespace(get_full_name=lambda name=client_name: name)
                                        status_label = {
                                            'PENDING': 'Pending',
                                            'DOCUMENTS_PENDING': 'Waiting for Documents',
                                            'DOCUMENTS_SUBMITTED': 'Documents Submitted',
                                            'DOCUMENTS_VERIFIED': 'Documents Verified',
                                            'ACCEPTED': 'Accepted',
                                            'COMPLETED': 'Completed',
                                            'REJECTED': 'Rejected',
                                        }.get(case_request.status, case_request.status)

                                        request_view = SimpleNamespace(
                                            id=case_request.id,
                                            message=case_request.message,
                                            created_at=case_request.created_at,
                                            status=case_request.status,
                                            client=display_name,
                                            get_status_display=lambda status_label=status_label: status_label,
                                        )
                                        pending_requests.append(request_view)
                                    context["pending_requests"] = pending_requests
                except Exception:
                    pass

        if template_name == "edit_profile_client.html":
            class DummyUser:
                email = ""
            class DummyProfile:
                id = None
                first_name = ""
                last_name = ""
                gender = ""
                marital_status = ""
                mobile_number = ""
                alternate_mobile_number = ""
                address = ""
                pincode = ""
                date_of_birth = None
                profile_picture = None
                user = DummyUser()
        if "profile" not in context:
            class DummyUser:
                email = ""
            class DummyProfile:
                full_name = ""
                gender = ""
                date_of_birth = None
                bar_registration_number = ""
                state_bar_council = ""
                years_of_experience = 0
                specialization = ""
                rating = 0.0
                rating_count = 0
                rating_total = 0
                verified = False
                is_profile_complete = False
                mobile_number = ""
                alternate_mobile_number = ""
                profile_picture = None
                bio = ""
                consultation_fee = 0.0
                office_city = ""
                custom_id = ""
                get_specialization_display = lambda self=None: ""
                get_gender_display = lambda self=None: ""
                user = DummyUser()
            context["profile"] = DummyProfile()
            context["user"] = DummyUser()
            
        return templates.TemplateResponse(request, template_name, context)
    except jinja2.exceptions.TemplateNotFound:
        raise HTTPException(status_code=404, detail="Page not found")
