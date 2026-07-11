from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    fernet_key: str

    meta_app_secret: str = ""
    meta_verify_token: str = ""
    meta_graph_api_version: str = "v25.0"

    # Model defaults only -- there is no app-wide OpenAI key. Every LLM/embedding/
    # transcription call uses the calling tenant's own key from llm_configs
    # (see services/llm.py), decrypted per-request.
    default_llm_model: str = "openai/gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    default_transcription_model: str = "whisper-1"

    # Owner handoff notification email -- all optional. Blank smtp_host means
    # notifications are silently skipped (no SMTP provider configured yet).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    app_base_url: str = "http://localhost:3000"

    # Google Sheets appointment booking -- one shared Service Account for
    # the whole app; each tenant shares their own Sheet with its email and
    # stores just the spreadsheet_id (see app/models/sheet_config.py). Blank
    # means the booking tools are never registered (feature no-ops).
    google_service_account_json: str = ""

    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
