"""
Render pre-start script: create all database tables synchronously.
Run this BEFORE starting gunicorn so tables exist when the first request hits.

Usage (in Procfile start command):
    python create_tables.py && gunicorn ...
"""
import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("create_tables")


def main():
    # ── Resolve DATABASE_URL ──────────────────────────────────────────────────
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        logger.warning("DATABASE_URL is not set – falling back to SQLite.")
        raw_url = "sqlite+aiosqlite:///./db.sqlite3"

    # Normalise to async driver
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgresql://") and "+asyncpg" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    logger.info(f"Target database: {raw_url[:40]}...")

    # ── Create all tables ─────────────────────────────────────────────────────
    from sqlalchemy.ext.asyncio import create_async_engine
    from fastapi_app.models import Base

    async def _create():
        engine = create_async_engine(raw_url, echo=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅  All database tables created / verified.")
        except Exception as exc:
            logger.error(f"❌  Failed to create tables: {exc}")
            sys.exit(1)
        finally:
            await engine.dispose()

    asyncio.run(_create())


if __name__ == "__main__":
    main()
