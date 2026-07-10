# WhatsApp AI Receptionist — Full Spec

This is the spec referenced by CLAUDE.md in this folder. It is self-contained
(no wiki-only links) so it survives being copied into a standalone repo.
Sources: two planning conversations (2026-07-06, 2026-07-07) and the
my-brain wiki pages under wiki/concepts/ and wiki/ideas/WhatsApp AI Receptionist.md.

## 1. Product vision & positioning

"We connect your official WhatsApp Business API to an AI assistant trained on
your business data. It answers inbound customer messages, handles voice notes,
captures leads, and alerts a human when needed."

Sell missed-lead recovery and faster response time, not "an AI chatbot." The
target buyer doesn't care about RAG, FastAPI, or vector DBs — they care that
customers message at night, nobody replies, and leads are lost.

**First niche:** clinics and service businesses (salons, real estate agents,
coaching institutes, small e-commerce, travel agents). Scope strictly to FAQs,
appointments, pricing, timings, location, and lead qualification. No medical
diagnosis or regulated advice — escalate those to a human.

**Build shape:** done-for-you agency service first. Manually onboard clients
until 3–5 are paying and the setup process is proven repeatable. Only then
invest in self-serve SaaS (Embedded Signup, billing, multi-tenant onboarding
UI). Multi-tenancy is still built into the data model from day one
(`tenant_id` everywhere) — only the *onboarding process* stays manual early on.

## 2. Scope for v1

**In scope:**
- Official WhatsApp Cloud API inbound webhook + reply within the 24h window
- RAG over uploaded business knowledge (text first, PDF if time remains)
- Prompt-based behavior/tone/handoff-rule configuration per tenant
- Human handoff with owner notification (email/Telegram/dashboard)
- Voice-note transcription (Whisper/Gemini) feeding the same RAG pipeline
- Basic CRM: contacts, conversations, lead status, notes, summaries
- Dashboard: login, conversations, knowledge base, agent settings, connection
  status
- Production hardening: webhook dedup, retries, rate limiting, logs, Sentry,
  backups, audit logs

**Out of scope for v1 (do not build even if it looks easy):**
Embedded Signup, billing, outbound campaigns/template marketing, team roles,
booking/tool-calling, Shopify/Sheets integrations, AI voice replies,
WebSockets (polling is fine), complex CRM, LangGraph.

## 3. Architecture

Stack: FastAPI (async) + SQLAlchemy 2.0 async + Alembic + Pydantic v2 ·
PostgreSQL 16 + pgvector · Redis + ARQ (not Celery) · LiteLLM (per-tenant
keys) · text-embedding-3-small (1536 dim) · Whisper/Gemini for audio ·
Next.js 14 App Router + Tailwind + shadcn/ui · Railway/Render first, VPS
later · Sentry + structured logs.

```
Customer sends WhatsApp message
        |
Meta webhook -> FastAPI POST /webhook/whatsapp
        |  verify X-Hub-Signature-256
        |  dedup on wa_message_id (unique constraint)
        |  store raw payload
        |  enqueue ARQ job
        |  return 200  (< 1s total, no LLM/HTTP calls inline)
        v
ARQ worker job
        |  normalize message (text / voice / image / document)
        |  if voice -> transcribe (Whisper/Gemini)
        |  classify intent (FAQ / booking / lead / complaint / human)
        |  if conversation.status in (needs_human, human) -> STOP, no auto-reply
        |  check last_inbound_at within 24h, else block + surface error
        |  retrieve top-5 chunks from tenant's pgvector knowledge base
        |  LLM (LiteLLM) generates answer from retrieved chunks only
        |  guardrail: no reliable source -> ask clarifying question or handoff
        |  send reply via WhatsApp Cloud API (services/meta.py)
        |  persist message, lead status, summary, usage/cost log
```

The webhook must never block on RAG/LLM/HTTP work — Meta retries slow or
failed webhooks, and duplicate work must be idempotent either way.

## 4. Data model

Every table below carries `tenant_id` (UUID v4); every query filters by it.
Timestamps are `TIMESTAMPTZ`, UTC.

