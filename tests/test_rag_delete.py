from app.models.document import Document
from app.models.tenant import Tenant
from app.services import rag


async def test_rag_delete(db_session, monkeypatch):
    """CLAUDE.md required test: delete doc -> its content absent from
    retrieval results."""

    async def fake_embed_texts(*, model, api_key, texts):
        return [[0.1] * 1536 for _ in texts]

    monkeypatch.setattr(rag, "embed_texts", fake_embed_texts)

    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    document = Document(tenant_id=tenant.id, title="Pricing FAQ")
    db_session.add(document)
    await db_session.flush()

    await rag.ingest_document(
        db=db_session, tenant_id=tenant.id, document=document,
        text="A consultation costs 2000 rupees and includes a follow-up visit.",
        embedding_model="text-embedding-3-small", api_key="sk-test",
    )
    await db_session.commit()

    before = await rag.retrieve_chunks(
        db=db_session, tenant_id=tenant.id, query="How much is a consultation?",
        embedding_model="text-embedding-3-small", api_key="sk-test", top_k=10,
    )
    assert any("2000 rupees" in chunk for chunk in before)

    await rag.delete_document(db=db_session, tenant_id=tenant.id, document_id=document.id)

    after = await rag.retrieve_chunks(
        db=db_session, tenant_id=tenant.id, query="How much is a consultation?",
        embedding_model="text-embedding-3-small", api_key="sk-test", top_k=10,
    )
    assert all("2000 rupees" not in chunk for chunk in after)


async def test_rag_rejects_weak_matches(db_session, monkeypatch):
    async def fake_embed_texts(*, model, api_key, texts):
        if texts == ["Do you repair laptops?"]:
            return [[-1.0] + [0.0] * 1535]
        return [[1.0] + [0.0] * 1535 for _ in texts]

    monkeypatch.setattr(rag, "embed_texts", fake_embed_texts)

    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    document = Document(tenant_id=tenant.id, title="Clinic Timings")
    db_session.add(document)
    await db_session.flush()

    await rag.ingest_document(
        db=db_session,
        tenant_id=tenant.id,
        document=document,
        text="The clinic is open 9am to 5pm for eye appointments.",
        embedding_model="text-embedding-3-small",
        api_key="sk-test",
    )
    await db_session.commit()

    results = await rag.retrieve_chunks(
        db=db_session,
        tenant_id=tenant.id,
        query="Do you repair laptops?",
        embedding_model="text-embedding-3-small",
        api_key="sk-test",
    )

    assert results == []
