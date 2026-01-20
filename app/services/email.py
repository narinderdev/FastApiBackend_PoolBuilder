from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app.schemas.email import EmailSendError
from app.config import settings

LOGGER = logging.getLogger(__name__)

GMAIL_SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"




def send_otp_email(to_email: str, code: str, purpose: str) -> None:
    sender = settings.otp_email_sender
    if not sender:
        raise EmailSendError("OTP email sender is not configured")

    subject = settings.otp_email_subject
    body = _build_body(code, purpose, settings.otp_ttl_seconds)
    raw_message = _build_raw_message(sender, to_email, subject, body)
    token = _get_access_token()

    payload = json.dumps({"raw": raw_message}).encode("utf-8")
    request = Request(
        GMAIL_SEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        LOGGER.error("Gmail API error: %s", error_body)
        raise EmailSendError("Failed to send OTP email") from exc
    except URLError as exc:
        raise EmailSendError("Failed to reach Gmail API") from exc


def _build_body(code: str, purpose: str, ttl_seconds: int) -> str:
    minutes = max(1, ttl_seconds // 60)
    if purpose == "onboarding":
        purpose_label = "onboarding"
    else:
        purpose_label = "login"
    return (
        f"Your Pool Builder OTP code is {code}.\n\n"
        f"It expires in {minutes} minute(s).\n"
        f"Requested for {purpose_label}.\n\n"
        "If you did not request this code, you can ignore this email."
    )


def _build_raw_message(sender: str, recipient: str, subject: str, body: str) -> str:
    lines = [
        f"From: {sender}",
        f"To: {recipient}",
        f"Subject: {subject}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
    ]
    message = "\r\n".join(lines)
    # Gmail API expects base64url-encoded RFC 2822 content.
    return base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii")


def _token_file_path() -> Path:
    if settings.gmail_token_file:
        return Path(settings.gmail_token_file)
    root = Path(__file__).resolve().parents[2]
    return root / "credentials" / "token.json"


def _credentials_file_path() -> Path:
    if settings.gmail_credentials_file:
        return Path(settings.gmail_credentials_file)
    root = Path(__file__).resolve().parents[2]
    return root / "credentials" / "credentials.json"


def _get_access_token() -> str:
    token_path = _token_file_path()
    token_data = _load_json(token_path)

    token = token_data.get("token")
    expiry = _parse_expiry(token_data.get("expiry"))
    if token and expiry and expiry > datetime.now(timezone.utc) + timedelta(minutes=1):
        return token

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise EmailSendError("Gmail refresh token is missing")

    client_id, client_secret = _resolve_client_details(token_data)
    token_uri = token_data.get("token_uri") or "https://oauth2.googleapis.com/token"

    payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")

    request = Request(token_uri, data=payload, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        LOGGER.error("Gmail token refresh error: %s", error_body)
        raise EmailSendError("Failed to refresh Gmail token") from exc
    except URLError as exc:
        raise EmailSendError("Failed to reach Gmail token endpoint") from exc

    access_token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3600))
    if not access_token:
        raise EmailSendError("Gmail token refresh did not return an access token")

    token_data["token"] = access_token
    token_data["expiry"] = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()
    _write_json(token_path, token_data)
    return access_token


def _resolve_client_details(token_data: dict[str, Any]) -> tuple[str, str]:
    client_id = token_data.get("client_id")
    client_secret = token_data.get("client_secret")
    if client_id and client_secret:
        return client_id, client_secret

    credentials_path = _credentials_file_path()
    credentials = _load_json(credentials_path)
    installed = credentials.get("installed", {})
    client_id = installed.get("client_id") or credentials.get("client_id")
    client_secret = installed.get("client_secret") or credentials.get("client_secret")
    if not client_id or not client_secret:
        raise EmailSendError("Gmail client credentials are missing")
    return client_id, client_secret


def _parse_expiry(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EmailSendError(f"Missing Gmail file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
