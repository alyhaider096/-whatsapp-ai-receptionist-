from app.models.tenant import Tenant
from app.services import rag


async def test_tenant_isolation(db_session, monkeypatch):
    """CLAUDE.md required test: tenant A can never retrieve tenant B's
    chunks/messages, even when both have near-identical content."""

    async def fake_embed_texts(*, model, api_key, texts):
        # Deterministic fake vectors -- content/order doesn't matter here,
        # only that retrieval is filtered by tenant_id.
        return [[0.1] * 1536 for _ in texts]

    monkeypatch.setattr(rag, "embed_texts", fake_embed_texts)

    tenant_a = Tenant(name="Clinic A")
    tenant_b = Tenant(name="Clinic B")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    from app.models.document import Document

    doc_a = Document(tenant_id=tenant_a.id, title="Clinic A FAQ")
    doc_b = Document(tenant_id=tenant_b.id, title="Clinic B FAQ")
    db_session.add_all([doc_a, doc_b])
    await db_session.flush()

    await rag.ingest_document(
        db=db_session, tenant_id=tenant_a.id, document=doc_a,
        text="Clinic A is open 9am to 5pm and offers dental checkups.",
        embedding_model="text-embedding-3-small", api_key="sk-test",
    )
    await rag.ingest_document(
        db=db_session, tenant_id=tenant_b.id, document=doc_b,
        text="Clinic B is open 10am to 6pm and offers eye exams.",
        embedding_model="text-embedding-3-small", api_key="sk-test",
    )
    await db_session.commit()

    results_a = await rag.retrieve_chunks(
        db=db_session, tenant_id=tenant_a.id, query="What are your timings?",
        embedding_model="text-embedding-3-small", api_key="sk-test", top_k=10,
    )
    results_b = await rag.retrieve_chunks(
        db=db_session, tenant_id=tenant_b.id, query="What are your timings?",
        embedding_model="text-embedding-3-small", api_key="sk-test", top_k=10,
    )

    assert any("Clinic A" in chunk for chunk in results_a)
    assert all("Clinic B" not in chunk for chunk in results_a)
    assert any("Clinic B" in chunk for chunk in results_b)
    assert all("Clinic A" not in chunk for chunk in results_b)
