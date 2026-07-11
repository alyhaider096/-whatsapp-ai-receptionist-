"""Google Sheets access for appointment booking, via one shared Service
Account (async httpx only -- no sync Google SDK, matching
app/services/meta.py's convention). Each tenant shares their own Sheet with
the service account's email and stores just the spreadsheet_id -- see
app/models/sheet_config.py. The Sheet itself is the single source of truth
for bookings; there is no local mirror table."""

import time
import uuid
from datetime import datetime, timezone

import httpx
from jose import jwt
from jose.exceptions import JWSError

from app.core.config import get_settings

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"

HEADER_ROW = [
    "Booking ID", "Customer Name", "Phone", "Service", "Date", "Time", "Status", "Notes", "Created At",
]

_cached_token: str | None = None
_cached_token_expires_at: float = 0.0


class SheetsError(Exception):
    """Any Sheets API/auth failure -- callers treat this as a tool-execution
    error to surface conversationally, never a reason to crash the worker."""


class SheetsNotConfigured(SheetsError):
    """Raised when GOOGLE_SERVICE_ACCOUNT_JSON is blank -- the feature is
    simply off, distinct from a real API failure."""


def _load_service_account() -> dict:
    settings = get_settings()
    if not settings.google_service_account_json:
        raise SheetsNotConfigured("Google Sheets isn't configured on this deployment yet.")
    import json

    try:
        return json.loads(settings.google_service_account_json)
    except ValueError as exc:
        raise SheetsError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc


async def _get_access_token() -> str:
    global _cached_token, _cached_token_expires_at
    if _cached_token and time.time() < _cached_token_expires_at - 60:
        return _cached_token

    account = _load_service_account()
    try:
        client_email = account["client_email"]
        now = int(time.time())
        claims = {
            "iss": client_email,
            "scope": SHEETS_SCOPE,
            "aud": TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(claims, account["private_key"], algorithm="RS256")
    except (KeyError, JWSError) as exc:
        raise SheetsError(
            "GOOGLE_SERVICE_ACCOUNT_JSON looks malformed (missing or invalid "
            "client_email/private_key)."
        ) from exc

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
    if response.status_code != 200:
        raise SheetsError(f"Google auth failed: {response.text}")
    data = response.json()

    _cached_token = data["access_token"]
    _cached_token_expires_at = time.time() + data.get("expires_in", 3600)
    return _cached_token


def _sheets_url(spreadsheet_id: str, path: str) -> str:
    return f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}{path}"


async def _request(method: str, url: str, **kwargs) -> dict:
    token = await _get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, headers=headers, **kwargs)

    if response.status_code == 403:
        raise SheetsError(
            "Access denied -- make sure this sheet is shared with the service account's "
            "email (Editor access)."
        )
    if response.status_code == 404:
        raise SheetsError("Spreadsheet not found -- double check the Spreadsheet ID.")
    if response.status_code == 400 and "Unable to parse range" in response.text:
        raise SheetsError("That sheet/tab name wasn't found in this spreadsheet.")
    if response.status_code >= 400:
        raise SheetsError(f"Google Sheets API error {response.status_code}: {response.text}")
    return response.json()


async def get_header_row(spreadsheet_id: str, sheet_name: str) -> list[str]:
    data = await _request("GET", _sheets_url(spreadsheet_id, f"/values/{sheet_name}!A1:I1"))
    values = data.get("values") or []
    return values[0] if values else []


async def list_rows(spreadsheet_id: str, sheet_name: str) -> list[dict]:
    data = await _request("GET", _sheets_url(spreadsheet_id, f"/values/{sheet_name}!A1:I1000"))
    values = data.get("values") or []
    if not values:
        return []
    header, *rows = values
    results = []
    for row in rows:
        if not row:
            continue
        padded = row + [""] * (len(header) - len(row))
        results.append(dict(zip(header, padded)))
    return results


async def find_bookings_by_phone(spreadsheet_id: str, sheet_name: str, phone: str) -> list[dict]:
    rows = await list_rows(spreadsheet_id, sheet_name)
    phone_digits = "".join(ch for ch in phone if ch.isdigit())
    return [
        row
        for row in rows
        if "".join(ch for ch in row.get("Phone", "") if ch.isdigit()).endswith(phone_digits[-7:])
    ]


async def list_bookings_for_date(spreadsheet_id: str, sheet_name: str, date: str) -> list[dict]:
    rows = await list_rows(spreadsheet_id, sheet_name)
    return [
        row for row in rows if row.get("Date", "").strip() == date.strip() and row.get("Status") != "cancelled"
    ]


async def append_booking(
    *, spreadsheet_id: str, sheet_name: str, name: str, phone: str, service: str,
    date: str, time_: str, notes: str = "",
) -> str:
    booking_id = uuid.uuid4().hex[:8]
    values = [
        booking_id, name, phone, service, date, time_, "booked", notes,
        datetime.now(timezone.utc).isoformat(),
    ]
    await _request(
        "POST",
        _sheets_url(spreadsheet_id, f"/values/{sheet_name}!A1:I1:append"),
        params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
        json={"values": [values]},
    )
    return booking_id


async def update_booking(
    *, spreadsheet_id: str, sheet_name: str, booking_id: str, updates: dict[str, str],
) -> bool:
    """Finds the row by Booking ID and updates specific columns by header
    name. Returns False if no row matches (caller should surface that as
    'booking not found' rather than silently doing nothing)."""
    data = await _request("GET", _sheets_url(spreadsheet_id, f"/values/{sheet_name}!A1:I1000"))
    values = data.get("values") or []
    if not values:
        return False
    header, *rows = values
    for i, row in enumerate(rows):
        if row and row[0] == booking_id:
            row_number = i + 2  # 1-indexed range, +1 to skip the header row
            padded = row + [""] * (len(header) - len(row))
            for key, value in updates.items():
                if key in header:
                    padded[header.index(key)] = value
            await _request(
                "PUT",
                _sheets_url(spreadsheet_id, f"/values/{sheet_name}!A{row_number}:I{row_number}"),
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": [padded]},
            )
            return True
    return False
