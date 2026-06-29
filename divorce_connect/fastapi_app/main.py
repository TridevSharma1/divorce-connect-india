from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .database import engine
from .models import Base
from .broker import broker
from .api import auth, notifs, lawyer, admin, admin_actions, client_actions, client_case_actions, payments, reminders
from .notifications import manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths for Templates and Static files (mapping to the existing Django paths)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIRS = [
    BASE_DIR / "templates",
    BASE_DIR / "clients" / "templates",
    BASE_DIR / "lawyers" / "templates",
    BASE_DIR / "adminpanel" / "templates",
    BASE_DIR / "accounts" / "templates",
]
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"

templates = Jinja2Templates(directory=[str(d) for d in TEMPLATES_DIRS if d.exists()])

import re
import jinja2
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

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive, listen for messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

# --- Fallback Server-side Logout ---
from fastapi.responses import HTMLResponse
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

# --- Frontend Template Routes ---
from fastapi import HTTPException
import jinja2

@app.get("/", tags=["Frontend"])
async def landing_page(request: Request):
    """
    Renders the main landing page.
    """
    return templates.TemplateResponse(request, "index.html")

@app.get("/{page_path:path}", tags=["Frontend"])
async def dynamic_page(request: Request, page_path: str):
    """
    Catch-all router to automatically render any HTML template by its URL path.
    For example, /login/ -> login.html
    /client_dashboard/ -> client_dashboard.html
    """
    # Remove trailing slash if present for easier handling
    if page_path.endswith("/"):
        page_path = page_path[:-1]
        
    # Map the client profile paths to the actual template file name
    if page_path in ["client_profile", "profile/edit"]:
        template_name = "edit_profile_client.html"
    elif page_path in ["delete-account", "api/auth/delete-account"]:
        template_name = "request_delete_account.html"
    elif page_path in ["lawyer_earnings", "earnings"]:
        template_name = "earning_dashboard.html"
    elif page_path in ["lawyer_case_orders", "case-orders"]:
        template_name = "case_order.html"
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
    elif page_path in ["case_documents_verification_list", "case-documents-verification"]:
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
        context = {"request": request}
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
            context["profile"] = DummyProfile()
            
        return templates.TemplateResponse(request, template_name, context)
    except jinja2.exceptions.TemplateNotFound:
        raise HTTPException(status_code=404, detail="Page not found")
