"""Plain linear RAG pipeline -- no LangGraph in v1 (CLAUDE.md). Chunk with a
token-aware splitter, embed via services/llm.py, retrieve top-k chunks
filtered by tenant_id, and let deleting a Document cascade-delete its chunks
at the DB level so retrieval forgets it immediately."""

import uuid

import tiktoken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.llm import embed_texts

_ENCODER = tiktoken.get_encoding("cl100k_base")

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
TOP_K = 5
# Calibrated against a real tenant's knowledge base + real customer phrasing:
# on-topic queries (even with typos) scored 0.44-0.54 cosine distance against
# the right chunk, genuinely unrelated queries scored 0.86+. 0.45 was
# rejecting most real on-topic questions as false negatives.
MAX_COSINE_DISTANCE = 0.65


def chunk_text(
    text: str, *, chunk_size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS
) -> list[str]:
    tokens = _ENCODER.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(_ENCODER.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - overlap
    return chunks


async def ingest_document(
    *,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document: Document,
    text: str,
    embedding_model: str,
    api_key: str,
) -> int:
    """Chunk, embed, and store a document's text. Returns the chunk count."""
    pieces = chunk_text(text)
    if not pieces:
        document.status = DocumentStatus.failed
        await db.flush()
        return 0

    vectors = await embed_texts(model=embedding_model, api_key=api_key, texts=pieces)
    for content, vector in zip(pieces, vectors):
        db.add(
            Chunk(tenant_id=tenant_id, document_id=document.id, content=content, embedding=vector)
        )

    document.status = DocumentStatus.ready
    await db.flush()
    return len(pieces)


async def delete_document(*, db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID) -> None:
    """Chunks cascade-delete via chunks.document_id ondelete=CASCADE --
    retrieval stops seeing this document's content immediately."""
    await db.execute(
        delete(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
    )
    await db.commit()


async def retrieve_chunks(
    *,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    embedding_model: str,
    api_key: str,
    top_k: int = TOP_K,
    max_cosine_distance: float = MAX_COSINE_DISTANCE,
) -> list[str]:
    """Top-k nearest chunks for this tenant only. Never call this without
    the tenant_id filter -- vector search without it is a bug, always
    (CLAUDE.md rule 1)."""
    vectors = await embed_texts(model=embedding_model, api_key=api_key, texts=[query])
    query_vector = vectors[0]

    distance = Chunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk.content)
        .where(Chunk.tenant_id == tenant_id)
        .where(distance <= max_cosine_distance)
        .order_by(distance)
        .limit(top_k)
    )
    result = await db.scalars(stmt)
    return list(result)
