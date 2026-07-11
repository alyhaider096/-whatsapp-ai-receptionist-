# Message Flow and Integrations Roadmap

This note captures the product shape for configurable WhatsApp flows, chat
memory, and future Google/Cal.com integrations.

## Current v1 message flow

The v1 bot is an AI receptionist, not a drag-and-drop automation builder yet.
The safe flow is:

1. Customer sends a WhatsApp message.
2. Meta calls `POST /webhook/whatsapp`.
3. Backend verifies the signature, stores the raw event, dedups by
   `wa_message_id`, enqueues ARQ, and returns quickly.
4. Worker resolves the tenant from `metadata.phone_number_id`.
5. Worker creates or updates contact, conversation, inbound message, and lead.
6. If the conversation is in `needs_human` or `human`, the worker stops.
7. **If this is the contact's first-ever message and a `greeting_message` is
   configured**, the worker sends that greeting (plus a tappable WhatsApp
   list menu if `greeting_menu_options` is set) instead of running the RAG
   pipeline on that first turn. Tapping a menu option comes back as a
   `type: interactive` message; the tapped option's title is treated as the
   customer's next message and flows through the normal pipeline below.
8. Otherwise, inbound text/voice/interactive messages are buffered for a few
   seconds (debounce) so a burst of quick messages gets one merged reply.
9. Worker retrieves tenant-scoped knowledge chunks from pgvector.
10. Worker sends the LLM: business knowledge, the latest user message, tenant
    behavior settings, and a bounded recent-chat memory.
11. Worker sends the reply through WhatsApp Cloud API and stores the outbound
    message.

## Two operating modes

Use two simple modes before building a visual flow builder:

- `AI receptionist`: answers supported questions from the knowledge base,
  asks a short follow-up when the intent is unclear, and hands off when the
  answer is not reliable.
- `Lead collector`: behaves like a front desk. It collects configured lead
  fields such as name, service needed, and preferred time. It can discuss
  business knowledge, but it must not claim that an appointment is booked.

These modes are stored in `tenants.settings.agent` and used by the worker.

## Chat memory

Do not store "memory" as one growing prompt. Use three separate memory layers:

- Short-term conversation memory: the last 0 to 12 messages for the same
  conversation, tenant-filtered, passed into the LLM prompt.
- Contact/lead memory: structured fields such as phone, name, intent, status,
  notes, and preferred time. This belongs in CRM tables, not prompt text.
- Business knowledge memory: uploaded documents split into chunks and searched
  through pgvector with `tenant_id` filtering.

The context window setting controls only short-term conversation memory. It
does not change tenant isolation, RAG retrieval, or the 24h WhatsApp window.

## Operator inbox CRM panel

The conversation screen should feel like an operator inbox, not only a chat
transcript. The right-side panel should eventually persist:

- Tags such as `Needs human`, `Follow up`, `Booked`, `Urgent`.
- Assigned agent/owner.
- Funnel stage such as new, qualified, appointment needed, human follow-up,
  booked, or lost.
- Internal notes.
- Custom fields such as patient/customer name, WhatsApp phone, intent, service,
  preferred date/time, location, and source.

The current dashboard can show this panel as UI/local state first. Backend
persistence should come after the core WhatsApp flow is stable, likely by
extending `leads`, `contacts`, and adding a small `conversation_tags` table.

## Future flow builder

The first builder should be block-based and boring:

- Start block: first greeting or first reply style.
- Condition block: keyword/intent such as appointment, price, timing, location,
  complaint, or human request.
- Ask block: collect one lead field.
- Answer block: answer from knowledge base.
- Handoff block: mark conversation `needs_human` and send the handoff line.
- External action block: disabled until v2 integrations are real.

Store flow definitions per tenant as JSON, version them, and keep the worker
linear. Do not add LangGraph until tool-calling and real multi-step booking are
actually implemented.

## Integrations hub

**Google Sheets appointment booking is live**, not a future module anymore
-- built via a shared Service Account, not OAuth (`app/services/sheets.py`,
`app/models/sheet_config.py`). Each tenant shares their own Sheet with one
service account email and pastes the Spreadsheet ID into the dashboard's
Integrations page; no OAuth consent flow, no Google app-review wait. The
bot uses LiteLLM tool-calling (`generate_reply_with_tools`, `BOOKING_TOOLS`
in `app/services/llm.py`) to check availability, look up an existing
booking by phone, and propose a booking/reschedule -- every write requires
the customer to confirm with a yes/no reply first
(`Conversation.pending_action`, gated in `app/worker/jobs.py`).