- `tenants` — id, name, plan, settings
- `users` — id, tenant_id, email, role, password_hash
- `whatsapp_configs` — tenant_id, waba_id, phone_number_id, encrypted access
  token, status
- `llm_configs` — tenant_id, provider, encrypted api key, model choice
- `contacts` — tenant_id, phone, name, language_pref
- `conversations` — tenant_id, contact_id, status (open/needs_human/human/
  closed), last_inbound_at
- `messages` — tenant_id, conversation_id, wa_message_id (unique), direction,
  type, text, audio_url, tokens_used, created_at
- `documents` — tenant_id, title, source_type, status
- `chunks` — tenant_id, document_id, content, embedding vector(1536),
  metadata JSONB
- `leads` — tenant_id, contact_id, intent, status, notes, value
- `handoff_events` — tenant_id, conversation_id, reason, created_at
- `usage_logs` — tenant_id, message count, tokens, transcription minutes, cost
- `audit_logs` — tenant_id, user_id, action, target, created_at

Rules: deleting a document must cascade-delete its chunks so retrieval stops
seeing it immediately. `wa_message_id` uniqueness is what makes the webhook
job idempotent against Meta's retried deliveries.

## 5. Meta / WhatsApp integration plan

**Phase 1 — test number (Week 1).** Create Meta Developer account and Business
app, add the WhatsApp product, get a test phone number ID, add your own phone
as a test recipient, build and verify the FastAPI webhook, subscribe to the
messages webhook, receive a message, send a reply.

**Phase 2 — first real client, manual (Weeks 6–8).** Onboard on a call using
the client's own Meta/Facebook access — never ask for their password. Prefer
a new unused phone number where possible; an existing WhatsApp Business App
number may need migration/coexistence handling, which is more fragile.

**Phase 3 — Embedded Signup (deferred, months 4–6, out of scope for v1).**
Client clicks "Connect WhatsApp" in the dashboard, logs in via Meta/Facebook
themselves, selects/creates a business portfolio + WABA, verifies their phone
number, and Meta returns an authorization code that the backend exchanges for
WABA/phone details before subscribing webhooks. Production Embedded Signup
requires Meta App Review and advanced permissions: `business_management` and
`whatsapp_business_management`. Do not start this before 3–5 paying clients —
it is a multi-week distraction before the product is proven to sell.

**24-hour service window.** A customer-initiated message opens a 24h window
during which normal (non-template) replies are allowed. Track
`conversation.last_inbound_at`; block free-form replies outside the window
and surface a clear error in the UI rather than silently failing or trying a
template send.

**AI policy positioning.** Meta restricts general-purpose AI assistants on
WhatsApp more than business-specific customer support automation. Stay
strictly in the latter category: answer only from the tenant's own business
knowledge, with mandatory human handoff paths — never position this as "put
ChatGPT on WhatsApp for anything."

**Pricing change to plan around.** Meta's published pricing has treated
non-template/service-window replies as free, but Meta's own upcoming pricing
page states that **from October 1, 2026, service messages will be charged
per message.** Never promise clients "free WhatsApp replies forever" — pass
through Meta/LLM/transcription costs or apply a fair-use limit.

## 6. RAG design

Prompt controls behavior (tone, scope, safety, handoff rules); RAG supplies
business facts. Do not put all business data in one giant prompt — required
once a client has more than a tiny, static FAQ, or once document deletion and
per-tenant isolation matter.

Pipeline: clean text → detect language → classify intent → retrieve top 5
chunks for the tenant → generate an answer that only uses retrieved content →
if no reliable chunk is found, ask a clarifying question or hand off. No
LangGraph in v1 — this is plain linear Python. Add LangGraph later only if
appointment booking, multi-step forms, or tool-calling are actually built.

Per-tenant business config (drives the system prompt): business name, tone,
languages, services, prices, locations, timings, booking rules, questions the
AI can/cannot answer, human handoff triggers, emergency/disclaimer rules,
lead fields to collect.

