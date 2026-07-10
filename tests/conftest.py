import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  registers all tables on Base.metadata
from app.db.base import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://receptionist:receptionist@localhost:5432/receptionist_test",
)


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine, monkeypatch):
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    import app.worker.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "async_session_maker", session_maker)
    async with session_maker() as session:
        yield session

    # Worker/router code commits internally, so a plain rollback isn't
    # enough -- truncate everything between tests instead.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


def build_whatsapp_text_payload(
    *, phone_number_id: str, wa_message_id: str, from_number: str, text_body: str
) -> dict:
    """Shape matches a real captured Meta webhook delivery, not the doc
    examples: entry[0].changes[0].value.messages[0] (CLAUDE.md convention)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001111",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Test Customer"}, "wa_id": from_number}
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wa_message_id,
                                    "timestamp": "1720000000",
                                    "text": {"body": text_body},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def build_whatsapp_audio_payload(
    *, phone_number_id: str, wa_message_id: str, from_number: str, audio_id: str = "audio-id-1"
) -> dict:
    """Shape matches a real captured Meta voice-note delivery."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001111",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Test Customer"}, "wa_id": from_number}
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wa_message_id,
                                    "timestamp": "1720000000",
                                    "audio": {"id": audio_id, "mime_type": "audio/ogg; codecs=opus"},
                                    "type": "audio",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def unique_phone() -> str:
    return f"1555{uuid.uuid4().int % 10_000_000:07d}"


class FakeRedis:
    """Minimal in-memory stand-in for arq's ctx["redis"] -- just enough of
    the redis API for the debounce buffer/generation-counter logic in
    app/worker/jobs.py. enqueue_job runs the target job function inline
    instead of actually deferring it, so tests don't need to sleep through
    DEBOUNCE_SECONDS: with one message per webhook event (the common test
    shape), "run the debounced job immediately" and "run it after the quiet
    window" produce the same observable result."""

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._lists: dict[str, list[bytes]] = {}
        self._counters: dict[str, int] = {}

    async def rpush(self, key, value) -> None:
        self._lists.setdefault(key, []).append(str(value).encode())

    async def expire(self, key, seconds) -> None:
        return None

    async def incr(self, key) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def get(self, key):
        if key in self._counters:
            return str(self._counters[key]).encode()
        return None

    async def lrange(self, key, start, end):
        return list(self._lists.get(key, []))

    async def delete(self, *keys) -> None:
        for key in keys:
            self._lists.pop(key, None)
            self._counters.pop(key, None)

    async def enqueue_job(self, function_name, *args, **kwargs):
        # Discard arq's own scheduling kwargs (_defer_by etc.) -- the real
        # job function signature never sees them.
        import app.worker.jobs as jobs_module

        func = getattr(jobs_module, function_name)
        await func(self._ctx, *args)


@pytest.fixture
def worker_ctx() -> dict:
    ctx: dict = {}
    ctx["redis"] = FakeRedis(ctx)
    return ctx