Google Calendar and Cal.com are still future modules -- see "Build order"
below for the confirmed next step.

Meta Official WhatsApp onboarding is also a future module, separate from the
current manual test-number settings. The business owner should connect it
through Meta's hosted Facebook Login for Business / WhatsApp Embedded Signup
flow:

1. Owner clicks `Connect Meta Official`.
2. Frontend asks for an internal instance name and opens Meta's login/setup
   window with the app ID, embedded signup configuration ID, redirect URI, and
   signed `state`.
3. Owner logs in with Facebook. The app never asks for or stores their Facebook
   password.
4. Meta shows business portfolios the owner administers.
5. Owner selects or creates the WhatsApp Business Account.
6. Owner selects or registers the production phone number.
7. Owner grants WhatsApp management/messaging permissions to this Meta app.
8. Meta redirects back with a code/state and/or setup payload.
9. Backend validates `state`, exchanges the code, confirms the WABA and phone
   number ID, subscribes the WABA to webhooks, stores encrypted credentials,
   and marks the WhatsApp config as `connected`.

Important constraints:

- This is not the test-number flow.
- The user's real number may need migration if it is already tied to the
  WhatsApp Business App or another provider.
- Meta App Review, business verification, allowed domains, redirect URIs,
  webhook subscription, and production permissions must be ready before this is
  offered to normal clients.
- Store only the IDs/tokens needed for API access, encrypted at rest; never
  store Facebook passwords.

Recommended future pages:

- Integrations: connect/disconnect accounts and show sync health. Google
  Sheets already has a real card here (Spreadsheet ID + tab + test
  connection); Calendar and Cal.com are still frontend-only previews.
- Meta Official WhatsApp: launch embedded signup, choose portfolio/WABA/phone,
  show webhook/subscription status, and disconnect/reconnect.
- Calendar availability: choose calendar, timezone, working hours, buffer, and
  conflict rules.
- Cal.com booking: choose event type, location, questions, and booking webhook
  behavior.

Recommended backend shape for the OAuth-based integrations still to come
(Google Calendar, Shopify -- Sheets and Cal.com don't need this, both use
simpler API-key/service-account auth with no OAuth consent flow):

- `integration_accounts`: tenant_id, provider, encrypted refresh/access token,
  scopes, status, last_error.
- `integration_connections`: tenant_id, provider, account_id, config JSONB,
  read_enabled, write_enabled, last_synced_at.
- `integration_events`: tenant_id, provider, event_type, payload, processed_at,
  failure_reason.
- `lead_sync_jobs`: tenant_id, lead_id, provider, target, status, last_error.

Security rules:

- OAuth tokens are encrypted with the same secret-at-rest pattern.
- Every integration query is tenant-filtered.
- Revoking an integration deletes or disables stored tokens immediately.
- Sheets writes must be append/update by configured mapping only.
- Calendar/Cal.com must never book unless a booking module has explicit user
  confirmation and conflict checks (matches the propose/confirm gate already
  built for Sheets).

## Build order

1. ~~Finish v1 receptionist~~ -- done.
2. ~~Google Sheets appointment booking~~ -- done (Service Account model,
   tool-calling, confirm-before-write). Needs a real service account key +
   a shared test sheet from the business owner before it's live end-to-end.
3. **Cal.com next, explicitly confirmed.** No OAuth review wait (API-key
   based), ships fastest of the remaining integrations, direct booking
   value. This is deliberately ahead of Google Calendar below, even though
   an earlier draft of this doc had Calendar first -- worth re-confirming
   this ordering with yourself if priorities shift, rather than letting it
   silently drift again.
4. Google Calendar availability -- needs real Google OAuth (unlike Sheets'
   service-account model, read/write on someone's *personal* calendar
   needs their own consent, which is where Google's app-review wait
   actually applies).
5. Shopify (OAuth + Admin API).
6. Generic "connect your own database" connector -- read-only,
   schema-restricted only; needs a dedicated security design pass before
   any build (arbitrary customer-supplied DB credentials are a real
   SSRF/credential-storage risk, not a quick add).
7. A simple Flow Builder, once the above integrations are stable.
