from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class CalcomConfig(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "calcom_configs"

    api_key_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    event_type_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_type_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
