"""All outbound WhatsApp Cloud API calls go through this module -- nowhere
else (CLAUDE.md convention). Async httpx only, no `requests`."""

import httpx

from app.core.config import get_settings

GRAPH_BASE = "https://graph.facebook.com"


def _graph_url(path: str) -> str:
    version = get_settings().meta_graph_api_version
    return f"{GRAPH_BASE}/{version}/{path}"


def _raise_for_meta_error(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        message = f"Meta Graph API error {response.status_code}: {detail}"
        raise httpx.HTTPStatusError(message, request=exc.request, response=exc.response) from exc


async def send_text_message(*, phone_number_id: str, access_token: str, to: str, body: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(_graph_url(f"{phone_number_id}/messages"), json=payload, headers=headers)
        _raise_for_meta_error(response)
        return response.json()


async def send_interactive_list_message(
    *,
    phone_number_id: str,
    access_token: str,
    to: str,
    body: str,
    button_text: str,
    options: list[dict],
) -> dict:
    """WhatsApp's native tappable list menu. `options` is
    [{"id", "title", "description"}, ...] -- Meta caps this at 10 rows,
    title <=24 chars, description <=72 chars (enforced upstream in
    agent_settings.py, but truncated again here defensively)."""
    rows = []
    for option in options[:10]:
        row = {"id": option["id"], "title": option["title"][:24]}
        description = (option.get("description") or "").strip()
        if description:
            row["description"] = description[:72]
        rows.append(row)

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {"button": button_text[:20], "sections": [{"rows": rows}]},
        },
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(_graph_url(f"{phone_number_id}/messages"), json=payload, headers=headers)
        _raise_for_meta_error(response)
        return response.json()


async def get_media_url(*, media_id: str, access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(_graph_url(media_id), headers=headers)
        _raise_for_meta_error(response)
        return response.json()["url"]


async def download_media(*, media_url: str, access_token: str) -> bytes:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(media_url, headers=headers)
        _raise_for_meta_error(response)
        return response.content
