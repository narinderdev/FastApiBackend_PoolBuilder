from __future__ import annotations

import base64
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import settings

LOGGER = logging.getLogger(__name__)


class SmsSendError(RuntimeError):
    pass


def send_otp_sms(to_phone: str, code: str, purpose: str) -> None:
    account_sid = settings.twilio_account_sid
    auth_token = settings.twilio_auth_token
    from_phone = settings.twilio_phone_number
    if not account_sid or not auth_token or not from_phone:
        raise SmsSendError("Twilio is not configured")

    to_number = _normalize_e164(to_phone)
    from_number = _normalize_e164(from_phone)
    body = _build_body(code, purpose, settings.otp_ttl_seconds)
    LOGGER.warning("Sending OTP SMS to=%s from=%s", to_number, from_number)
    endpoint = (
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    )
    payload = urlencode({"To": to_number, "From": from_number, "Body": body}).encode(
        "utf-8"
    )
    token = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode(
        "ascii"
    )
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        LOGGER.error(
            "Twilio API error to=%s from=%s response=%s",
            to_number,
            from_number,
            error_body,
        )
        raise SmsSendError("Failed to send OTP SMS") from exc
    except URLError as exc:
        raise SmsSendError("Failed to reach Twilio API") from exc


def _normalize_e164(phone_number: str) -> str:
    raw = phone_number.strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise SmsSendError("Phone number is missing")
    if len(digits) == 10:
        default_code = re.sub(r"\D", "", settings.default_country_code)
        if not default_code:
            raise SmsSendError("Default country code is not configured")
        digits = f"{default_code}{digits}"
    if len(digits) < 10 or len(digits) > 15:
        raise SmsSendError("Phone number must include a valid country code")
    return f"+{digits}"


def _build_body(code: str, purpose: str, ttl_seconds: int) -> str:
    minutes = max(1, ttl_seconds // 60)
    if purpose == "onboarding":
        purpose_label = "onboarding"
    else:
        purpose_label = "login"
    return (
        f"Your Pool Builder OTP code is {code}."
        f" It expires in {minutes} minute(s)."
        f" Requested for {purpose_label}."
    )
