import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, unquote
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Pointing to the original Django database
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


def ensure_sqlite_schema_compatibility(url: str | None = None) -> None:
    """Backfill missing columns on the legacy SQLite database used by FastAPI auth."""
    if url is None:
        url = DATABASE_URL

    if not url.startswith("sqlite"):
        return

    parsed = urlparse(url)
    db_path = unquote(parsed.path)
    is_relative_sqlite_path = url.startswith(("sqlite:///", "sqlite+aiosqlite:///")) and not url.startswith(("sqlite:////", "sqlite+aiosqlite:////"))
    if is_relative_sqlite_path:
        db_path = db_path.lstrip("/")
        db_file = (Path.cwd() / db_path).resolve()
    else:
        db_file = Path(db_path).resolve() if db_path.startswith("/") else (Path.cwd() / db_path).resolve()

    if not db_file.exists():
        return

    conn = sqlite3.connect(db_file)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info('accounts_baseuser')")]
        if "role" not in columns:
            conn.execute("ALTER TABLE accounts_baseuser ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'client'")
        if "razorpay_customer_id" not in columns:
            conn.execute("ALTER TABLE accounts_baseuser ADD COLUMN razorpay_customer_id VARCHAR(50)")
        conn.commit()
    finally:
        conn.close()


ensure_sqlite_schema_compatibility()


async def get_db():
    """Dependency for providing database session to endpoints."""
    async with AsyncSessionLocal() as session:
        yield session
