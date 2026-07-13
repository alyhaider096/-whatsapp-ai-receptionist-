"""Cal.com API v2 client for booking integration -- API-key based, no OAuth
(each tenant brings their own Cal.com API key, same shape as their LLM key).

IMPORTANT: Cal.com's v2 API is date-versioned per endpoint via the
`cal-api-version` header. Only the slots endpoint's version below
(2024-09-04) was confirmed against current docs at build time; the booking
create/reschedule/cancel version strings are best-effort and MUST be
verified against a real Cal.com account before this is trusted in
production -- see CALCOM_API_VERSIONS below to adjust if Cal.com rejects a
request with a version-mismatch error."""

import httpx

CALCOM_BASE_URL = "https://api.cal.com/v2"

# Per-endpoint cal-api-version headers. Confirmed: slots. Best-effort,
# needs live verification: bookings/reschedule/cancel.
CALCOM_API_VERSIONS = {
    "slots": "2024-09-04",
    "bookings": "2024-08-13",
    "reschedule": "2024-08-13",
    "cancel": "2024-08-13",
}


class CalcomError(Exception):
    """Any Cal.com API failure -- callers treat this as a tool-execution
    error to surface conversationally, never a reason to crash the worker."""


def _headers(api_key: str, *, version_key: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if version_key:
        headers["cal-api-version"] = CALCOM_API_VERSIONS[version_key]
    return headers


async def _request(method: str, url: str, *, api_key: str, version_key: str | None = None, **kwargs) -> dict:
    headers = _headers(api_key, version_key=version_key)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, headers=headers, **kwargs)

    if response.status_code == 401:
        raise CalcomError("Cal.com rejected this API key -- check it's correct and active.")
    if response.status_code == 404:
        raise CalcomError("Cal.com resource not found -- check the event type or booking reference.")
    if response.status_code >= 400:
        raise CalcomError(f"Cal.com API error {response.status_code}: {response.text}")
    return response.json()


async def list_event_types(api_key: str) -> list[dict]:
    data = await _request("GET", f"{CALCOM_BASE_URL}/event-types", api_key=api_key)
    return data.get("data", [])


async def get_available_slots(
    *, api_key: str, event_type_id: int, start_date: str, end_date: str, timezone: str = "UTC"
) -> dict:
    """start_date/end_date are YYYY-MM-DD. Returns Cal.com's raw
    {date: [times...]} shaped slots dict."""
    params = {
        "eventTypeId": event_type_id,
        "start": start_date,
        "end": end_date,
        "timeZone": timezone,
    }
    data = await _request(
        "GET", f"{CALCOM_BASE_URL}/slots", api_key=api_key, version_key="slots", params=params
    )
    return data.get("data", {})


async def create_booking(
    *, api_key: str, event_type_id: int, start_iso: str, name: str, email: str,
    phone: str | None = None, timezone: str = "UTC",
) -> dict:
    attendee = {"name": name, "email": email, "timeZone": timezone, "language": "en"}
    if phone:
        attendee["phoneNumber"] = phone
    payload = {"start": start_iso, "eventTypeId": event_type_id, "attendee": attendee}
    data = await _request(
        "POST", f"{CALCOM_BASE_URL}/bookings", api_key=api_key, version_key="bookings", json=payload
    )
    return data.get("data", data)


async def find_bookings_by_email(*, api_key: str, email: str) -> list[dict]:
    params = {"attendeeEmail": email}
    data = await _request("GET", f"{CALCOM_BASE_URL}/bookings", api_key=api_key, params=params)
    return data.get("data", [])


async def reschedule_booking(*, api_key: str, booking_uid: str, new_start_iso: str) -> dict:
    payload = {"start": new_start_iso}
    data = await _request(
        "POST", f"{CALCOM_BASE_URL}/bookings/{booking_uid}/reschedule",
        api_key=api_key, version_key="reschedule", json=payload,
    )
    return data.get("data", data)


async def cancel_booking(*, api_key: str, booking_uid: str, reason: str = "") -> dict:
    payload = {"cancellationReason": reason or "Cancelled via WhatsApp assistant"}
    data = await _request(
        "POST", f"{CALCOM_BASE_URL}/bookings/{booking_uid}/cancel",
        api_key=api_key, version_key="cancel", json=payload,
    )
    return data.get("data", data)
