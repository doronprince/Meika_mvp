from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# A hosted Postgres allows far fewer connections than a local one, and
# asyncpg wants an `ssl` flag rather than libpq's sslmode (stripped in
# app/core/config.py).
_connect_args: dict = {"ssl": True} if settings.database_requires_tls else {}

# A pooled host (Neon's `-pooler`, Supabase's pgbouncer port, and friends)
# runs PgBouncer in transaction mode, which cannot carry asyncpg's prepared
# statements between statements — left on, queries fail intermittently with
# "prepared statement _pg_N does not exist". Both caches go off for pooled
# hosts only, so a direct connection keeps the faster path.
if "-pooler" in settings.sqlalchemy_database_url or "pgbouncer=true" in settings.sqlalchemy_database_url:
    _connect_args["statement_cache_size"] = 0
    _connect_args["prepared_statement_cache_size"] = 0

engine = create_async_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
