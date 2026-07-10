from types import SimpleNamespace

from app.models.llm_config import LLMConfig
from app.models.tenant import Tenant
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp_config import WhatsAppConfig
from app.routers import settings as settings_router
from app.routers.settings import get_connection_status


async def test_status_reports_missing_meta_secret_and_placeholder_token(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        settings_router,
        "get_settings",
        lambda: SimpleNamespace(
            meta_app_secret="",
            meta_verify_token="dev-verify-token-change-me",
            redis_url="redis://unused",
        ),
    )

    async def fake_runtime_diagnostics():
        return True, 0, True, "worker healthy"

    monkeypatch.setattr(settings_router, "_get_runtime_diagnostics", fake_runtime_diagnostics)

    tenant = Tenant(name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()
    db_session.add_all(
        [
            WhatsAppConfig(
                tenant_id=tenant.id,
                waba_id="waba-1",
                phone_number_id="1238786779316885",
                access_token_encrypted="encrypted",
            ),
            LLMConfig(
                tenant_id=tenant.id,
                api_key_encrypted="encrypted",
                model="openai/gpt-4o-mini",
            ),
            WebhookEvent(
                tenant_id=tenant.id,
                phone_number_id="1238786779316885",
                payload={"entry": []},
                processed=True,
                failure_reason="whatsapp_send_failed",
                send_error="HTTPStatusError: token rejected",
            ),
        ]
    )
    await db_session.commit()

    status = await get_connection_status(db_session, tenant.id, None)

    assert status.webhook_expected_phone_number_id == "1238786779316885"
    assert status.webhook_last_phone_number_id == "1238786779316885"
    assert status.webhook_signature_configured is False
    assert status.webhook_verify_token_configured is True
    assert status.webhook_verify_token_is_placeholder is True
    assert status.redis_connected is True
    assert status.worker_health_seen is True
    assert status.worker_queue_depth == 0
    assert status.webhook_last_failure_reason == "whatsapp_send_failed"
    assert status.webhook_last_send_error == "HTTPStatusError: token rejected"
