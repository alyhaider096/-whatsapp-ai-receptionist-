"""cal.com booking integration: calcom_configs

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calcom_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_encrypted", sa.String(2048), nullable=False),
        sa.Column("event_type_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type_title", sa.String(255), nullable=True),
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
    op.create_index("ix_calcom_configs_tenant_id", "calcom_configs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_calcom_configs_tenant_id", table_name="calcom_configs")
    op.drop_table("calcom_configs")
