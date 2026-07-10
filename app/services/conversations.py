"""Contact/conversation lookup helpers and the handoff + 24h-window rules
shared by the inbound worker job and (later) any manual-reply endpoint."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.conversation import Conversation

SERVICE_WINDOW = timedelta(hours=24)

# Matches the handoff trigger list in WHATSAPP_AI_RECEPTIONIST_DOCS.md section 7.
HANDOFF_KEYWORDS = (
    "human",
    "agent",
    "real person",
    "call me",
    "callback",
    "talk to someone",
    "speak to someone",
    "speak to a person",
)


async def get_or_create_contact(*, db: AsyncSession, tenant_id: uuid.UUID, phone: str) -> Contact:
    contact = await db.scalar(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.phone == phone)
    )
    if contact is None:
        contact = Contact(tenant_id=tenant_id, phone=phone)
        db.add(contact)
        await db.flush()
    return contact


async def get_or_create_conversation(
    *, db: AsyncSession, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> Conversation:
    conversation = await db.scalar(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id, Conversation.contact_id == contact_id)
        .order_by(Conversation.created_at.desc())
    )
    if conversation is None:
        conversation = Conversation(tenant_id=tenant_id, contact_id=contact_id)
        db.add(conversation)
        await db.flush()
    return conversation


def is_within_service_window(conversation: Conversation, *, now: datetime | None = None) -> bool:
    """CLAUDE.md rule 5: block free-form outbound sends once last_inbound_at
    is more than 24h old."""
    if conversation.last_inbound_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - conversation.last_inbound_at <= SERVICE_WINDOW


def detect_handoff_trigger(text: str) -> str | None:
    """Returns the matched trigger reason, or None. Cheap keyword check --
    good enough for v1; the 'no reliable chunk' trigger is handled separately
    where retrieval actually runs."""
    lowered = text.lower()
    for keyword in HANDOFF_KEYWORDS:
        if keyword in lowered:
            return f"user_requested_human:{keyword}"
    return None
