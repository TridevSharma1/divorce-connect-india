import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# ─── Load environment variables first (permanent solution) ───────────────────
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# ─── Alembic Config object ────────────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ─── Ensure project root is on sys.path so models can be imported ─────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

# ─── Import Base metadata from FastAPI models ─────────────────────────────────
from divorce_connect.fastapi_app.models import Base
target_metadata = Base.metadata


# ─── Permanent DATABASE_URL resolver ─────────────────────────────────────────
def _alembic_sync_url(url: str) -> str:
    """
    Alembic uses a synchronous engine (psycopg2/sqlite3), so we must strip
    any async driver prefix that FastAPI's database.py adds at runtime.
    This normaliser is the single source of truth for Alembic's connection.
    """
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Define it in your .env file or as an environment variable."
        )
    # Heroku/Render legacy prefix
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # FastAPI async prefix → strip to sync
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("sqlite+aiosqlite:///"):
        url = url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    return url


# Environment always wins; alembic.ini sqlalchemy.url is the documented fallback
_raw_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
url = _alembic_sync_url(_raw_url)


# ─── Migration runners ────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a live synchronous connection."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = url          # Override ini value with resolved URL
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
