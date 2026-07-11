import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin
from app.models.enums import ConversationStatus


class Conversation(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "conversations"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status"),
        nullable=False,
        default=ConversationStatus.open,
    )
    # Drives the 24h service-window rule (CLAUDE.md rule 5). Updated on every
    # inbound message; outbound sends must check this before replying.
    last_inbound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # CRM inbox panel: who owns this conversation right now. Nullable/unassigned
    # by default; SET NULL if that user is ever removed.
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Booking confirmation gate: {"type": "create"|"reschedule", "args": {...},
    # "proposed_at": iso timestamp} while a proposed Sheets write is awaiting
    # the customer's yes/no. Cleared on confirm, decline, or staleness.
    pending_action: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
