# AGENTS.md — WhatsApp AI Receptionist

Project rules for Codex. Read before writing any code.
Full spec lives in WHATSAPP_AI_RECEPTIONIST_DOCS.md — follow it; don't re-decide settled choices.

## Stack (fixed — do not substitute)
- Backend: FastAPI (async) + SQLAlchemy 2.0 async + Alembic + Pydantic v2
- DB: PostgreSQL 16 + pgvector (NO external vector DB)
- Queue: Redis + ARQ (NO Celery)
- LLM: LiteLLM library, per-tenant keys; embeddings = text-embedding-3-small (1536)
- Frontend: Next.js 14 App Router + Tailwind + shadcn/ui
- NO LangGraph in v1. The RAG pipeline is plain linear Python.

## Non-negotiable rules
1. **Tenant isolation.** Every table has tenant_id. Every query filters by it.
   tenant_id comes from the JWT via deps.get_tenant — NEVER from request body.
   Vector search without a tenant_id filter is a bug, always.
2. **Webhook speed.** POST /webhook/whatsapp must: verify X-Hub-Signature-256,
   dedup on wa_message_id (unique constraint), store raw payload, enqueue ARQ
   job, return 200. Total < 1s. No LLM/embedding/HTTP calls in the webhook.
3. **Idempotency.** Meta retries deliveries. Duplicate wa_message_id = skip
   silently. Jobs must be safe to run twice.
4. **Secrets.** All API keys and Meta tokens Fernet-encrypted at rest
   (security.py). Never log decrypted values. Display masked (sk-...4f2a).
5. **24h window.** Before any outbound send, check conversation.last_inbound_at
   is within 24h. Outside window: block, surface a clear error to the UI.
6. **Handoff is sacred.** If conversation.status in (needs_human, human),
   the worker must NOT auto-reply. Ever.
7. **Async everywhere.** No sync DB calls, no requests library — use httpx.

## Conventions
- IDs: UUID v4. Timestamps: TIMESTAMPTZ, UTC.
- One SQLAlchemy model file per domain in app/models/.
- Routers thin; logic in app/services/; background work in app/worker/jobs.py.
- All Meta Cloud API calls go through services/meta.py — nowhere else.
- All LLM calls go through services/llm.py (LiteLLM) — nowhere else.
- Parse webhook payloads against REAL captured JSON in tests/payloads/,
  not doc examples. Path: entry[0].changes[0].value.messages[0].
- Route inbound to tenant by value.metadata.phone_number_id.
- Migrations: alembic revision --autogenerate, then review by hand.

## Required tests (write alongside features, not after)
- test_webhook_dedup: same wa_message_id twice → one job, one reply
- test_tenant_isolation: tenant A can never retrieve tenant B's chunks/messages
- test_rag_delete: delete doc → its content absent from retrieval results
- test_24h_window: reply blocked when last_inbound_at > 24h ago
- test_handoff_stops_ai: needs_human conversation gets no auto-reply

## Build order (vertical slices — finish end-to-end before widening)
1. Webhook round-trip with hardcoded reply (Week 1)
2. RAG: upload .txt → answer from it → delete → forgets (Week 2)
3. Dashboard: auth, chats, knowledge, agent settings, LLM keys (Week 3)
4. Handoff + voice notes + leads + connection status page (Week 4)
5. Hardening + deploy + first client (Weeks 5–6)

## Out of scope for v1 (do not build even if it seems easy)
Embedded Signup · billing · outbound campaigns/templates · team roles ·
booking/tool-calling · Shopify/Sheets integrations · AI voice replies ·
WebSockets (polling is fine)
