# WhatsApp AI Receptionist

Read [CLAUDE.md](CLAUDE.md) first, then [WHATSAPP_AI_RECEPTIONIST_DOCS.md](WHATSAPP_AI_RECEPTIONIST_DOCS.md)
for the full spec. Planning history lives in the `my-brain` Obsidian vault
(`wiki/ideas/WhatsApp AI Receptionist.md` and linked concept pages) — this repo
only holds buildable code and the spec snapshot it was built from. The
message-flow, memory, and future Google/Cal.com module plan is in
[docs/MESSAGE_FLOW_AND_INTEGRATIONS.md](docs/MESSAGE_FLOW_AND_INTEGRATIONS.md).

## Local setup -- backend

1. Copy `.env.example` to `.env` and fill in secrets (Meta app secret/verify
   token, OpenAI/Gemini API key, JWT secret, Fernet key). A hosted Postgres
   (Supabase/Neon/Railway) + hosted Redis (Upstash) work fine in place of
   Docker Compose -- just point `DATABASE_URL`/`REDIS_URL` at them.
2. `docker compose up -d postgres redis` (or use hosted services instead)
3. Create a virtualenv and `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `uvicorn app.main:app --reload` (API) and, in a second terminal,
   `arq app.worker.worker_settings.WorkerSettings` (background worker)

Or run everything in containers: `docker compose up --build`.

## Local setup -- frontend

```
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:3000`. `frontend/.env.local` points it at the API
(`NEXT_PUBLIC_API_URL`, defaults to `http://127.0.0.1:8000`). The backend's
CORS config in `app/main.py` allows `http://localhost:3000` specifically --
update both if you change the frontend port.

Pages: `/login`, `/signup`, `/dashboard/status` (connection health and test
conversation), `/dashboard/knowledge` (upload/list/delete documents),
`/dashboard/settings` (WhatsApp, LLM, behavior, and memory config),
`/dashboard/conversations` (chat list + thread view).

## Trying it end to end

1. Sign up via the frontend (`/signup`) or `POST /auth/signup` directly.
2. In **Agent Settings**, save an LLM API key (required before uploading
   documents) and, once you have a Meta test number, the WhatsApp connection
   fields. `scripts/seed_dev_tenant.py` does the same thing from the CLI if
   you'd rather not use the UI.
3. Upload FAQ text in **Knowledge Base**; delete it to confirm the bot
   forgets it (RAG delete test).
4. Point Meta's webhook at `https://<your-tunnel>/webhook/whatsapp` (ngrok/
   Cloudflare Tunnel for local dev) using `META_VERIFY_TOKEN` from `.env`.
5. Message the test number -- replies come from the uploaded knowledge via
   RAG, or a handoff message if nothing relevant was found. Voice notes are
   transcribed (Whisper) and answered through the same RAG pipeline as typed
   messages. Conversations and their status show up in **Conversations**,
   where you can also take over a conversation with a manual reply.

## Status

Week 1 done (webhook round-trip, DB schema), Week 2 done (RAG ingest/
retrieve/delete via pgvector, documents API), Week 3 done (dashboard: auth,
conversations, knowledge base, agent settings, connection status). Week 4
in progress: voice-note transcription done (Whisper via LiteLLM, falls back
gracefully on unsupported audio/transcription failure) and human takeover
done (`POST /conversations/{id}/reply`); leads-as-CRM-fields and owner
notifications still open. Production hardening (Week 5) still open --
notably, a failed WhatsApp send (bad/expired token) is now caught and
logged rather than crashing the job, but there's still no retry/backoff or
alerting when that happens. See CLAUDE.md's "Build order" section.

Tests: `pytest` (needs Postgres+pgvector and the schema migrated).
`test_24h_window_*` are pure-logic and don't need a DB. Backend has been
smoke-tested end-to-end against a real Supabase (Postgres+pgvector) +
Upstash (Redis) setup, including a full auth → knowledge base → settings →
conversations round trip through the actual frontend.
