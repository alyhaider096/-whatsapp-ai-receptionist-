from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class WhatsAppConfig(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "whatsapp_configs"

    waba_id: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="disconnected")
