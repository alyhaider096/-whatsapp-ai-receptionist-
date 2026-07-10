from sqlalchemy import select

from app.core.security import encrypt_secret
from app.models.enums import MessageDirection
from app.models.llm_config import LLMConfig
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.usage_log import UsageLog
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_text_payload


async def test_webhook_dedup(db_session, unique_phone, monkeypatch, worker_ctx):
    """CLAUDE.md required test: same wa_message_id twice -> one job, one reply."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return ["We're open 9am-5pm, Monday to Saturday."]

    async def fake_generate_reply(**kwargs):
        return "We're open 9am-5pm, Monday to Saturday!"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    phone_number_id = "109876543210987"
    whatsapp_config = WhatsAppConfig(
        tenant_id=tenant.id,
        waba_id="waba-1",
        phone_number_id=phone_number_id,
        access_token_encrypted=encrypt_secret("test-meta-token"),
    )
    llm_config = LLMConfig(
        tenant_id=tenant.id,
        api_key_encrypted=encrypt_secret("sk-test"),
        model="openai/gpt-4o-mini",
    )
    db_session.add_all([whatsapp_config, llm_config])
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.duplicate-test-1",
        from_number=unique_phone,
        text_body="What are your timings?",
    )

    event1 = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event1)
    await db_session.commit()
    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event1.id))

    # Meta redelivers the exact same message in a second webhook event.
    event2 = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event2)
    await db_session.commit()
    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event2.id))

    assert len(sent) == 1

    outbound = (
        await db_session.scalars(
            select(Message).where(Message.direction == MessageDirection.outbound)
        )
    ).all()
    assert len(outbound) == 1

    inbound = (
        await db_session.scalars(
            select(Message).where(Message.wa_message_id == "wamid.duplicate-test-1")
        )
    ).all()
    assert len(inbound) == 1


async def test_webhook_unknown_phone_records_failure(db_session, worker_ctx):
    payload = build_whatsapp_text_payload(
        phone_number_id="unknown-phone-id",
        wa_message_id="wamid.unknown-phone-1",
        from_number="15550009999",
        text_body="hey",
    )
    event = WebhookEvent(phone_number_id="unknown-phone-id", payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))
    await db_session.refresh(event)

    assert event.processed is True
    assert event.processed_at is not None
    assert event.tenant_id is None
    assert event.failure_reason == "unknown_phone_number_id"


async def test_webhook_send_failure_is_recorded(db_session, unique_phone, monkeypatch, worker_ctx):
    async def fake_send_text_message(**kwargs):
        raise RuntimeError("Meta token rejected")

    async def fake_retrieve_chunks(**kwargs):
        return ["We're open 9am-5pm, Monday to Saturday."]

    async def fake_generate_reply(**kwargs):
        return "We're open 9am-5pm, Monday to Saturday!"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    phone_number_id = "109876543210987"
    db_session.add_all(
        [
            WhatsAppConfig(
                tenant_id=tenant.id,
                waba_id="waba-1",
                phone_number_id=phone_number_id,
                access_token_encrypted=encrypt_secret("test-meta-token"),
            ),
            LLMConfig(
                tenant_id=tenant.id,
                api_key_encrypted=encrypt_secret("sk-test"),
                model="openai/gpt-4o-mini",
            ),
        ]
    )
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.send-failure-1",
        from_number=unique_phone,
        text_body="What are your timings?",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))
    await db_session.refresh(event)

    outbound = (
        await db_session.scalars(
            select(Message).where(Message.direction == MessageDirection.outbound)
        )
    ).all()
    assert outbound == []
    assert event.processed is True
    assert event.processed_at is not None
    assert event.tenant_id == tenant.id
    assert event.failure_reason == "whatsapp_send_failed"
    assert "RuntimeError: Meta token rejected" in event.send_error

    usage_logs = (await db_session.scalars(select(UsageLog))).all()
    assert usage_logs == []
