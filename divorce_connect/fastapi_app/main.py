from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .database import engine
from .models import Base
from .broker import broker
from .api import auth, notifs, lawyer, admin
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
        
    if not page_path.endswith(".html"):
        template_name = f"{page_path}.html"
    else:
        template_name = page_path
        
    try:
        return templates.TemplateResponse(request, template_name)
    except jinja2.exceptions.TemplateNotFound:
        raise HTTPException(status_code=404, detail="Page not found")
