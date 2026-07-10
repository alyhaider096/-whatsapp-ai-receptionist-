from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from app.routers import settings as settings_router
from app.routers.settings import create_test_inbound_message
from app.schemas.settings import TestInboundMessageIn as InboundPayload


async def test_test_inbound_is_development_only(monkeypatch):
    monkeypatch.setattr(
        settings_router,
        "get_settings",
        lambda: SimpleNamespace(environment="production"),
    )

    with pytest.raises(HTTPException) as exc:
        await create_test_inbound_message(
            InboundPayload(from_number="03030222057", text="hey"),
            None,
            None,
            None,
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
