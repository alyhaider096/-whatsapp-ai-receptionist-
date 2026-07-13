from sqlalchemy import select

from app.core.security import encrypt_secret
from app.models.enums import MessageDirection
from app.models.llm_config import LLMConfig
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_text_payload


async def _seed_tenant(db_session, phone_number_id: str):
    tenant = Tenant(name="Dr. Amjad Eye Clinic")
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
        ]
    )
    await db_session.commit()
    return tenant


async def test_clearly_off_topic_question_gets_direct_decline_not_handoff(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    """A question entirely outside the business's domain (knee pain at an
    eye clinic) should get a direct honest answer, not an escalation to a
    human who can't help with it either."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return []

    async def fake_classify_and_reply_off_topic(**kwargs):
        assert "knee pain" in kwargs["user_message"].lower()
        return "That's outside what we handle here -- try an orthopedic specialist."

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "classify_and_reply_off_topic", fake_classify_and_reply_off_topic)

    phone_number_id = "109876543229001"
    await _seed_tenant(db_session, phone_number_id)

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.offtopic-1",
        from_number=unique_phone, text_body="I have knee pain, can you help?",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert "orthopedic" in sent[0]["body"]

    from app.models.handoff_event import HandoffEvent

    handoffs = (await db_session.scalars(select(HandoffEvent))).all()
    assert handoffs == []


async def test_plausibly_relevant_question_still_hands_off(db_session, unique_phone, monkeypatch, worker_ctx):
    """A question that could plausibly be answered by this business, just
    not documented, must still go to a human -- unlike the clearly
    off-topic case."""
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return []

    async def fake_classify_and_reply_off_topic(**kwargs):
        return None  # signals "plausibly relevant, hand off"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "classify_and_reply_off_topic", fake_classify_and_reply_off_topic)

    phone_number_id = "109876543229002"
    await _seed_tenant(db_session, phone_number_id)

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id, wa_message_id="wamid.offtopic-2",
        from_number=unique_phone, text_body="Do you accept insurance for cataract surgery?",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert "connecting you with a team member" in sent[0]["body"].lower()

    from app.models.handoff_event import HandoffEvent

    handoffs = (await db_session.scalars(select(HandoffEvent))).all()
    assert len(handoffs) == 1
    assert handoffs[0].reason == "no_reliable_answer"
