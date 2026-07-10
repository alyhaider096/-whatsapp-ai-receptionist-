from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TenantId
from app.core.security import decrypt_secret
from app.models.document import Document
from app.models.llm_config import LLMConfig
from app.schemas.document import DocumentCreateRequest, DocumentOut
from app.services import rag

router = APIRouter(prefix="/documents", tags=["documents"])


async def _get_embedding_api_key(db: DbSession, tenant_id: UUID) -> str:
    llm_config = await db.scalar(select(LLMConfig).where(LLMConfig.tenant_id == tenant_id))
    if llm_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add an LLM API key before uploading knowledge documents.",
        )
    return decrypt_secret(llm_config.api_key_encrypted)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreateRequest, db: DbSession, tenant_id: TenantId, _user: CurrentUser
) -> Document:
    api_key = await _get_embedding_api_key(db, tenant_id)
    settings = get_settings()

    document = Document(tenant_id=tenant_id, title=payload.title, source_type="txt")
    db.add(document)
    await db.flush()

    await rag.ingest_document(
        db=db,
        tenant_id=tenant_id,
        document=document,
        text=payload.text,
        embedding_model=settings.default_embedding_model,
        api_key=api_key,
    )
    await db.commit()
    await db.refresh(document)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: DbSession, tenant_id: TenantId, _user: CurrentUser) -> list[Document]:
    result = await db.scalars(select(Document).where(Document.tenant_id == tenant_id))
    return list(result)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID, db: DbSession, tenant_id: TenantId, _user: CurrentUser
) -> None:
    await rag.delete_document(db=db, tenant_id=tenant_id, document_id=document_id)
