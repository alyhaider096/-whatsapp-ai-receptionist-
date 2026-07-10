"""Inbound WhatsApp webhook. Must stay fast: verify signature, dedup, store
the raw payload, enqueue a background job, return 200 -- no LLM/embedding/
HTTP calls inline (CLAUDE.md rule 2)."""

import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.security import verify_meta_signature
from app.models.message import Message
from app.models.webhook_event import WebhookEvent
from app.worker.queue import enqueue_job

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/whatsapp")
async def verify_webhook(request: Request) -> Response:
    settings = get_settings()
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if settings.meta_verify_token and mode == "subscribe" and token == settings.meta_verify_token:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_webhook(request: Request, db: DbSession) -> dict:
    settings = get_settings()
    raw_body = await request.body()

    signature = request.headers.get("x-hub-signature-256", "")
    if not settings.meta_app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook signature verification is not configured",
        )
    if not verify_meta_signature(
        app_secret=settings.meta_app_secret, payload=raw_body, signature_header=signature
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    wa_message_id, phone_number_id = _extract_ids(payload)

    # Fast-path dedup so a Meta retry never even reaches the queue. The
    # unique constraint on messages.wa_message_id is the real safety net for
    # the race where two deliveries arrive at almost the same time.
    if wa_message_id:
        existing = await db.scalar(
            select(Message.id).where(Message.wa_message_id == wa_message_id)
        )
        if existing is not None:
            return {"status": "duplicate_ignored"}

    event = WebhookEvent(phone_number_id=phone_number_id or "", payload=payload)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await enqueue_job("process_whatsapp_webhook", str(event.id))

    return {"status": "queued"}


def _extract_ids(payload: dict) -> tuple[str | None, str | None]:
    """Path per CLAUDE.md: entry[0].changes[0].value.messages[0]."""
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        messages = value.get("messages") or []
        wa_message_id = messages[0]["id"] if messages else None
        return wa_message_id, phone_number_id
    except (KeyError, IndexError, TypeError):
        return None, None
