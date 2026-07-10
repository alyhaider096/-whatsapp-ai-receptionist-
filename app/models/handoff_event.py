import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class HandoffEvent(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "handoff_events"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
