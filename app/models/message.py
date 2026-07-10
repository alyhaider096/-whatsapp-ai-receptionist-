import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin
from app.models.enums import MessageDirection, MessageType


class Message(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        # Meta retries webhook deliveries. This constraint is what makes the
        # webhook job idempotent (CLAUDE.md rule 3) -- a second delivery of
        # the same wa_message_id must fail to insert, not create a duplicate.
        UniqueConstraint("wa_message_id", name="uq_messages_wa_message_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    # Null for outbound messages we generate ourselves.
    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction"), nullable=False
    )
    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"), nullable=False, default=MessageType.text
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
