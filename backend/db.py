"""SQLAlchemy async engine + session for GestPro PostgreSQL backend."""
import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ["DATABASE_URL"]
# Render fournit « postgresql://… » : on force le pilote asyncpg et on retire « sslmode »,
# que asyncpg ne comprend pas (le SSL est géré par DB_SSL ci-dessous).
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL.split("://", 1)[1]
if "sslmode=" in DATABASE_URL:
    base, _, query = DATABASE_URL.partition("?")
    kept = [q for q in query.split("&") if q and not q.startswith("sslmode=")]
    DATABASE_URL = base + ("?" + "&".join(kept) if kept else "")

# Render Postgres requires SSL. asyncpg accepts ssl=ctx via connect_args.
# Set DB_SSL=false for a local PostgreSQL without SSL (development / tests).
_connect_args = {}
if os.environ.get("DB_SSL", "true").lower() not in ("0", "false", "no", "off"):
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args = {"ssl": _ssl_ctx}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
