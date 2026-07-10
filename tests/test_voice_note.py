from sqlalchemy import select

from app.core.security import encrypt_secret
from app.models.enums import MessageDirection
from app.models.llm_config import LLMConfig
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.worker import jobs as jobs_module
from tests.conftest import build_whatsapp_audio_payload


async def _seed_tenant(db_session, phone_number_id: str):
    tenant = Tenant(name="Test Clinic")
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
    db_session.add(
        LLMConfig(
            tenant_id=tenant.id,
            api_key_encrypted=encrypt_secret("sk-test"),
            model="openai/gpt-4o-mini",
        )
    )
    await db_session.commit()
    return tenant


async def test_voice_note_transcribed_and_answered(db_session, unique_phone, monkeypatch, worker_ctx):
    """A transcribed voice note flows through the exact same RAG pipeline as
    a typed message -- the inbound Message.text should be the transcript."""
    sent = []

    async def fake_get_media_url(*, media_id, access_token):
        return "https://graph.facebook.com/fake-media-url"

    async def fake_download_media(*, media_url, access_token):
        return b"fake-audio-bytes"

    async def fake_transcribe_audio(**kwargs):
        return "What are your clinic timings?"

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fake_retrieve_chunks(**kwargs):
        return ["We're open 9am-5pm, Monday to Saturday."]

    async def fake_generate_reply(**kwargs):
        return "We're open 9am-5pm, Monday to Saturday!"

    monkeypatch.setattr(jobs_module.meta, "get_media_url", fake_get_media_url)
    monkeypatch.setattr(jobs_module.meta, "download_media", fake_download_media)
    monkeypatch.setattr(jobs_module, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr(jobs_module, "generate_reply", fake_generate_reply)

    phone_number_id = "109876543210987"
    await _seed_tenant(db_session, phone_number_id)

    payload = build_whatsapp_audio_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.voice-test-1",
        from_number=unique_phone,
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1

    inbound = await db_session.scalar(
        select(Message).where(
            Message.wa_message_id == "wamid.voice-test-1",
            Message.direction == MessageDirection.inbound,
        )
    )
    assert inbound.text == "What are your clinic timings?"
    assert inbound.audio_url == "https://graph.facebook.com/fake-media-url"


async def test_voice_note_transcription_failure_falls_back(
    db_session, unique_phone, monkeypatch, worker_ctx
):
    """If transcription fails (bad audio, API error), the customer gets the
    friendly fallback reply -- not a crash, and RAG never runs on garbage."""
    sent = []

    async def fake_get_media_url(*, media_id, access_token):
        return "https://graph.facebook.com/fake-media-url"

    async def fake_download_media(*, media_url, access_token):
        return b"fake-audio-bytes"

    async def failing_transcribe_audio(**kwargs):
        raise RuntimeError("Whisper rejected this audio format")

    async def fake_send_text_message(**kwargs):
        sent.append(kwargs)
        return {"messages": [{"id": "wamid.reply"}]}

    async def fail_if_called(**kwargs):
        raise AssertionError("RAG must not run when transcription failed")

    monkeypatch.setattr(jobs_module.meta, "get_media_url", fake_get_media_url)
    monkeypatch.setattr(jobs_module.meta, "download_media", fake_download_media)
    monkeypatch.setattr(jobs_module, "transcribe_audio", failing_transcribe_audio)
    monkeypatch.setattr(jobs_module.meta, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(jobs_module.rag, "retrieve_chunks", fail_if_called)

    phone_number_id = "109876543210988"
    await _seed_tenant(db_session, phone_number_id)

    payload = build_whatsapp_audio_payload(
        phone_number_id=phone_number_id,
        wa_message_id="wamid.voice-test-2",
        from_number=unique_phone,
    )
    event = WebhookEvent(phone_number_id=phone_number_id, payload=payload)
    db_session.add(event)
    await db_session.commit()

    await jobs_module.process_whatsapp_webhook(worker_ctx, str(event.id))

    assert len(sent) == 1
    assert "not fully sure" in sent[0]["body"]
