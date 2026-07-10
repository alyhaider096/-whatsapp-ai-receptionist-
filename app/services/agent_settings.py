from typing import Any


REPLY_MODE_AUTO = "auto_answer"
REPLY_MODE_LEAD_CAPTURE = "lead_capture"
VALID_REPLY_MODES = {REPLY_MODE_AUTO, REPLY_MODE_LEAD_CAPTURE}

DEFAULT_HANDOFF_MESSAGE = "I'm connecting you with a team member. Please wait a moment."
DEFAULT_LEAD_FIELDS = ["name", "service needed", "preferred day/time"]
# WhatsApp list-message limits (Meta Cloud API): max 10 rows, row title
# <=24 chars, row description <=72 chars. We cap options lower than the
# hard max to keep the menu readable on-screen.
MAX_GREETING_MENU_OPTIONS = 5
DEFAULT_AGENT_SETTINGS = {
    "reply_mode": REPLY_MODE_AUTO,
    "tone": "friendly and professional",
    "memory_window_messages": 8,
    "handoff_message": DEFAULT_HANDOFF_MESSAGE,
    "lead_fields": DEFAULT_LEAD_FIELDS,
    "extra_instructions": "",
    "greeting_message": "",
    "greeting_menu_options": [],
}


def get_agent_settings(tenant_settings: dict[str, Any] | None) -> dict[str, Any]:
    raw_agent = {}
    if isinstance(tenant_settings, dict) and isinstance(tenant_settings.get("agent"), dict):
        raw_agent = tenant_settings["agent"]

    reply_mode = raw_agent.get("reply_mode")
    if reply_mode not in VALID_REPLY_MODES:
        reply_mode = DEFAULT_AGENT_SETTINGS["reply_mode"]

    tone = _clean_text(raw_agent.get("tone"), DEFAULT_AGENT_SETTINGS["tone"], max_length=160)
    handoff_message = _clean_text(
        raw_agent.get("handoff_message"),
        DEFAULT_AGENT_SETTINGS["handoff_message"],
        max_length=500,
    )
    extra_instructions = _clean_text(raw_agent.get("extra_instructions"), "", max_length=2000)
    lead_fields = _clean_lead_fields(raw_agent.get("lead_fields"))
    greeting_message = _clean_text(raw_agent.get("greeting_message"), "", max_length=1024)
    greeting_menu_options = _clean_menu_options(raw_agent.get("greeting_menu_options"))

    try:
        memory_window = int(raw_agent.get("memory_window_messages", 8))
    except (TypeError, ValueError):
        memory_window = 8

    return {
        "reply_mode": reply_mode,
        "tone": tone,
        "memory_window_messages": min(max(memory_window, 0), 12),
        "handoff_message": handoff_message,
        "lead_fields": lead_fields,
        "extra_instructions": extra_instructions,
        "greeting_message": greeting_message,
        "greeting_menu_options": greeting_menu_options,
    }


def _clean_text(value: Any, fallback: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned[:max_length] if cleaned else fallback


def _clean_lead_fields(value: Any) -> list[str]:
    if not isinstance(value, list):
        return list(DEFAULT_LEAD_FIELDS)

    fields: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        field = item.strip()[:64]
        key = field.lower()
        if field and key not in seen:
            seen.add(key)
            fields.append(field)
        if len(fields) >= 12:
            break

    return fields or list(DEFAULT_LEAD_FIELDS)


def _clean_menu_options(value: Any) -> list[dict[str, str]]:
    """Greeting menu rows -- title is required (WhatsApp list-row title),
    description is optional. Silently drops malformed entries rather than
    rejecting the whole settings save."""
    if not isinstance(value, list):
        return []

    options: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        description = item.get("description")
        options.append(
            {
                "title": title.strip()[:24],
                "description": description.strip()[:72] if isinstance(description, str) else "",
            }
        )
        if len(options) >= MAX_GREETING_MENU_OPTIONS:
            break
    return options
