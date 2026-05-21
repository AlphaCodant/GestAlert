"""Pool PostgreSQL asyncpg — pattern GESTREB."""
import os
import ssl
import asyncpg
from dotenv import load_dotenv

load_dotenv()

_pool: asyncpg.Pool | None = None
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            port=int(os.getenv("DB_PORT", "5432")),
            password=os.getenv("DB_PWD"),
            database=os.getenv("DB_NAME"),
            ssl=_ssl_ctx,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_db():
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection
