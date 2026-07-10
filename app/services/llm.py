"""All LLM calls go through this module (LiteLLM) -- nowhere else
(CLAUDE.md convention). The model string is just config: swap
"openai/gpt-4o-mini" for "openai/gpt-5-nano" or any other LiteLLM-supported
model without touching this code."""

import io

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
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
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
