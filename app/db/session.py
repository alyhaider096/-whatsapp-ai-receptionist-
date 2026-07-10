from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# Behind a transaction-mode pooler (Supabase Supavisor, PgBouncer, etc.) a
# transaction can land on a different backend connection each time, so:
# - statement_cache_size=0 disables asyncpg's own prepared-statement cache
# - prepared_statement_name_func randomizes statement names (SQLAlchemy's
#   documented fix -- see asyncpg dialect docs, "Prepared Statement Name
#   with PGBouncer") so a leftover statement name from another session's
#   connection never collides with ours
# - NullPool avoids holding a connection open across transactions, since the
#   pooler -- not SQLAlchemy -- is the actual connection pool here
# ssl="require" only for non-local hosts: hosted providers reject
# unencrypted connections, but the local docker-compose Postgres has no SSL.
_is_local_db = "localhost" in settings.database_url or "127.0.0.1" in settings.database_url
_connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
}
if not _is_local_db:
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args=_connect_args,
)

async_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
