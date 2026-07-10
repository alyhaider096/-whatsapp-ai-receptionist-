import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

from app.routers import webhook


def _request(*, body: bytes = b"", query_string: bytes = b"", headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhook/whatsapp",
        "query_string": query_string,
        "headers": encoded_headers,
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


async def test_webhook_post_requires_meta_app_secret(monkeypatch):
    monkeypatch.setattr(
        webhook,
        "get_settings",
        lambda: SimpleNamespace(meta_app_secret="", meta_verify_token="verify-token"),
    )

    payload = {"object": "whatsapp_business_account", "entry": []}

    with pytest.raises(HTTPException) as exc:
        await webhook.receive_webhook(_request(body=json.dumps(payload).encode()), db=None)

    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


async def test_webhook_verify_requires_configured_verify_token(monkeypatch):
    monkeypatch.setattr(
        webhook,
        "get_settings",
        lambda: SimpleNamespace(meta_app_secret="secret", meta_verify_token=""),
    )

    request = _request(query_string=b"hub.mode=subscribe&hub.verify_token=&hub.challenge=ok")

    with pytest.raises(HTTPException) as exc:
        await webhook.verify_webhook(request)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
