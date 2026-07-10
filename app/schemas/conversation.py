from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContactOut(BaseModel):
    id: UUID
    phone: str
    name: str | None

    model_config = {"from_attributes": True}


class TeamMemberOut(BaseModel):
    id: UUID
    email: str
    role: str


class ConversationOut(BaseModel):
    id: UUID
    status: str
    last_inbound_at: datetime | None
    contact: ContactOut
    last_message_text: str | None
    updated_at: datetime
    assigned_user_id: UUID | None = None
    assigned_user_email: str | None = None
    tags: list[str] = Field(default_factory=list)
    lead_status: str | None = None
    lead_notes: str | None = None


class ConversationCrmUpdateIn(BaseModel):
    """All fields optional -- only the ones actually present in the request
    body are applied (see routers/conversations.py's use of
    model_fields_set), so sending {"lead_notes": "..."} never wipes out an
    already-set assigned_user_id."""

    assigned_user_id: UUID | None = None
    lead_status: str | None = None
    lead_notes: str | None = Field(default=None, max_length=4000)


class TagIn(BaseModel):
    tag: str = Field(min_length=1, max_length=50)


class MessageOut(BaseModel):
    id: UUID
    direction: str
    type: str
    text: str | None
    audio_url: str | None
    created_at: datetime


class ReplyIn(BaseModel):
    text: str = Field(min_length=1)


class LeadOut(BaseModel):
    id: UUID
    intent: str | None
    status: str
    notes: str | None
    value: float | None
    contact: ContactOut
    created_at: datetime