Common mistakes to avoid: letting the AI answer when retrieval found nothing,
forgetting to delete vectors when a document is removed, mixing tenant
knowledge in retrieval, and trusting model confidence over actual source
quality.

## 7. Handoff design

Handoff triggers: user asks for a human/agent/real person/callback; user is
angry or confused; the question is medical/legal/financial/regulated beyond
the FAQ; retrieval has no reliable answer; booking/payment/complaint needs a
person.

When triggered: the AI sends one message ("I'm connecting you with a team
member. Please wait a moment."), the conversation status becomes
`needs_human`, and the worker must not auto-reply again — this is
non-negotiable regardless of what a later message contains. Notify the owner
via email, Telegram, or the dashboard (WhatsApp-to-owner notification and SMS
are later, template-rule and cost-sensitive additions).

## 8. Voice notes

Flow: download media from Meta → transcribe (Whisper or Gemini) → store the
transcript as an incoming message → run the normal RAG pipeline → reply in
text (not AI voice — that's out of scope for v1).

Known risks: mistranscription, background noise, Urdu/Roman Urdu/English
code-switching, added cost and latency. Fallback line: "I'm not fully sure I
understood the voice note. Can you please type your question or wait while I
connect you with a person?"

## 9. CRM / dashboard tiers

**v1 (build now):** contact list, lead status (new/qualified/needs_human/
booked/lost), intent tag, conversation summary, handoff flag, message counts,
low-confidence flag, search by phone/name/message, connection status page
(WhatsApp token, webhook last-seen, LLM key health).

**v2 (after first paying clients):** team members, internal notes, manual
human reply from the dashboard, canned replies, CSV export, Google
Sheets/Calendar sync, analytics dashboard.

**v3 (SaaS phase):** multi-branch businesses, role permissions, SLA alerts,
billing, white-label agency accounts, Shopify/HubSpot/Pipedrive integrations.

## 10. Security & compliance

- Tenant isolation is the #1 risk: every table has `tenant_id`; every query,
  including vector search, filters by it; `tenant_id` comes from the JWT via
  `deps.get_tenant`, never from the request body.
- All API keys and Meta tokens Fernet-encrypted at rest (`security.py`);
  never log decrypted values; display masked in the UI (e.g. `sk-...4f2a`).
- Verify `X-Hub-Signature-256` on every webhook call; dedup on `wa_message_id`.
- Audit log table for config changes, exports, and admin actions.
- PII minimization: store phone, name, conversation — nothing beyond what's
  needed; a consent line in the first AI message is good practice for
  health-adjacent (clinic) data.
- WhatsApp's Business Solution Terms require third-party providers to process
  Business Solution Data only on the client's behalf and per their
  instructions, with reasonable safeguards — this shapes the privacy policy
  and data-handling story before onboarding real clients.

## 11. Pricing

**Local (Pakistan):**
| Package | Setup | Monthly |
|---|---|---|
| Starter | PKR 50k–100k | PKR 15k–35k |
| Growth | PKR 100k–200k | PKR 35k–75k |
| Custom | PKR 200k+ | PKR 75k+ |

**International:**
| Package | Setup | Monthly |
|---|---|---|
| Basic AI FAQ bot | $300–$700 | $79–$199 |
| AI receptionist + CRM | $800–$2,000 | $199–$499 |
| Custom automation | $2,000+ | $500+ |

Never promise unlimited free usage. Standard line: "Includes fair-use AI
replies (e.g. 1,000/month). Meta WhatsApp, LLM, transcription, and hosting
overages billed separately or passed through at cost."

**Competitive positioning:** Wati, respond.io, Interakt, Chatwoot, Manychat,
Gupshup, and SleekFlow all offer AI-assisted WhatsApp inboxes with knowledge-
base answers and routing. The differentiator here isn't a bigger feature
list — it's personal setup, tuning on the client's real data, and working
Urdu/Roman Urdu/English code-switching well, which off-the-shelf tools handle
poorly for this market.

## 12. Biggest risks

1. Meta app review can gate SaaS growth (privacy policy, data deletion URL,
   demo video, permission justification, business verification).
2. Clients often don't know who controls their Facebook Page, Business
   Manager, or WhatsApp number — expect this to be a service bottleneck.
3. Migrating an existing WhatsApp Business App number to Cloud API can be
   fragile depending on coexistence support at onboarding time.
4. Hallucination: mitigate with retrieval-only answering, "I don't know"
   fallback, human handoff, and refusing to answer without a source chunk.
5. Data privacy: encrypted tokens, tenant isolation, audit logs, deletion
   support, no training on client data without explicit consent.
6. The October 1, 2026 WhatsApp service-message pricing change — build
   pass-through cost language into contracts now, not later.
7. Competitive pressure from established WhatsApp CRM tools — win on
   personalization and local-language quality, not feature count.

## 13. Milestone timeline

- **Week 1 (Jul 6–12, 2026) — Foundation.** Repo, Docker Compose, FastAPI,
  Postgres/pgvector, Redis, migrations, auth. Meta dev app + test number.
  Webhook verify/receive/store/hardcoded-reply. Exit: 50 test messages
  round-trip, no duplicate replies.
- **Week 2 (Jul 13–19) — RAG v1.** TXT upload, chunk/embed/store, top-5
  retrieval, strict "answer only from business knowledge" prompt, document
  deletion proven to forget. Exit: answers 30 FAQs, refuses unknowns.
- **Week 3 (Jul 20–26) — Dashboard v1.** Login, conversations, knowledge
  base, agent settings, connection status; encrypted LLM key storage;
  WhatsApp config screen. Exit: fully configurable from the UI, no DB edits.
- **Week 4 (Jul 27–Aug 2) — Handoff + Voice.** Handoff triggers, stop-AI +
  owner notification, voice-note transcription into RAG, 24h window
  enforcement. Exit: text, voice, handoff, human takeover all work together.
- **Week 5 (Aug 3–9) — Production hardening.** Webhook dedup, retries, rate
  limiting, structured logs, Sentry, backups, audit logs, usage/cost
  tracking, deploy with HTTPS domain. Exit: 7-day soak test, stable.
- **Weeks 6–8 (Aug 10–30) — First paid client.** Manual onboarding, client-
  owned Meta access, upload real business knowledge, test 100 real
  questions before going live, daily monitoring for two weeks. Exit: one
  paying client with before/after metrics and a testimonial.
- **Month 3 (Sep 2026) — Productized agency.** Onboarding questionnaire,
  clinic FAQ template, deployment SOP, weekly report template, CSV export,
  better lead status. Sell to 3–5 similar businesses. Exit: repeatable setup,
  recurring revenue.
- **Months 4–6 (Oct–Dec 2026) — SaaS beta, only if proven.** Embedded
  Signup, app review, privacy policy, data deletion URL, billing, usage
  limits, team inbox, template messages if needed. Exit: self-serve
  WhatsApp connection, agency onboarding still available.

## 14. Test plan

Mirrors CLAUDE.md's required tests, plus broader QA:
- Webhook signature verification, malformed payloads, duplicate Meta
  retries (dedup on `wa_message_id`).
- 24h service window enforcement; blocked late free-form replies surface a
  clear UI error.
- RAG correctness, unknown-question refusal, deleted-document removal.
- Tenant isolation: tenant A never retrieves tenant B's chunks or messages.
- Handoff stops AI immediately and alerts the owner.
- Voice-note transcription fallback wording when audio is unclear.
- Invalid/expired Meta token and invalid LLM key handling, surfaced on the
  connection status page.
- Production smoke test after every deploy: text, voice, document update,
  handoff, human reply.

## 15. Open questions

- Which exact clinic/service niche has the shortest sales cycle?
- Which language mix matters first: English, Urdu, Roman Urdu, Hindi, or a
  local combination?
- How much manual onboarding can be productized before self-serve is worth
  building?
- What client questions require mandatory human handoff, beyond the default
  trigger list?
- What fair-use limit protects margin while staying simple for clients to
  understand?
