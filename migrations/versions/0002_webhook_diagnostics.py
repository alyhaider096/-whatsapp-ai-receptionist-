"""webhook diagnostics

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webhook_events", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("webhook_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("webhook_events", sa.Column("failure_reason", sa.String(length=128), nullable=True))
    op.add_column("webhook_events", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("webhook_events", sa.Column("send_error", sa.Text(), nullable=True))
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_events_tenant_id", table_name="webhook_events")
    op.drop_column("webhook_events", "send_error")
    op.drop_column("webhook_events", "error_message")
    op.drop_column("webhook_events", "failure_reason")
    op.drop_column("webhook_events", "processed_at")
    op.drop_column("webhook_events", "tenant_id")
