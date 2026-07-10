from app.services.agent_settings import (
    DEFAULT_AGENT_SETTINGS,
    REPLY_MODE_AUTO,
    REPLY_MODE_LEAD_CAPTURE,
    get_agent_settings,
)


def test_agent_settings_defaults_when_missing():
    assert get_agent_settings({}) == DEFAULT_AGENT_SETTINGS


def test_agent_settings_sanitizes_saved_json():
    settings = get_agent_settings(
        {
            "agent": {
                "reply_mode": REPLY_MODE_LEAD_CAPTURE,
                "tone": "  warm and concise  ",
                "memory_window_messages": 99,
                "handoff_message": "  We will help shortly.  ",
                "lead_fields": ["Name", "name", "Preferred time", "", 123],
                "extra_instructions": "  Use Roman Urdu when the customer does.  ",
            }
        }
    )

    assert settings["reply_mode"] == REPLY_MODE_LEAD_CAPTURE
    assert settings["tone"] == "warm and concise"
    assert settings["memory_window_messages"] == 12
    assert settings["handoff_message"] == "We will help shortly."
    assert settings["lead_fields"] == ["Name", "Preferred time"]
    assert settings["extra_instructions"] == "Use Roman Urdu when the customer does."


def test_agent_settings_falls_back_from_invalid_mode_and_fields():
    settings = get_agent_settings(
        {
            "agent": {
                "reply_mode": "tool_call_booking",
                "memory_window_messages": "bad",
                "lead_fields": [],
            }
        }
    )

    assert settings["reply_mode"] == REPLY_MODE_AUTO
    assert settings["memory_window_messages"] == 8
    assert settings["lead_fields"] == DEFAULT_AGENT_SETTINGS["lead_fields"]
