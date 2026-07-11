from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin


class SheetConfig(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "sheet_configs"

    spreadsheet_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Appointments")
