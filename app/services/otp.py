from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import secrets

from sqlalchemy import delete, select
from app.schemas.otp import OtpRecord
from app.config import settings
from app.models.db_operation import _delete_expired_record_,_delete_records,_add_record,_select_records,_scalar_one_or_none_operation

def normalize_identifier(identifier: str) -> str:
    cleaned = identifier.strip()
    if "@" in cleaned:
        return cleaned.lower()
    return re.sub(r"\D", "", cleaned)


class OtpStore:
    def __init__(self, ttl_seconds: int, code_length: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._code_length = code_length

    def request_otp(self, identifier: str, purpose: str) -> OtpRecord:
        now = datetime.now(timezone.utc)
        code = self._generate_code()
        record = OtpRecord(
            code=code,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            purpose=purpose,
        )
        normalized = normalize_identifier(identifier)
        # Delete any existing OTPs for this identifier + purpos
        _delete_expired_record_("otp",now)
        _delete_records(
            "otp",
            identifier=normalized,
            purpose=purpose,
        )
        entry={"identifier":normalized,
            "purpose":purpose,
            "code":record.code,
            "expires_at":record.expires_at,
            "created_at":now,}
        # Insert new OTP
        _add_record(
            "otp",
            **entry
        )

        return record

    def verify_otp(self, identifier: str, purpose: str, code: str) -> bool:
        now = datetime.now(timezone.utc)
        normalized = normalize_identifier(identifier)
        clean_code = code.strip()

        if settings.otp_debug and clean_code == "123456" and "@" not in normalized:
            _delete_expired_record_("otp",now)
            _delete_records(
                "otp",
                identifier=normalized,
                purpose=purpose,
            )
            return True
        payload={
                "identifier":normalized,
                "purpose":purpose
                }
        entry=_scalar_one_or_none_operation(
                    db="otp",  # Replace with the actual database name
                    now=now,
                    clean_code=clean_code,
                    **payload # Assuming `purpose` is one of the filters or additional parameters
                )
        return entry

    def _generate_code(self) -> str:
        value = secrets.randbelow(10**self._code_length)
        return str(value).zfill(self._code_length)


otp_store = OtpStore(settings.otp_ttl_seconds, settings.otp_length)
