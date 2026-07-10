from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.agent_settings import (
    DEFAULT_AGENT_SETTINGS,
    REPLY_MODE_AUTO,
    REPLY_MODE_LEAD_CAPTURE,
)


class WhatsAppConfigIn(BaseModel):
    waba_id: str = Field(min_length=1, max_length=64)
    phone_number_id: str = Field(min_length=1, max_length=64)
    access_token: str | None = Field(default=None, min_length=1)


class WhatsAppConfigOut(BaseModel):
    waba_id: str
    phone_number_id: str
    access_token_masked: str
    status: str


class LLMConfigIn(BaseModel):
    provider: str = Field(default="openai", max_length=64)
    model: str = Field(default="openai/gpt-4o-mini", max_length=128)
    api_key: str | None = Field(default=None, min_length=1)


class LLMConfigOut(BaseModel):
    provider: str
    model: str
    api_key_masked: str


class GreetingMenuOptionIn(BaseModel):
    title: str = Field(min_length=1, max_length=24)
    description: str = Field(default="", max_length=72)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_option_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class AgentBehaviorIn(BaseModel):
    reply_mode: Literal[REPLY_MODE_AUTO, REPLY_MODE_LEAD_CAPTURE] = DEFAULT_AGENT_SETTINGS[
        "reply_mode"
    ]
    tone: str = Field(default=DEFAULT_AGENT_SETTINGS["tone"], min_length=1, max_length=160)
    memory_window_messages: int = Field(
        default=DEFAULT_AGENT_SETTINGS["memory_window_messages"], ge=0, le=12
    )
    handoff_message: str = Field(
        default=DEFAULT_AGENT_SETTINGS["handoff_message"], min_length=1, max_length=500
    )
    lead_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_AGENT_SETTINGS["lead_fields"]))
    extra_instructions: str = Field(default="", max_length=2000)
    greeting_message: str = Field(default="", max_length=1024)
    greeting_menu_options: list[GreetingMenuOptionIn] = Field(default_factory=list)

    @field_validator("tone", "handoff_message", "extra_instructions", "greeting_message", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("greeting_menu_options")
    @classmethod
    def cap_menu_options(cls, value: list[GreetingMenuOptionIn]) -> list[GreetingMenuOptionIn]:
        return value[:5]

    @field_validator("lead_fields")
    @classmethod
    def clean_lead_fields(cls, value: list[str]) -> list[str]:
        fields: list[str] = []
        seen: set[str] = set()
        for item in value:
            field = item.strip()[:64]
            key = field.lower()
            if field and key not in seen:
                seen.add(key)
                fields.append(field)
            if len(fields) >= 12:
                break
        return fields or list(DEFAULT_AGENT_SETTINGS["lead_fields"])


class AgentBehaviorOut(AgentBehaviorIn):
    pass


class ConnectionStatusOut(BaseModel):
    whatsapp_connected: bool
    whatsapp_status: str | None
    llm_connected: bool
    llm_model: str | None
    webhook_last_seen_at: datetime | None
    webhook_expected_phone_number_id: str | None = None
    webhook_last_phone_number_id: str | None = None
    webhook_last_processed_at: datetime | None = None
    webhook_last_failure_reason: str | None = None
    webhook_last_error_message: str | None = None
    webhook_last_send_error: str | None = None
    webhook_signature_configured: bool = False
    webhook_verify_token_configured: bool = False
    webhook_verify_token_is_placeholder: bool = False
    redis_connected: bool = False
    worker_queue_depth: int | None = None
    worker_health_seen: bool = False
    worker_health_detail: str | None = None


class TestInboundMessageIn(BaseModel):
    from_number: str = Field(min_length=5, max_length=32)
    text: str = Field(min_length=1, max_length=2000)
    reset_conversation: bool = False


class TestInboundMessageOut(BaseModel):
    status: str
    webhook_event_id: str
    wa_message_id: str
    normalized_from_number: str
