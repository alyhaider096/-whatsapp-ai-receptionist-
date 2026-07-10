from sqlalchemy import Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class UsageLog(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "usage_logs"

    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transcription_minutes: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
