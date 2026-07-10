from app.core.security import encrypt_secret
from app.models.enums import MessageDirection
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_text_payload
from sqlalchemy import select


async def _seed_tenant_with_greeting(db_session, phone_number_id: str, *, menu_options=None):
    tenant = Tenant(
        name="Test Clinic",
        settings={
            "agent": {
                "greeting_message": "Hi! Welcome to Test Clinic.",
                "greeting_menu_options": menu_options or [],
            }
        },
    )
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        WhatsAppConfig(
            tenant_id=tenant.id,
            waba_id="waba-1",
            phone_number_id=phone_number_id,
            access_token_encrypted=encrypt_secret("test-meta-token"),
        )
    )
    await db_session.commit()
    return tenant


async def test_first_message_gets_plain_greeting(db_session, unique_phone, monkeypatch, worker_ctx):
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fail_if_called(**kwargs):
        raise AssertionError("RAG must not run on the first-contact greeting turn")

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fail_if_called)

    phone_number_id = "109876543210987"
    await _seed_tenant_with_greeting(db_session, phone_number_id)

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.greeting-1",
        from_number=unique_phone,
        text_body="hi",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert sent[0]["body"] == "Hi! Welcome to Test Clinic."


async def test_first_message_gets_interactive_menu(db_session, unique_phone, monkeypatch, worker_ctx):
    sent = []

    async def fake_send_interactive_list_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fail_if_called(**kwargs):
        raise AssertionError("RAG must not run on the first-contact greeting turn")

    monkeypatch.setattr(
        jobs_module.meta, "send_interactive_list_message", fake_send_interactive_list_message
    )
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fail_if_called)

    phone_number_id = "109876543210988"
    await _seed_tenant_with_greeting(
        db_session,
        phone_number_id,
        menu_options=[
            {"title": "Book an appointment", "description": "Schedule a visit"},
            {"title": "Ask a question", "description": ""},
        ],
    )

    payload = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.greeting-2",
        from_number=unique_phone,
        text_body="hello",
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert sent[0]["body"] == "Hi! Welcome to Test Clinic."
    assert [o["title"] for o in sent[0]["options"]] == ["Book an appointment", "Ask a question"]

    outbound = (
        await db_session.scalars(select(Message).where(Message.direction == MessageDirection.outbound))
    ).all()
    assert len(outbound) == 1
    assert outbound[0].text == "Hi! Welcome to Test Clinic."


async def test_second_message_skips_greeting(db_session, unique_phone, monkeypatch, worker_ctx):
    sent_text = []

    async def fake_send_text_message(**kwargs):
        sent_text.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return ["We're open 9am-5pm."]

    async def fake_generate_reply(**kwargs):
        return "We're open 9am-5pm!"

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    phone_number_id = "109876543210989"
    tenant = await _seed_tenant_with_greeting(db_session, phone_number_id)
    # LLM config needed for the second (non-greeting) turn to run the RAG pipeline.
    from app.models.llm_config import LLMConfig

    db_session.add(
        LLMConfig(tenant_id=tenant.id, api_key_encrypted=encrypt_secret("sk-test"), model="openai/gpt-4o-mini")
    )
    await db_session.commit()

    first = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.greeting-3a",
        from_number=unique_phone,
        text_body="hi",
    )
    event1 = WebhookEvent(phone_number_id=phone_number_id, payload=first)
    db_session.add(event1)
    await db_session.commit()
    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event1.id))
    assert len(sent_text) == 1
    assert sent_text[0]["body"] == "Hi! Welcome to Test Clinic."

    second = build_whatsapp_text_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.greeting-3b",
        from_number=unique_phone,
        text_body="what are your timings?",
    )
    event2 = WebhookEvent(phone_number_id=phone_number_id, payload=second)
    db_session.add(event2)
    await db_session.commit()
    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event2.id))

    assert len(sent_text) == 2
    assert sent_text[1]["body"] == "We're open 9am-5pm!"


async def test_interactive_list_reply_flows_through_normal_pipeline(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    sent = []

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    captured_queries = []

    async def fake_retrieve_chunks(**kwargs):
        captured_queries.append(kwargs["query"])
        return ["We take walk-ins and appointments."]

    async def fake_generate_reply(**kwargs):
        return "Sure, here's how appointments work."

    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    phone_number_id = "109876543210990"
    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    from app.models.llm_config import LLMConfig

    db_session.add_all(
        [
            WhatsAppConfig(
                tenant_id=tenant.id,
                waba_id="waba-1",
                phone_number_id=phone_number_id,
                access_token_encrypted=encrypt_secret("test-meta-token"),
            ),
            LLMConfig(
                tenant_id=tenant.id, api_key_encrypted=encrypt_secret("sk-test"), model="openai/gpt-4o-mini"
            ),
        ]
    )
    await db_session.commit()

    payload = {
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
                            "contacts": [{"profile": {"name": "Test Customer"}, "wa_id": unique_phone}],
                            "messages": [
                                {
                                    "from": unique_phone,
                                    "id": "wamid.interactive-1",
                                    "timestamp": "1720000000",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {
                                            "id": "greeting_option_0",
                                            "title": "Book an appointment",
                                            "description": "Schedule a visit",
                                        },
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert captured_queries == ["Book an appointment"]
    assert len(sent) == 1
    assert sent[0]["body"] == "Sure, here's how appointments work."

    inbound = await db_session.scalar(
        select(Message).where(Message.wa_message_id == "wamid.interactive-1")
    )
    assert inbound.text == "Book an appointment"
