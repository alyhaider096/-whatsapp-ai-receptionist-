"""ARQ job(s) that process inbound WhatsApp webhook deliveries. Kept
idempotent throughout: re-running the same webhook_event_id (or a duplicate
wa_message_id landing twice) must never send a second reply."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.db.session import async_session_maker
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, LeadStatus, MessageDirection, MessageType, UserRole
from app.models.handoff_event import HandoffEvent
from app.models.lead import Lead
from app.models.llm_config import LLMConfig
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.usage_log import UsageLog
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.services import meta, notifications, rag
from app.services.agent_settings import DEFAULT_HANDOFF_MESSAGE, get_agent_settings
from app.services.conversations import (
    detect_handoff_trigger,
    get_or_create_contact,
    get_or_create_conversation,
    is_within_service_window,
)
from app.services.llm import generate_reply, transcribe_audio

logger = logging.getLogger(__name__)

UNSUPPORTED_TYPE_REPLY = (
    "I'm not fully sure I understood that. Can you please type your question, "
    "or wait while I connect you with a person?"
)
MAX_DIAGNOSTIC_LENGTH = 1000

# A customer typing "I need an" then "appointment" then "for tomorrow" as three
# separate WhatsApp messages should get ONE reply to the whole thought, not
# three replies to each fragment. We buffer inbound text in Redis and defer
# the actual reply generation until DEBOUNCE_SECONDS of silence on that
# conversation -- see _buffer_and_schedule_reply / process_debounced_reply.
DEBOUNCE_SECONDS = 8
DEBOUNCE_KEY_TTL = 120


async def process_whatsapp_webhook(ctx, webhook_event_id: str) -> None:
    async with async_session_maker() as db:
        event = await db.get(WebhookEvent, uuid.UUID(webhook_event_id))
        if event is None or event.processed:
            return

        try:
            value = event.payload["entry"][0]["changes"][0]["value"]
        except (KeyError, IndexError, TypeError):
            _mark_event_processed(event, failure_reason="malformed_payload")
            await db.commit()
            return

        phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
        messages = value.get("messages") or []
        if not messages:
            # Status callbacks (delivered/read/failed) -- nothing to reply to.
            _mark_event_processed(event, failure_reason="no_inbound_message")
            await db.commit()
            return

        whatsapp_config = await db.scalar(
            select(WhatsAppConfig).where(WhatsAppConfig.phone_number_id == phone_number_id)
        )
        if whatsapp_config is None:
            logger.warning("No tenant configured for phone_number_id=%s", phone_number_id)
            _mark_event_processed(event, failure_reason="unknown_phone_number_id")
            await db.commit()
            return

        event.tenant_id = whatsapp_config.tenant_id
        tenant = await db.get(Tenant, whatsapp_config.tenant_id)
        access_token = decrypt_secret(whatsapp_config.access_token_encrypted)

        try:
            for raw_message in messages:
                await _handle_message(
                    ctx=ctx,
                    db=db,
                    tenant=tenant,
                    whatsapp_config=whatsapp_config,
                    access_token=access_token,
                    raw_message=raw_message,
                    webhook_event=event,
                )
        except Exception as exc:
            logger.exception("Webhook worker failed for event=%s", event.id)
            await db.rollback()
            event = await db.get(WebhookEvent, uuid.UUID(webhook_event_id))
            if event is not None:
                _mark_event_processed(
                    event,
                    failure_reason="worker_exception",
                    error_message=_safe_error_message(exc),
                )
                await db.commit()
            return

        _mark_event_processed(event)
        await db.commit()


async def _handle_message(
    *, ctx, db, tenant: Tenant, whatsapp_config, access_token, raw_message, webhook_event
) -> None:
    tenant_id = tenant.id
    wa_message_id = raw_message.get("id")
    from_number = raw_message.get("from")
    msg_type = raw_message.get("type", "text")

    if wa_message_id:
        existing = await db.scalar(
            select(Message.id).where(Message.wa_message_id == wa_message_id)
        )
        if existing is not None:
            webhook_event.failure_reason = webhook_event.failure_reason or "duplicate_message"
            return  # Meta retried a delivery we already processed.

    settings = get_settings()
    llm_config = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))
    llm_api_key = decrypt_secret(llm_config.api_key_encrypted) if llm_config else None

    # text stays None for anything we couldn't turn into a reply-able string
    # (unsupported type, no LLM key configured yet, or transcription failure)
    # -- that's the signal below to fall back instead of running the RAG pipeline.
    audio_url: str | None = None
    if msg_type == "text":
        text = raw_message.get("text", {}).get("body", "")
    elif msg_type == "audio" and llm_api_key is not None:
        text, audio_url = await _transcribe_voice_note(
            raw_message=raw_message,
            access_token=access_token,
            transcription_model=settings.default_transcription_model,
            api_key=llm_api_key,
        )
    elif msg_type == "interactive":
        # A tapped list/button reply -- treat the option's title as the
        # customer's message so it flows through the same RAG/handoff
        # pipeline as if they'd typed it.
        text = _extract_interactive_reply_text(raw_message)
    else:
        text = None

    contact = await get_or_create_contact(db=db, tenant_id=tenant_id, phone=from_number)
    conversation = await get_or_create_conversation(
        db=db, tenant_id=tenant_id, contact_id=contact.id
    )
    conversation.last_inbound_at = datetime.now(timezone.utc)

    inbound = Message(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        wa_message_id=wa_message_id,
        direction=MessageDirection.inbound,
        type=MessageType(msg_type) if msg_type in MessageType.__members__ else MessageType.text,
        text=text if text is not None else f"[{msg_type} message -- could not process]",
        audio_url=audio_url,
    )
    db.add(inbound)
    try:
        await db.flush()
    except IntegrityError:
        # Race: a second delivery of the same wa_message_id landed first.
        await db.rollback()
        webhook_event.failure_reason = webhook_event.failure_reason or "duplicate_message"
        return

    await _ensure_lead(db=db, tenant_id=tenant_id, contact_id=contact.id)

    # Handoff is sacred: once a conversation needs a human, never auto-reply
    # again, regardless of what arrives afterward (CLAUDE.md rule 6).
    if conversation.status in (ConversationStatus.needs_human, ConversationStatus.human):
        await db.commit()
        return

    agent_settings = get_agent_settings(tenant.settings)
    if agent_settings["greeting_message"]:
        message_count = await db.scalar(
            select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
        )
        if message_count == 1:
            # First-ever message from this contact -- a fixed welcome (+
            # optional tappable menu) takes priority over both the RAG
            # pipeline and the unsupported-type fallback below. Whatever
            # they actually said is already stored as `inbound` and becomes
            # chat history for their next turn.
            await _send_greeting(
                db=db, tenant_id=tenant_id, conversation=conversation,
                whatsapp_config=whatsapp_config, access_token=access_token,
                to=from_number, agent_settings=agent_settings, webhook_event=webhook_event,
            )
            return

    if text is None:
        await _send_reply(
            db=db, tenant_id=tenant_id, conversation=conversation,
            whatsapp_config=whatsapp_config, access_token=access_token,
            to=from_number, body=UNSUPPORTED_TYPE_REPLY, webhook_event=webhook_event,
        )
        return

    # From here on a transcribed voice note is handled identically to a typed
    # message. Don't reply yet -- buffer this fragment and (re)schedule a
    # debounced job so a burst of quick messages gets one merged reply
    # instead of one reply per fragment.
    await db.commit()
    await _buffer_and_schedule_reply(
        ctx=ctx,
        conversation_id=conversation.id,
        message_id=inbound.id,
        webhook_event_id=webhook_event.id,
    )


async def _buffer_and_schedule_reply(*, ctx, conversation_id, message_id, webhook_event_id) -> None:
    redis = ctx["redis"]
    msgs_key = _debounce_msgs_key(conversation_id)
    gen_key = _debounce_gen_key(conversation_id)

    # "{message_id}:{webhook_event_id}" -- keeps enough of a trail that the
    # debounced job can still write send failures back onto the webhook
    # event that most recently fed it, for the connection-status diagnostics.
    await redis.rpush(msgs_key, f"{message_id}:{webhook_event_id}")
    await redis.expire(msgs_key, DEBOUNCE_KEY_TTL)
    generation = await redis.incr(gen_key)
    await redis.expire(gen_key, DEBOUNCE_KEY_TTL)

    await redis.enqueue_job(
        "process_debounced_reply", str(conversation_id), generation, _defer_by=DEBOUNCE_SECONDS
    )


async def process_debounced_reply(ctx, conversation_id: str, generation: int) -> None:
    """Fires DEBOUNCE_SECONDS after the last buffered fragment. If a newer
    fragment arrived in the meantime, the generation counter has moved on
    and this run is a no-op -- the job scheduled for that newer fragment is
    the one that will actually reply."""
    redis = ctx["redis"]
    gen_key = _debounce_gen_key(conversation_id)
    current_generation = await redis.get(gen_key)
    if current_generation is None or int(current_generation) != generation:
        return

    msgs_key = _debounce_msgs_key(conversation_id)
    raw_entries = await redis.lrange(msgs_key, 0, -1)
    await redis.delete(msgs_key, gen_key)
    if not raw_entries:
        return

    message_ids: set[uuid.UUID] = set()
    last_webhook_event_id: uuid.UUID | None = None
    for raw in raw_entries:
        entry = raw.decode() if isinstance(raw, bytes) else raw
        message_id_str, _, webhook_event_id_str = entry.partition(":")
        message_ids.add(uuid.UUID(message_id_str))
        if webhook_event_id_str:
            last_webhook_event_id = uuid.UUID(webhook_event_id_str)

    async with async_session_maker() as db:
        conversation = await db.get(Conversation, uuid.UUID(conversation_id))
        if conversation is None:
            return
        # Re-check: handoff is sacred, and status could have changed while we
        # waited (e.g. a staff member sent a manual reply in the meantime).
        if conversation.status in (ConversationStatus.needs_human, ConversationStatus.human):
            return

        messages = (
            await db.scalars(
                select(Message)
                .where(Message.id.in_(message_ids))
                .order_by(Message.created_at.asc())
            )
        ).all()
        merged_text = "\n".join((m.text or "").strip() for m in messages if m.text).strip()
        if not merged_text:
            return

        tenant = await db.get(Tenant, conversation.tenant_id)
        whatsapp_config = await db.scalar(
            select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == conversation.tenant_id)
        )
        contact = await db.get(Contact, conversation.contact_id)
        if tenant is None or whatsapp_config is None or contact is None:
            return
        access_token = decrypt_secret(whatsapp_config.access_token_encrypted)

        webhook_event = (
            await db.get(WebhookEvent, last_webhook_event_id)
            if last_webhook_event_id is not None
            else None
        )

        await _generate_and_send_reply(
            db=db,
            tenant=tenant,
            whatsapp_config=whatsapp_config,
            access_token=access_token,
            conversation=conversation,
            to=contact.phone,
            text=merged_text,
            webhook_event=webhook_event,
            exclude_message_ids=message_ids,
        )


async def _generate_and_send_reply(
    *, db, tenant: Tenant, whatsapp_config, access_token, conversation, to, text,
    webhook_event=None, exclude_message_ids: set | None = None,
) -> None:
    """The RAG-grounded reply pipeline, shared by the debounced worker job.
    Assumes the handoff-is-sacred check already passed for this conversation."""
    tenant_id = tenant.id
    settings = get_settings()
    agent_settings = get_agent_settings(tenant.settings)
    llm_config = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))
    llm_api_key = decrypt_secret(llm_config.api_key_encrypted) if llm_config else None

    trigger = detect_handoff_trigger(text)
    if trigger is not None:
        await _trigger_handoff(
            db=db, tenant_id=tenant_id, conversation=conversation,
            whatsapp_config=whatsapp_config, access_token=access_token,
            to=to, reason=trigger, webhook_event=webhook_event,
            handoff_message=agent_settings["handoff_message"],
        )
        return

    if not is_within_service_window(conversation):
        logger.info(
            "Outside 24h service window for conversation=%s -- no auto-reply", conversation.id
        )
        await db.commit()
        return

    if llm_config is None or llm_api_key is None:
        await _trigger_handoff(
            db=db, tenant_id=tenant_id, conversation=conversation,
            whatsapp_config=whatsapp_config, access_token=access_token,
            to=to, reason="no_llm_configured", webhook_event=webhook_event,
            handoff_message=agent_settings["handoff_message"],
        )
        return

    chunks = await rag.retrieve_chunks(
        db=db,
        tenant_id=tenant_id,
        query=text,
        embedding_model=settings.default_embedding_model,
        api_key=llm_api_key,
    )
    if not chunks:
        await _trigger_handoff(
            db=db, tenant_id=tenant_id, conversation=conversation,
            whatsapp_config=whatsapp_config, access_token=access_token,
            to=to, reason="no_reliable_answer", webhook_event=webhook_event,
            handoff_message=agent_settings["handoff_message"],
        )
        return

    conversation_context = await _load_recent_chat_context(
        db=db,
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        limit=agent_settings["memory_window_messages"],
        exclude_message_ids=exclude_message_ids,
    )
    reply_text = await generate_reply(
        model=llm_config.model,
        api_key=llm_api_key,
        business_name=tenant.name,
        tone=agent_settings["tone"],
        context="\n\n".join(chunks),
        user_message=text,
        reply_mode=agent_settings["reply_mode"],
        lead_fields=agent_settings["lead_fields"],
        extra_instructions=agent_settings["extra_instructions"],
        conversation_context=conversation_context,
    )

    sent = await _send_reply(
        db=db, tenant_id=tenant_id, conversation=conversation,
        whatsapp_config=whatsapp_config, access_token=access_token,
        to=to, body=reply_text, webhook_event=webhook_event,
    )
    if sent:
        db.add(UsageLog(tenant_id=tenant_id, message_count=1))
    await db.commit()


def _debounce_msgs_key(conversation_id) -> str:
    return f"debounce:msgs:{conversation_id}"


def _debounce_gen_key(conversation_id) -> str:
    return f"debounce:gen:{conversation_id}"


def _extract_interactive_reply_text(raw_message: dict) -> str | None:
    """Meta sends the tapped option back as interactive.list_reply (or
    .button_reply for reply-button messages) -- the row's title is what the
    customer effectively "said"."""
    interactive = raw_message.get("interactive") or {}
    list_reply = interactive.get("list_reply")
    if list_reply and list_reply.get("title"):
        return list_reply["title"]
    button_reply = interactive.get("button_reply")
    if button_reply and button_reply.get("title"):
        return button_reply["title"]
    return None


async def _send_greeting(
    *, db, tenant_id, conversation, whatsapp_config, access_token, to, agent_settings, webhook_event=None
) -> None:
    greeting = agent_settings["greeting_message"]
    options = agent_settings["greeting_menu_options"]

    if not options:
        await _send_reply(
            db=db, tenant_id=tenant_id, conversation=conversation,
            whatsapp_config=whatsapp_config, access_token=access_token,
            to=to, body=greeting, webhook_event=webhook_event,
        )
        return

    menu_options = [
        {"id": f"greeting_option_{i}", "title": option["title"], "description": option["description"]}
        for i, option in enumerate(options)
    ]
    try:
        await meta.send_interactive_list_message(
            phone_number_id=whatsapp_config.phone_number_id,
            access_token=access_token,
            to=to,
            body=greeting,
            button_text="Choose an option",
            options=menu_options,
        )
    except Exception as exc:
        logger.exception(
            "Failed to send greeting list message for tenant=%s conversation=%s",
            tenant_id, conversation.id,
        )
        if webhook_event is not None:
            webhook_event.failure_reason = webhook_event.failure_reason or "whatsapp_send_failed"
            webhook_event.send_error = _safe_error_message(exc, secret=access_token)
        await db.commit()
        return

    db.add(
        Message(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            direction=MessageDirection.outbound,
            type=MessageType.text,
            text=greeting,
        )
    )
    await db.commit()


async def _transcribe_voice_note(
    *, raw_message: dict, access_token: str, transcription_model: str, api_key: str
) -> tuple[str | None, str | None]:
    """Downloads and transcribes an inbound WhatsApp voice note. Returns
    (transcript, media_url) on success, (None, media_url_or_None) on any
    failure -- callers treat None as "couldn't process" and fall back to the
    unsupported-type reply rather than surfacing an error to the customer."""
    audio_id = raw_message.get("audio", {}).get("id")
    if not audio_id:
        return None, None

    media_url: str | None = None
    try:
        media_url = await meta.get_media_url(media_id=audio_id, access_token=access_token)
        audio_bytes = await meta.download_media(media_url=media_url, access_token=access_token)
        transcript = await transcribe_audio(
            model=transcription_model,
            api_key=api_key,
            audio_bytes=audio_bytes,
            filename="voice_note.ogg",
        )
        return (transcript or None), media_url
    except Exception:
        logger.exception("Voice note transcription failed for audio_id=%s", audio_id)
        return None, media_url


async def _send_reply(
    *, db, tenant_id, conversation, whatsapp_config, access_token, to, body, webhook_event=None
) -> bool:
    try:
        await meta.send_text_message(
            phone_number_id=whatsapp_config.phone_number_id,
            access_token=access_token,
            to=to,
            body=body,
        )
    except Exception as exc:
        # An invalid/expired WhatsApp token must not crash the job -- log it
        # so it's visible on the connection status page/logs, and let the
        # webhook event still get marked processed rather than retried
        # forever against a token that will keep failing.
        logger.exception(
            "Failed to send WhatsApp reply for tenant=%s conversation=%s -- "
            "check the WhatsApp access token in Agent Settings",
            tenant_id,
            conversation.id,
        )
        if webhook_event is not None:
            webhook_event.failure_reason = webhook_event.failure_reason or "whatsapp_send_failed"
            webhook_event.send_error = _safe_error_message(exc, secret=access_token)
        await db.commit()
        return False

    db.add(
        Message(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            direction=MessageDirection.outbound,
            type=MessageType.text,
            text=body,
        )
    )
    await db.commit()
    return True


async def _trigger_handoff(
    *,
    db,
    tenant_id,
    conversation,
    whatsapp_config,
    access_token,
    to,
    reason,
    webhook_event=None,
    handoff_message: str = DEFAULT_HANDOFF_MESSAGE,
) -> None:
    conversation.status = ConversationStatus.needs_human
    db.add(HandoffEvent(tenant_id=tenant_id, conversation_id=conversation.id, reason=reason))

    lead = await db.scalar(
        select(Lead).where(Lead.tenant_id == tenant_id, Lead.contact_id == conversation.contact_id)
    )
    if lead is not None:
        lead.status = LeadStatus.needs_human
        lead.intent = reason[:64]  # matches leads.intent's column length

    await _notify_owner_of_handoff(
        db=db, tenant_id=tenant_id, conversation=conversation, reason=reason, customer_phone=to,
    )

    await _send_reply(
        db=db, tenant_id=tenant_id, conversation=conversation,
        whatsapp_config=whatsapp_config, access_token=access_token,
        to=to, body=handoff_message, webhook_event=webhook_event,
    )


async def _notify_owner_of_handoff(*, db, tenant_id, conversation, reason, customer_phone) -> None:
    """Best-effort: nobody watches the dashboard 24/7, so the owner needs a
    ping when a chat needs them. A missing/broken SMTP config must never
    break the handoff itself -- failures are logged and swallowed here."""
    try:
        tenant = await db.get(Tenant, tenant_id)
        owner_email = await db.scalar(
            select(User.email).where(User.tenant_id == tenant_id, User.role == UserRole.owner)
        )
        if tenant is None or not owner_email:
            return
        await notifications.send_handoff_email(
            to_email=owner_email,
            business_name=tenant.name,
            reason=reason,
            customer_phone=customer_phone,
            conversation_id=conversation.id,
        )
    except Exception:
        logger.exception("Owner handoff notification failed for tenant=%s", tenant_id)


async def _ensure_lead(*, db, tenant_id, contact_id) -> None:
    """One lead per contact, created on their first message. This is the
    CRM's actual lead-capture step -- without it, /leads and the dashboard's
    lead count are always empty regardless of how many conversations exist."""
    existing = await db.scalar(
        select(Lead.id).where(Lead.tenant_id == tenant_id, Lead.contact_id == contact_id)
    )
    if existing is None:
        db.add(Lead(tenant_id=tenant_id, contact_id=contact_id, status=LeadStatus.new))
        await db.flush()


async def _load_recent_chat_context(
    *, db, tenant_id, conversation_id, limit: int, exclude_message_ids: set | None = None
) -> str:
    if limit <= 0:
        return ""
    exclude_message_ids = exclude_message_ids or set()

    messages = (
        await db.scalars(
            select(Message)
            .where(Message.tenant_id == tenant_id, Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit + len(exclude_message_ids) + 1)
        )
    ).all()

    lines: list[str] = []
    for message in reversed(messages):
        if message.id in exclude_message_ids:
            continue
        body = (message.text or "").strip()
        if not body:
            continue
        speaker = "Customer" if message.direction == MessageDirection.inbound else "Assistant"
        lines.append(f"{speaker}: {body[:500]}")
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def _mark_event_processed(
    event: WebhookEvent, *, failure_reason: str | None = None, error_message: str | None = None
) -> None:
    event.processed = True
    event.processed_at = datetime.now(timezone.utc)
    if failure_reason is not None:
        event.failure_reason = failure_reason
    if error_message is not None:
        event.error_message = error_message[:MAX_DIAGNOSTIC_LENGTH]


def _safe_error_message(exc: Exception, *, secret: str | None = None) -> str:
    message = f"{type(exc).__name__}: {exc}"
    if secret:
        message = message.replace(secret, "[redacted]")
    return message[:MAX_DIAGNOSTIC_LENGTH]
