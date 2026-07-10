"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # create_type=False: these are created explicitly below via checkfirst=True.
    # Without it, op.create_table() also tries to auto-create the same type
    # via each column's before_create hook (no checkfirst there), which fails
    # with "already exists" against the one we just created by hand.
    user_role = postgresql.ENUM("owner", "staff", name="user_role", create_type=False)
    conversation_status = postgresql.ENUM(
        "open", "needs_human", "human", "closed", name="conversation_status", create_type=False
    )
    message_direction = postgresql.ENUM(
        "inbound", "outbound", name="message_direction", create_type=False
    )
    message_type = postgresql.ENUM(
        "text", "audio", "image", "document", name="message_type", create_type=False
    )
    document_status = postgresql.ENUM(
        "processing", "ready", "failed", name="document_status", create_type=False
    )
    lead_status = postgresql.ENUM(
        "new", "qualified", "needs_human", "booked", "lost", name="lead_status", create_type=False
    )
    bind = op.get_bind()
    for enum in (
        user_role,
        conversation_status,
        message_direction,
        message_type,
        document_status,
        lead_status,
    ):
        enum.create(bind, checkfirst=True)

    def ts_columns():
        return [
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
                nullable=False,
            ),
        ]

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        *ts_columns(),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="owner"),
        *ts_columns(),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "whatsapp_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("waba_id", sa.String(64), nullable=False),
        sa.Column("phone_number_id", sa.String(64), nullable=False),
        sa.Column("access_token_encrypted", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="disconnected"),
        *ts_columns(),
    )
    op.create_index("ix_whatsapp_configs_tenant_id", "whatsapp_configs", ["tenant_id"])
    op.create_index(
        "ix_whatsapp_configs_phone_number_id", "whatsapp_configs", ["phone_number_id"]
    )

    op.create_table(
        "llm_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="openai"),
        sa.Column("api_key_encrypted", sa.String(2048), nullable=False),
        sa.Column("model", sa.String(128), nullable=False, server_default="openai/gpt-4o-mini"),
        *ts_columns(),
    )
    op.create_index("ix_llm_configs_tenant_id", "llm_configs", ["tenant_id"])

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("language_pref", sa.String(16), nullable=True),
        *ts_columns(),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),
    )
    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])
    op.create_index("ix_contacts_phone", "contacts", ["phone"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column("status", conversation_status, nullable=False, server_default="open"),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        *ts_columns(),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_contact_id", "conversations", ["contact_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("wa_message_id", sa.String(128), nullable=True),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("type", message_type, nullable=False, server_default="text"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.String(1024), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        *ts_columns(),
        sa.UniqueConstraint("wa_message_id", name="uq_messages_wa_message_id"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_wa_message_id", "messages", ["wa_message_id"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="txt"),
        sa.Column("status", document_status, nullable=False, server_default="processing"),
        *ts_columns(),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        *ts_columns(),
    )
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("status", lead_status, nullable=False, server_default="new"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("value", sa.Numeric(12, 2), nullable=True),
        *ts_columns(),
    )
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])
    op.create_index("ix_leads_contact_id", "leads", ["contact_id"])

    op.create_table(
        "handoff_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(128), nullable=False),
        *ts_columns(),
    )
    op.create_index("ix_handoff_events_tenant_id", "handoff_events", ["tenant_id"])
    op.create_index("ix_handoff_events_conversation_id", "handoff_events", ["conversation_id"])

    op.create_table(
        "usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transcription_minutes", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        *ts_columns(),
    )
    op.create_index("ix_usage_logs_tenant_id", "usage_logs", ["tenant_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_number_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *ts_columns(),
    )
    op.create_index(
        "ix_webhook_events_phone_number_id", "webhook_events", ["phone_number_id"]
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        *ts_columns(),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("webhook_events")
    op.drop_table("usage_logs")
    op.drop_table("handoff_events")
    op.drop_table("leads")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("contacts")
    op.drop_table("llm_configs")
    op.drop_table("whatsapp_configs")
    op.drop_table("users")
    op.drop_table("tenants")

    bind = op.get_bind()
    for enum_name in (
        "lead_status",
        "document_status",
        "message_type",
        "message_direction",
        "conversation_status",
        "user_role",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
