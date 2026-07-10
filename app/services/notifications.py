"""Owner handoff email notifications. Best-effort only -- SMTP is optional
(blank SMTP_HOST means "not configured yet"), and any failure here must
never break the worker pipeline that calls it, so everything is caught and
logged rather than raised."""

import asyncio
import logging
import smtplib
import uuid
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_REASON_LABELS = {
    "no_llm_configured": "No LLM API key is configured for this business yet.",
    "no_reliable_answer": "The AI didn't have a confident, knowledge-base-backed answer.",
}


def _describe_reason(reason: str) -> str:
    if reason in _REASON_LABELS:
        return _REASON_LABELS[reason]
    if reason.startswith("user_requested_human:"):
        keyword = reason.split(":", 1)[1]
        return f'Customer asked for a human (matched "{keyword}").'
    return reason


async def send_handoff_email(
    *,
    to_email: str,
    business_name: str,
    reason: str,
    customer_phone: str,
    conversation_id: uuid.UUID,
) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.info("SMTP not configured -- skipping owner handoff notification")
        return

    message = EmailMessage()
    message["Subject"] = f"[{business_name}] A WhatsApp chat needs you"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "A conversation just got handed off to a human.\n\n"
        f"Customer: {customer_phone}\n"
        f"Reason: {_describe_reason(reason)}\n\n"
        f"Open it: {settings.app_base_url}/dashboard/conversations/{conversation_id}"
    )

    try:
        await asyncio.to_thread(_send_via_smtp, message)
    except Exception:
        logger.exception("Failed to send owner handoff notification email to %s", to_email)


def _send_via_smtp(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
