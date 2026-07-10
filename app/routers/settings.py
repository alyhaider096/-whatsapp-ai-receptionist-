import redis.asyncio as redis
from fastapi import APIRouter
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TenantId
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.llm_config import LLMConfig
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.handoff_event import HandoffEvent
from app.models.lead import Lead
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.schemas.settings import (
    AgentBehaviorIn,
    AgentBehaviorOut,
    ConnectionStatusOut,
    LLMConfigIn,
    LLMConfigOut,
    TestInboundMessageIn,
    TestInboundMessageOut,
    WhatsAppConfigIn,
    WhatsAppConfigOut,
)
from app.services.agent_settings import get_agent_settings
from app.worker.queue import enqueue_job

router = APIRouter(prefix="/settings", tags=["settings"])


PLACEHOLDER_MARKERS = ("change-me", "placeholder", "dev-", "test", "fake", "your-")


def _looks_like_placeholder(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


async def _get_runtime_diagnostics() -> tuple[bool, int | None, bool, str | None]:
    settings = get_settings()
    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        await client.ping()
        queue_depth = await client.zcard("arq:queue")
        health_detail = await client.get("arq:queue:health-check")
        if health_detail is not None:
            health_detail = health_detail[:200]
        return True, int(queue_depth), health_detail is not None, health_detail
    except Exception:
        return False, None, False, None
    finally:
        await client.aclose()


def _normalize_whatsapp_number(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("92"):
        return digits
    if digits.startswith("0"):
        return f"92{digits[1:]}"
    if digits.startswith("3") and len(digits) == 10:
        return f"92{digits}"
    return digits


def _build_test_webhook_payload(
    *, waba_id: str, phone_number_id: str, from_number: str, text: str, wa_message_id: str
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": phone_number_id,
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Dashboard Test"}, "wa_id": from_number}
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wa_message_id,
                                    "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                                    "text": {"body": text},
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


async def _reset_test_conversation(*, db: DbSession, tenant_id, from_number: str) -> None:
    contact = await db.scalar(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.phone == from_number)
    )
    if contact is None:
        return

    conversation_ids = (
        await db.scalars(
            select(Conversation.id).where(
                Conversation.tenant_id == tenant_id,
                Conversation.contact_id == contact.id,
            )
        )
    ).all()
    if conversation_ids:
        await db.execute(
            delete(HandoffEvent).where(
                HandoffEvent.tenant_id == tenant_id,
                HandoffEvent.conversation_id.in_(conversation_ids),
            )
        )
        await db.execute(
            delete(Message).where(
                Message.tenant_id == tenant_id,
                Message.conversation_id.in_(conversation_ids),
            )
        )
        await db.execute(
            delete(Conversation).where(
                Conversation.tenant_id == tenant_id,
                Conversation.id.in_(conversation_ids),
            )
        )
    await db.execute(
        delete(Lead).where(Lead.tenant_id == tenant_id, Lead.contact_id == contact.id)
    )
    await db.execute(delete(Contact).where(Contact.tenant_id == tenant_id, Contact.id == contact.id))


@router.get("/whatsapp", response_model=WhatsAppConfigOut | None)
async def get_whatsapp_config(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    config = await db.scalar(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant_id))
    if config is None:
        return None
    return WhatsAppConfigOut(
        waba_id=config.waba_id,
        phone_number_id=config.phone_number_id,
        access_token_masked=mask_secret(decrypt_secret(config.access_token_encrypted)),
        status=config.status,
    )


@router.put("/whatsapp", response_model=WhatsAppConfigOut)
async def put_whatsapp_config(
    payload: WhatsAppConfigIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    config = await db.scalar(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant_id))
    if config is None:
        if payload.access_token is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add a WhatsApp access token before saving this connection.",
            )
        config = WhatsAppConfig(tenant_id=tenant_id)
        db.add(config)

    config.waba_id = payload.waba_id
    config.phone_number_id = payload.phone_number_id
    if payload.access_token is not None:
        config.access_token_encrypted = encrypt_secret(payload.access_token)
    config.status = "connected"
    await db.commit()
    await db.refresh(config)

    return WhatsAppConfigOut(
        waba_id=config.waba_id,
        phone_number_id=config.phone_number_id,
        access_token_masked=mask_secret(decrypt_secret(config.access_token_encrypted)),
        status=config.status,
    )


@router.get("/llm", response_model=LLMConfigOut | None)
async def get_llm_config(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    config = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))
    if config is None:
        return None
    return LLMConfigOut(
        provider=config.provider,
        model=config.model,
        api_key_masked=mask_secret(decrypt_secret(config.api_key_encrypted)),
    )


