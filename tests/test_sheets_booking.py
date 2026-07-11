from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import encrypt_secret
from app.models.enums import MessageDirection
from app.models.llm_config import LLMConfig
from app.models.message import Message
from app.models.sheet_config import SheetConfig
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.services import sheets as sheets_module
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_text_payload


async def _seed_tenant_with_sheet(db_session, phone_number_id: str):
    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    db_session.add_all(
        [
            WhatsAppConfig(
                tenant_id=tenant.id, waba_id="waba-1", phone_number_id=phone_number_id,
                access_token_encrypted=encrypt_secret("test-meta-token"),
            ),
            LLMConfig(
                tenant_id=tenant.id, api_key_encrypted=encrypt_secret("sk-test"), model="openai/gpt-4o-mini"
            ),
            SheetConfig(tenant_id=tenant.id, spreadsheet_id="sheet-abc", sheet_name="Appointments"),
        ]
    )
    await db_session.commit()
    return tenant


async def test_propose_booking_stages_pending_action_without_writing(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    """A propose_booking tool call must stage a pending_action and must NOT
    call sheets.append_booking -- the write only happens after confirmation."""
    sent = []
    append_called = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_append_booking(**kwargs):
        append_called.append(kwargs)
        return "shouldnotcall"

    async def fake_generate_reply_with_tools(*, tools, tool_executor, **kwargs):
        # Simulate the LLM deciding to call propose_booking.
        result = await tool_executor(
            "propose_booking",
            {"name": "Ali Haider", "service": "LASIK consult", "date": "2026-08-01", "time": "2:00 PM"},
        )
        return f"Here's what I'd book: {result}"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(sheets_module, "append_booking", fake_append_booking)
    monkeypatch.setattr(jobs_module, "generate_reply_with_tools", fake_generate_reply_with_tools)

    phone_number_id = "109876543219001"
    await _seed_tenant_with_sheet(db_session, phone_number_id)

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.book-1",
        from_number=unique_phone, text_body="I want to book LASIK for Aug 1 2pm, name Ali Haider",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert append_called == []  # never actually wrote
    assert len(sent) == 1

    from app.models.conversation import Conversation
    from app.models.contact import Contact

    conversation = await db_session.scalar(
        select(Conversation).join(Contact).where(Contact.phone == unique_phone)
    )
    assert conversation.pending_action is not None
    assert conversation.pending_action["type"] == "create"
    assert conversation.pending_action["args"]["service"] == "LASIK consult"


async def test_confirming_pending_booking_writes_to_sheet(db_session, unique_phone, monkeypatch, worker_ctx):
    sent = []
    append_calls = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_append_booking(**kwargs):
        append_calls.append(kwargs)
        return "abc12345"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(sheets_module, "append_booking", fake_append_booking)

    phone_number_id = "109876543219002"
    tenant = await _seed_tenant_with_sheet(db_session, phone_number_id)

    from app.models.conversation import Conversation
    from app.models.contact import Contact

    contact = Contact(tenant_id=tenant.id, phone=unique_phone)
    db_session.add(contact)
    await db_session.flush()
    conversation = Conversation(
        tenant_id=tenant.id, contact_id=contact.id,
        last_inbound_at=datetime.now(timezone.utc),
        pending_action={
            "type": "create",
            "args": {
                "name": "Ali Haider", "phone": unique_phone, "service": "LASIK consult",
                "date": "2026-08-01", "time": "2:00 PM",
            },
            "proposed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db_session.add(conversation)
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.confirm-1",
        from_number=unique_phone, text_body="yes",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(append_calls) == 1
    assert append_calls[0]["service"] == "LASIK consult"
    assert len(sent) == 1
    assert "booked" in sent[0]["body"].lower()

    await db_session.refresh(conversation)
    assert conversation.pending_action is None


async def test_declining_pending_booking_does_not_write(db_session, unique_phone, monkeypatch, worker_ctx):
    sent = []
    append_calls = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_append_booking(**kwargs):
        append_calls.append(kwargs)
        return "shouldnotcall"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(sheets_module, "append_booking", fake_append_booking)

    phone_number_id = "109876543219003"
    tenant = await _seed_tenant_with_sheet(db_session, phone_number_id)

    from app.models.conversation import Conversation
    from app.models.contact import Contact

    contact = Contact(tenant_id=tenant.id, phone=unique_phone)
    db_session.add(contact)
    await db_session.flush()
    conversation = Conversation(
        tenant_id=tenant.id, contact_id=contact.id,
        last_inbound_at=datetime.now(timezone.utc),
        pending_action={
            "type": "create",
            "args": {"name": "Ali", "phone": unique_phone, "service": "X", "date": "2026-08-01", "time": "2pm"},
            "proposed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db_session.add(conversation)
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.decline-1",
        from_number=unique_phone, text_body="no",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert append_calls == []
    assert len(sent) == 1
    assert "not booked" in sent[0]["body"].lower()

    await db_session.refresh(conversation)
    assert conversation.pending_action is None


async def test_stale_pending_action_falls_through_to_normal_pipeline(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    """A pending_action older than the TTL must be cleared and NOT treated
    as an answer -- the message should go through the normal RAG pipeline."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return ["We are open 9-5."]

    async def fake_generate_reply(**kwargs):
        return "We are open 9am-5pm!"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    phone_number_id = "109876543219004"
    tenant = await _seed_tenant_with_sheet(db_session, phone_number_id)

    from app.models.conversation import Conversation
    from app.models.contact import Contact

    contact = Contact(tenant_id=tenant.id, phone=unique_phone)
    db_session.add(contact)
    await db_session.flush()
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    conversation = Conversation(
        tenant_id=tenant.id, contact_id=contact.id,
        last_inbound_at=datetime.now(timezone.utc),
        pending_action={
            "type": "create",
            "args": {"name": "Ali", "phone": unique_phone, "service": "X", "date": "2026-08-01", "time": "2pm"},
            "proposed_at": stale_time.isoformat(),
        },
    )
    db_session.add(conversation)
    await db_session.commit()

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.stale-1",
        from_number=unique_phone, text_body="what are your timings?",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    await db_session.refresh(conversation)
    assert conversation.pending_action is None
    assert len(sent) == 1
    assert sent[0]["body"] == "We are open 9am-5pm!"


async def test_no_chunks_does_not_handoff_when_sheet_configured(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    """With a Sheet connected, an empty RAG match must not trigger the hard
    handoff -- the tool-enabled model gets a chance to handle it instead."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return []

    async def fake_generate_reply_with_tools(**kwargs):
        return "Sure, let me check availability for you."

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply_with_tools", fake_generate_reply_with_tools)

    phone_number_id = "109876543219005"
    await _seed_tenant_with_sheet(db_session, phone_number_id)

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.avail-1",
        from_number=unique_phone, text_body="do you have a slot Friday morning",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert sent[0]["body"] == "Sure, let me check availability for you."

    from app.models.handoff_event import HandoffEvent

    handoffs = (await db_session.scalars(select(HandoffEvent))).all()
    assert handoffs == []
