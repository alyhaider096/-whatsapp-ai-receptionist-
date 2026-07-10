from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class LLMConfig(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "llm_configs"

    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openai")
    api_key_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="openai/gpt-4o-mini")