@router.put("/llm", response_model=LLMConfigOut)
async def put_llm_config(
    payload: LLMConfigIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    config = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))
    if config is None:
        if payload.api_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add an LLM API key before saving this model.",
            )
        config = LLMConfig(tenant_id=tenant_id)
        db.add(config)

    config.provider = payload.provider
    config.model = payload.model
    if payload.api_key is not None:
        config.api_key_encrypted = encrypt_secret(payload.api_key)
    await db.commit()
    await db.refresh(config)

    return LLMConfigOut(
        provider=config.provider,
        model=config.model,
        api_key_masked=mask_secret(decrypt_secret(config.api_key_encrypted)),
    )


@router.get("/agent", response_model=AgentBehaviorOut)
async def get_agent_behavior(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return AgentBehaviorOut(**get_agent_settings(tenant.settings))


@router.put("/agent", response_model=AgentBehaviorOut)
async def put_agent_behavior(
    payload: AgentBehaviorIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    next_settings = dict(tenant.settings or {})
    next_settings["agent"] = payload.model_dump()
    tenant.settings = next_settings
    await db.commit()
    await db.refresh(tenant)
    return AgentBehaviorOut(**get_agent_settings(tenant.settings))


@router.get("/status", response_model=ConnectionStatusOut)
async def get_connection_status(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    settings = get_settings()
    whatsapp = await db.scalar(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant_id))
    llm = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))

    webhook_last = None
    if whatsapp is not None:
        webhook_last = await db.scalar(
            select(WebhookEvent)
            .where(
                or_(
                    WebhookEvent.tenant_id == tenant_id,
                    WebhookEvent.phone_number_id == whatsapp.phone_number_id,
                )
            )
            .order_by(WebhookEvent.created_at.desc())
            .limit(1)
        )
    redis_connected, worker_queue_depth, worker_health_seen, worker_health_detail = (
        await _get_runtime_diagnostics()
    )

    return ConnectionStatusOut(
        whatsapp_connected=whatsapp is not None,
        whatsapp_status=whatsapp.status if whatsapp else None,
        llm_connected=llm is not None,
        llm_model=llm.model if llm else None,
        webhook_last_seen_at=webhook_last.created_at if webhook_last else None,
        webhook_expected_phone_number_id=whatsapp.phone_number_id if whatsapp else None,
        webhook_last_phone_number_id=webhook_last.phone_number_id if webhook_last else None,
        webhook_last_processed_at=webhook_last.processed_at if webhook_last else None,
        webhook_last_failure_reason=webhook_last.failure_reason if webhook_last else None,
        webhook_last_error_message=webhook_last.error_message if webhook_last else None,
        webhook_last_send_error=webhook_last.send_error if webhook_last else None,
        webhook_signature_configured=bool(settings.meta_app_secret),
        webhook_verify_token_configured=bool(settings.meta_verify_token),
        webhook_verify_token_is_placeholder=_looks_like_placeholder(settings.meta_verify_token),
        redis_connected=redis_connected,
        worker_queue_depth=worker_queue_depth,
        worker_health_seen=worker_health_seen,
        worker_health_detail=worker_health_detail,
    )


@router.post(
    "/test-inbound",
    response_model=TestInboundMessageOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_test_inbound_message(
    payload: TestInboundMessageIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    settings = get_settings()
    if settings.environment.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard test conversations are only available in development.",
        )

    whatsapp = await db.scalar(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant_id))
    if whatsapp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect a WhatsApp number in Agent Settings first.",
        )

    from_number = _normalize_whatsapp_number(payload.from_number)
    if len(from_number) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid WhatsApp number. Pakistani local numbers are auto-converted to +92.",
        )

    if payload.reset_conversation:
        await _reset_test_conversation(db=db, tenant_id=tenant_id, from_number=from_number)

    wa_message_id = f"wamid.dashboard-test-{uuid.uuid4()}"
    event_payload = _build_test_webhook_payload(
        waba_id=whatsapp.waba_id,
        phone_number_id=whatsapp.phone_number_id,
        from_number=from_number,
        text=payload.text,
        wa_message_id=wa_message_id,
    )
    event = WebhookEvent(
        tenant_id=tenant_id,
        phone_number_id=whatsapp.phone_number_id,
        payload=event_payload,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await enqueue_job("process_whatsapp_webhook", str(event.id))

    return TestInboundMessageOut(
        status="queued",
        webhook_event_id=str(event.id),
        wa_message_id=wa_message_id,
        normalized_from_number=from_number,
    )
