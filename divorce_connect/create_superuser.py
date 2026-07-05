"""
create_superuser.py - DivorceConnect India

Standalone async CLI to create or promote a superuser in PostgreSQL.
Run from inside divorce_connect/ directory:

    python create_superuser.py

Requires DATABASE_URL in the .env file.
"""
import asyncio
import getpass
import os
import sys
import io
from pathlib import Path

# Force UTF-8 output so Windows console doesn't choke on box-drawing chars
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load .env
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except ImportError:
    pass  # read from environment directly


def normalize_for_asyncpg(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


async def create_superuser() -> None:
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set. Add it to your .env file.")
        sys.exit(1)

    DATABASE_URL = normalize_for_asyncpg(DATABASE_URL)

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.future import select
    from passlib.context import CryptContext

    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    pwd_context = CryptContext(
        schemes=["django_pbkdf2_sha256", "bcrypt"], deprecated="auto"
    )

    db_host = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "connected"

    print("")
    print("=" * 52)
    print("  DivorceConnect India  --  Create Superuser")
    print("=" * 52)
    print(f"  DB : {db_host}")
    print("")

    email = input("  Email address : ").strip().lower()
    if not email:
        print("ERROR: Email cannot be empty.")
        sys.exit(1)

    first_name = input("  First name    : ").strip()
    last_name  = input("  Last name     : ").strip()

    try:
        password = getpass.getpass("  Password      : ")
    except Exception:
        password = input("  Password      : ").strip()

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    try:
        password_confirm = getpass.getpass("  Confirm pass  : ")
    except Exception:
        password_confirm = input("  Confirm pass  : ").strip()

    if password != password_confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)

    hashed = pwd_context.hash(password)

    try:
        from fastapi_app.models import User
    except ImportError:
        from divorce_connect.fastapi_app.models import User

    import datetime

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_superuser = True
            existing.is_staff     = True
            existing.is_active    = True
            existing.role         = "admin"
            if first_name:
                existing.first_name = first_name
            if last_name:
                existing.last_name = last_name
            existing.password = hashed
            await db.commit()
            print("")
            print(f"  OK  Existing user '{email}' promoted to superuser.")
        else:
            now = datetime.datetime.utcnow()
            new_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=email,
                password=hashed,
                role="admin",
                is_active=True,
                is_staff=True,
                is_superuser=True,
                date_joined=now,
                created_at=now,
                updated_at=now,
            )
            db.add(new_user)
            await db.commit()
            print("")
            print(f"  OK  Superuser '{email}' created successfully.")

    print("")
    print("  Login at  : /superuser_login/")
    print("  Dashboard : /superuser_dashboard/")
    print("=" * 52)
    print("")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_superuser())
