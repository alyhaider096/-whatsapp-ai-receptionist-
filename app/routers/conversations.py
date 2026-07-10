from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession, TenantId
from app.core.security import decrypt_secret
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_tag import ConversationTag
from app.models.enums import ConversationStatus, LeadStatus, MessageDirection, MessageType
from app.models.lead import Lead
from app.models.message import Message
from app.models.user import User
from app.models.whatsapp_config import WhatsAppConfig
from app.schemas.conversation import (
    ContactOut,
    ConversationCrmUpdateIn,
    ConversationOut,
    LeadOut,
    MessageOut,
    ReplyIn,
    TagIn,
    TeamMemberOut,
)
from app.services import meta
from app.services.conversations import is_within_service_window

router = APIRouter(tags=["conversations"])

MAX_TAGS_PER_CONVERSATION = 20


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    result = await db.execute(
        select(Conversation, Contact)
        .join(Contact, Conversation.contact_id == Contact.id)
        .where(Conversation.tenant_id == tenant_id, Contact.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = result.all()

    tags_by_conversation = await _load_tags_by_conversation(db, tenant_id)
    lead_by_contact = await _load_lead_by_contact(db, tenant_id)
    email_by_user = await _load_email_by_user(db, tenant_id)

    conversations = []
    for conversation, contact in rows:
        last_message_text = await db.scalar(
            select(Message.text)
            .where(Message.tenant_id == tenant_id, Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        conversations.append(
            _serialize_conversation(
                conversation,
                contact,
                last_message_text=last_message_text,
                tags=tags_by_conversation.get(conversation.id, []),
                lead=lead_by_contact.get(contact.id),
                assigned_user_email=email_by_user.get(conversation.assigned_user_id),
            )
        )
    return conversations


@router.get("/team-members", response_model=list[TeamMemberOut])
async def list_team_members(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    result = await db.scalars(
        select(User).where(User.tenant_id == tenant_id).order_by(User.email)
    )
    return [TeamMemberOut(id=u.id, email=u.email, role=u.role.value) for u in result]


@router.patch("/conversations/{conversation_id}/crm", response_model=ConversationOut)
async def update_conversation_crm(
    conversation_id: UUID,
    payload: ConversationCrmUpdateIn,
    db: DbSession,
    tenant_id: TenantId,
    _user: CurrentUser,
):
    """Only fields actually present in the request body are applied -- a
    client sending just {"lead_notes": "..."} must not clear an already-set
    assigned_user_id or lead_status."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    fields_set = payload.model_fields_set

    if "assigned_user_id" in fields_set:
        if payload.assigned_user_id is not None:
            assignee = await db.scalar(
                select(User.id).where(
                    User.id == payload.assigned_user_id, User.tenant_id == tenant_id
                )
            )
            if assignee is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="That team member doesn't belong to this business.",
                )
        conversation.assigned_user_id = payload.assigned_user_id

    if "lead_status" in fields_set or "lead_notes" in fields_set:
        lead = await db.scalar(
            select(Lead).where(Lead.tenant_id == tenant_id, Lead.contact_id == conversation.contact_id)
        )
        if lead is None:
            lead = Lead(tenant_id=tenant_id, contact_id=conversation.contact_id)
            db.add(lead)

        if "lead_status" in fields_set:
            if payload.lead_status not in LeadStatus.__members__:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lead status."
                )
            lead.status = LeadStatus(payload.lead_status)
        if "lead_notes" in fields_set:
            lead.notes = payload.lead_notes

    await db.commit()
    return await _fetch_conversation_out(db, tenant_id=tenant_id, conversation_id=conversation_id)


@router.post(
    "/conversations/{conversation_id}/tags",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_conversation_tag(
    conversation_id: UUID, payload: TagIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    tag = payload.tag.strip()
    if not tag:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag can't be empty.")

    current_tags = await db.scalars(
        select(ConversationTag.tag).where(
            ConversationTag.tenant_id == tenant_id,
            ConversationTag.conversation_id == conversation_id,
        )
    )
    if len(list(current_tags)) >= MAX_TAGS_PER_CONVERSATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A conversation can have at most {MAX_TAGS_PER_CONVERSATION} tags.",
        )

    db.add(ConversationTag(tenant_id=tenant_id, conversation_id=conversation_id, tag=tag))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # tag already exists -- adding it again is a no-op, not an error

    return await _fetch_conversation_out(db, tenant_id=tenant_id, conversation_id=conversation_id)


@router.delete(
    "/conversations/{conversation_id}/tags/{tag}",
    response_model=ConversationOut,
)
async def remove_conversation_tag(
    conversation_id: UUID, tag: str, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    existing = await db.scalar(
        select(ConversationTag).where(
            ConversationTag.tenant_id == tenant_id,
            ConversationTag.conversation_id == conversation_id,
            ConversationTag.tag == tag,
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.commit()

    return await _fetch_conversation_out(db, tenant_id=tenant_id, conversation_id=conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: UUID, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.tenant_id == tenant_id)
        .order_by(Message.created_at.asc())
    )
    return [
        MessageOut(
            id=m.id,
            direction=m.direction.value,
            type=m.type.value,
            text=m.text,
            audio_url=m.audio_url,
            created_at=m.created_at,
        )
        for m in result
    ]


@router.post(
    "/conversations/{conversation_id}/reply",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_conversation(
    conversation_id: UUID, payload: ReplyIn, db: DbSession, tenant_id: TenantId, _user: CurrentUser
):
    """A human sending a manual reply takes the conversation over -- the
    worker's handoff-is-sacred rule already skips auto-replying once status
    is 'human', so setting it here is what stops the AI going forward."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if not is_within_service_window(conversation):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outside the 24-hour service window -- can't send a free-form reply.",
        )

    whatsapp_config = await db.scalar(
        select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant_id)
    )
    if whatsapp_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect a WhatsApp number in Agent Settings first.",
        )

    contact = await db.scalar(
        select(Contact).where(Contact.id == conversation.contact_id, Contact.tenant_id == tenant_id)
    )
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    access_token = decrypt_secret(whatsapp_config.access_token_encrypted)
    try:
        await meta.send_text_message(
            phone_number_id=whatsapp_config.phone_number_id,
            access_token=access_token,
            to=contact.phone,
            body=payload.text,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WhatsApp send failed. Check Connection Status and the recipient number.",
        )

    message = Message(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        direction=MessageDirection.outbound,
        type=MessageType.text,
        text=payload.text,
    )
    db.add(message)
    conversation.status = ConversationStatus.human
    await db.commit()
    await db.refresh(message)

    return MessageOut(
        id=message.id,
        direction=message.direction.value,
        type=message.type.value,
        text=message.text,
        audio_url=message.audio_url,
        created_at=message.created_at,
    )


@router.get("/leads", response_model=list[LeadOut])
async def list_leads(db: DbSession, tenant_id: TenantId, _user: CurrentUser):
    result = await db.execute(
        select(Lead, Contact)
        .join(Contact, Lead.contact_id == Contact.id)
        .where(Lead.tenant_id == tenant_id, Contact.tenant_id == tenant_id)
        .order_by(Lead.created_at.desc())
    )
    return [
        LeadOut(
            id=lead.id,
            intent=lead.intent,
            status=lead.status.value,
            notes=lead.notes,
            value=float(lead.value) if lead.value is not None else None,
            contact=ContactOut(id=contact.id, phone=contact.phone, name=contact.name),
            created_at=lead.created_at,
        )
        for lead, contact in result.all()
    ]


def _serialize_conversation(
    conversation: Conversation,
    contact: Contact,
    *,
    last_message_text: str | None,
    tags: list[str],
    lead: Lead | None,
    assigned_user_email: str | None,
) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        status=conversation.status.value,
        last_inbound_at=conversation.last_inbound_at,
        contact=ContactOut(id=contact.id, phone=contact.phone, name=contact.name),
        last_message_text=last_message_text,
        updated_at=conversation.updated_at,
        assigned_user_id=conversation.assigned_user_id,
        assigned_user_email=assigned_user_email,
        tags=tags,
        lead_status=lead.status.value if lead is not None else None,
        lead_notes=lead.notes if lead is not None else None,
    )


async def _load_tags_by_conversation(db, tenant_id) -> dict[UUID, list[str]]:
    result = await db.execute(
        select(ConversationTag.conversation_id, ConversationTag.tag).where(
            ConversationTag.tenant_id == tenant_id
        )
    )
    tags_by_conversation: dict[UUID, list[str]] = {}
    for conversation_id, tag in result.all():
        tags_by_conversation.setdefault(conversation_id, []).append(tag)
    return tags_by_conversation


async def _load_lead_by_contact(db, tenant_id) -> dict[UUID, Lead]:
    result = await db.scalars(select(Lead).where(Lead.tenant_id == tenant_id))
    return {lead.contact_id: lead for lead in result}


async def _load_email_by_user(db, tenant_id) -> dict[UUID, str]:
    result = await db.execute(
        select(User.id, User.email).where(User.tenant_id == tenant_id)
    )
    return {user_id: email for user_id, email in result.all()}


async def _fetch_conversation_out(db, *, tenant_id, conversation_id: UUID) -> ConversationOut:
    row = (
        await db.execute(
            select(Conversation, Contact)
            .join(Contact, Conversation.contact_id == Contact.id)
            .where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conversation, contact = row

    last_message_text = await db.scalar(
        select(Message.text)
        .where(Message.tenant_id == tenant_id, Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    tags = list(
        await db.scalars(
            select(ConversationTag.tag).where(
                ConversationTag.tenant_id == tenant_id,
                ConversationTag.conversation_id == conversation.id,
            )
        )
    )
    lead = await db.scalar(
        select(Lead).where(Lead.tenant_id == tenant_id, Lead.contact_id == contact.id)
    )
    assigned_user_email = None
    if conversation.assigned_user_id is not None:
        assigned_user_email = await db.scalar(
            select(User.email).where(User.id == conversation.assigned_user_id)
        )

    return _serialize_conversation(
        conversation,
        contact,
        last_message_text=last_message_text,
        tags=tags,
        lead=lead,
        assigned_user_email=assigned_user_email,
    )
