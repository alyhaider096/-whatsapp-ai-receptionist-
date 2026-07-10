import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class WebhookEvent(Base, UUIDPKMixin, TimestampMixin):
    """Raw Meta webhook deliveries, stored before enqueueing so a failed job
    can be replayed. tenant_id starts nullable because inbound routing is
    based on phone_number_id; the worker fills it once a tenant is resolved."""

    __tablename__ = "webhook_events"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
