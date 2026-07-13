"""All LLM calls go through this module (LiteLLM) -- nowhere else
(CLAUDE.md convention). The model string is just config: swap
"openai/gpt-4o-mini" for "openai/gpt-5-nano" or any other LiteLLM-supported
model without touching this code."""

import io
import json
from typing import Awaitable, Callable

import litellm

from app.services.agent_settings import REPLY_MODE_AUTO, REPLY_MODE_LEAD_CAPTURE


REPLY_MODE_INSTRUCTIONS = {
    REPLY_MODE_AUTO: (
        "Answer the customer directly when the answer is supported by Business knowledge. "
        "Ask one concise follow-up question when the customer's intent is unclear."
    ),
    REPLY_MODE_LEAD_CAPTURE: (
        "Act like a front-desk receptionist. Collect the lead fields naturally, answer only "
        "supported business questions, and never claim an appointment is booked."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """You are the WhatsApp assistant for {business_name}.
Answer ONLY using the "Business knowledge" below. If the answer isn't in it,
say you're not sure and offer to connect the customer with a team member --
never guess prices, timings, or policies.

Tone: {tone}
Mode: {reply_mode_instruction}
Lead fields to collect when relevant: {lead_fields}
Owner instructions:
{extra_instructions}

Recent chat memory:
{conversation_context}

Business knowledge:
{context}
"""

NO_CONTEXT_PLACEHOLDER = "(no business knowledge uploaded yet)"
NO_RECENT_CONTEXT_PLACEHOLDER = "(no prior messages in this conversation)"
NO_EXTRA_INSTRUCTIONS_PLACEHOLDER = "(none)"

OFF_TOPIC_PROMPT_TEMPLATE = """You are the WhatsApp assistant for {business_name}.
A customer just asked something you have no specific information about in
your knowledge base: "{user_message}"

Decide which of these two cases this is:

CASE A -- clearly outside what a business like this would ever handle (for
example, asking an eye clinic about knee pain, or asking a restaurant for
legal advice). Reply with ONE short, polite message explaining this isn't
something you handle, and if it's obviously a different kind of
specialist/service, say so in one sentence. Do NOT offer to connect them
with your team -- your team can't help with this either, so escalating
would just waste everyone's time.

CASE B -- plausibly something this business handles, just not documented
here (a real question about this business's own services, pricing, hours,
or policies that you simply don't have the specific answer to). Reply with
exactly the text NEEDS_HUMAN and nothing else.

Reply with either your CASE A message, or exactly NEEDS_HUMAN."""


async def classify_and_reply_off_topic(
    *, model: str, api_key: str, business_name: str, user_message: str
) -> str | None:
    """Called when RAG found no relevant chunks. Returns a customer-facing
    decline message if the question is clearly outside this business's
    domain (no human handoff needed -- a person can't help with this
    either), or None if it's plausibly relevant and should still go to a
    human via the normal handoff path."""
    prompt = OFF_TOPIC_PROMPT_TEMPLATE.format(business_name=business_name, user_message=user_message)
    response = await litellm.acompletion(
        model=model,
        api_key=api_key,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=150,
    )
    content = (response["choices"][0]["message"]["content"] or "").strip()
    if content == "NEEDS_HUMAN" or content.startswith("NEEDS_HUMAN"):
        return None
    return content


BOOKING_TOOLS_PROMPT_ADDENDUM = """
You also have booking tools: check_availability, find_booking,
propose_booking, propose_reschedule. Use them for anything about booking,
scheduling, or an existing appointment. propose_booking and
propose_reschedule do NOT actually book anything -- they only prepare a
proposal; always tell the customer what you're proposing and ask them to
reply YES to confirm before it's final. For everything else, keep using
only the Business knowledge above."""


def _build_system_prompt(
    *, business_name: str, tone: str, reply_mode: str, lead_fields: list[str] | None,
    extra_instructions: str, conversation_context: str, context: str, tools_enabled: bool = False,
) -> str:
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        business_name=business_name,
        tone=tone or "friendly and professional",
        reply_mode_instruction=REPLY_MODE_INSTRUCTIONS.get(
            reply_mode, REPLY_MODE_INSTRUCTIONS[REPLY_MODE_AUTO]
        ),
        lead_fields=", ".join(lead_fields or []) or "name, service needed, preferred day/time",
        extra_instructions=extra_instructions or NO_EXTRA_INSTRUCTIONS_PLACEHOLDER,
        conversation_context=conversation_context or NO_RECENT_CONTEXT_PLACEHOLDER,
        context=context or NO_CONTEXT_PLACEHOLDER,
    )
    if tools_enabled:
        prompt += BOOKING_TOOLS_PROMPT_ADDENDUM
    return prompt


async def generate_reply(
    *,
    model: str,
    api_key: str,
    business_name: str,
    tone: str,
    context: str,
    user_message: str,
    reply_mode: str = REPLY_MODE_AUTO,
    lead_fields: list[str] | None = None,
    extra_instructions: str = "",
    conversation_context: str = "",
) -> str:
    system_prompt = _build_system_prompt(
        business_name=business_name, tone=tone, reply_mode=reply_mode, lead_fields=lead_fields,
        extra_instructions=extra_instructions, conversation_context=conversation_context,
        context=context,
    )
    response = await litellm.acompletion(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    return response["choices"][0]["message"]["content"].strip()


async def generate_reply_with_tools(
    *,
    model: str,
    api_key: str,
    business_name: str,
    tone: str,
    context: str,
    user_message: str,
    tools: list[dict],
    tool_executor: Callable[[str, dict], Awaitable[str]],
    reply_mode: str = REPLY_MODE_AUTO,
    lead_fields: list[str] | None = None,
    extra_instructions: str = "",
    conversation_context: str = "",
) -> str:
    """Same prompt/context as generate_reply, but lets the model call one of
    `tools` before producing its final reply. Always resolves to one
    plain-text reply: if the model calls a tool, `tool_executor` runs it and
    its result is fed back for a second completion that produces the actual
    customer-facing text. Only the first tool call per turn is honored --
    one action per turn keeps this predictable."""
    system_prompt = _build_system_prompt(
        business_name=business_name, tone=tone, reply_mode=reply_mode, lead_fields=lead_fields,
        extra_instructions=extra_instructions, conversation_context=conversation_context,
        context=context, tools_enabled=True,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    response = await litellm.acompletion(
        model=model, api_key=api_key, messages=messages,
        tools=tools, tool_choice="auto", temperature=0.2, max_tokens=400,
    )
    message = response["choices"][0]["message"]
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else message.tool_calls

    if not tool_calls:
        content = message.get("content") if isinstance(message, dict) else message.content
        return (content or "").strip()

    call = tool_calls[0]
    function = call["function"] if isinstance(call, dict) else call.function
    tool_name = function["name"] if isinstance(function, dict) else function.name
    raw_args = function["arguments"] if isinstance(function, dict) else function.arguments
    try:
        tool_args = json.loads(raw_args) if raw_args else {}
    except ValueError:
        tool_args = {}

    tool_result = await tool_executor(tool_name, tool_args)

    assistant_message = message if isinstance(message, dict) else message.model_dump()
    messages.append(assistant_message)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call["id"] if isinstance(call, dict) else call.id,
            "content": tool_result,
        }
    )
    follow_up = await litellm.acompletion(
        model=model, api_key=api_key, messages=messages, temperature=0.2, max_tokens=400,
    )
    return follow_up["choices"][0]["message"]["content"].strip()


BOOKING_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Check what appointments are already booked on a given date, to see "
                "if a time is free before proposing a booking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_booking",
            "description": "Look up the customer's existing appointment booking(s) by phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number. Omit to use their WhatsApp number.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_booking",
            "description": (
                "Propose creating a new appointment. This does NOT book it yet -- it only "
                "prepares a proposal for the customer to confirm with a yes/no reply."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Customer's full name"},
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number. Omit to use their WhatsApp number.",
                    },
                    "service": {"type": "string", "description": "What the appointment is for"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "e.g. 2:00 PM"},
                },
                "required": ["name", "service", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_reschedule",
            "description": (
                "Propose moving an existing booking to a new date/time. This does NOT "
                "reschedule it yet -- only prepares the change for the customer to confirm."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The Booking ID from find_booking's result",
                    },
                    "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "new_time": {"type": "string", "description": "e.g. 2:00 PM"},
                },
                "required": ["booking_id", "new_date", "new_time"],
            },
        },
    },
]


async def embed_texts(*, model: str, api_key: str, texts: list[str]) -> list[list[float]]:
    response = await litellm.aembedding(model=model, api_key=api_key, input=texts)
    return [item["embedding"] for item in response["data"]]


async def transcribe_audio(*, model: str, api_key: str, audio_bytes: bytes, filename: str) -> str:
    """Whisper transcription for inbound voice notes. WhatsApp sends audio as
    OGG/Opus, which isn't in OpenAI's officially documented format list --
    it works in practice, but callers should treat failures here as expected
    and fall back gracefully rather than surfacing an error to the customer."""
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    response = await litellm.atranscription(model=model, api_key=api_key, file=audio_file)
    text = response.get("text") if isinstance(response, dict) else getattr(response, "text", "")
    return (text or "").strip()
