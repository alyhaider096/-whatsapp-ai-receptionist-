"""google sheets appointment booking: sheet_configs + conversations.pending_action

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sheet_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spreadsheet_id", sa.String(128), nullable=False),
        sa.Column("sheet_name", sa.String(64), nullable=False, server_default="Appointments"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sheet_configs_tenant_id", "sheet_configs", ["tenant_id"])

    op.add_column(
        "conversations", sa.Column("pending_action", postgresql.JSONB, nullable=True)
    )


def downgrade() -> None:
    op.drop_column("conversations", "pending_action")
    op.drop_index("ix_sheet_configs_tenant_id", table_name="sheet_configs")
    op.drop_table("sheet_configs")
