from datetime import datetime, timedelta, timezone

from app.core.security import encrypt_secret
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.services.conversations import is_within_service_window
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_text_payload


def test_24h_window_blocks_after_24_hours():
    """CLAUDE.md required test: reply blocked when last_inbound_at > 24h ago."""
    now = datetime.now(timezone.utc)
    stale = Conversation()
    stale.last_inbound_at = now - timedelta(hours=25)
    assert is_within_service_window(stale, now=now) is False


def test_24h_window_allows_within_24_hours():
    now = datetime.now(timezone.utc)
    fresh = Conversation()
    fresh.last_inbound_at = now - timedelta(hours=1)
    assert is_within_service_window(fresh, now=now) is True


def test_24h_window_blocks_when_never_messaged():
    conversation = Conversation()
    conversation.last_inbound_at = None
    assert is_within_service_window(conversation) is False


async def test_handoff_stops_ai(db_session, unique_phone, monkeypatch, worker_ctx):
    """CLAUDE.md required test: needs_human conversation gets no auto-reply."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fail_if_called(**kwargs):
        raise AssertionError("RAG must not run once a conversation needs a human")

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fail_if_called)

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
    db_session.add(whatsapp_config)

    contact = Contact(tenant_id=tenant.id, phone=unique_phone)
    db_session.add(contact)
    await db_session.flush()

    conversation = Conversation(
        tenant_id=tenant.id, contact_id=contact.id, status=ConversationStatus.needs_human
    )
    db_session.add(conversation)
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.handoff-test-1",
        from_number=unique_phone,
        text_body="Are you still there?",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert sent == []
