"""conversation CRM persistence: assigned_user_id + conversation_tags

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_assigned_user_id_users",
        "conversations",
        "users",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "conversation_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(50), nullable=False),
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
        sa.UniqueConstraint("conversation_id", "tag", name="uq_conversation_tags_conversation_tag"),
    )
    op.create_index("ix_conversation_tags_tenant_id", "conversation_tags", ["tenant_id"])
    op.create_index(
        "ix_conversation_tags_conversation_id", "conversation_tags", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_tags_conversation_id", table_name="conversation_tags")
    op.drop_index("ix_conversation_tags_tenant_id", table_name="conversation_tags")
    op.drop_table("conversation_tags")
    op.drop_constraint(
        "fk_conversations_assigned_user_id_users", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "assigned_user_id")
