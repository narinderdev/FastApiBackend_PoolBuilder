from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import secrets

from sqlalchemy import delete, select

from app.config import settings
from app.database import session_scope
from app.models.otp import OtpEntry


@dataclass(frozen=True)
class OtpRecord:
    code: str
    expires_at: datetime
    purpose: str


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

        with session_scope() as session:
            session.execute(delete(OtpEntry).where(OtpEntry.expires_at <= now))
            session.execute(
                delete(OtpEntry).where(
                    OtpEntry.identifier == normalized,
                    OtpEntry.purpose == purpose,
                )
            )
            session.add(
                OtpEntry(
                    identifier=normalized,
                    purpose=purpose,
                    code=record.code,
                    expires_at=record.expires_at,
                    created_at=now,
                )
            )
        return record

    def verify_otp(self, identifier: str, purpose: str, code: str) -> bool:
        now = datetime.now(timezone.utc)
        normalized = normalize_identifier(identifier)
        clean_code = code.strip()
        if settings.otp_debug and clean_code == "123456" and "@" not in normalized:
            with session_scope() as session:
                session.execute(delete(OtpEntry).where(OtpEntry.expires_at <= now))
                session.execute(
                    delete(OtpEntry).where(
                        OtpEntry.identifier == normalized,
                        OtpEntry.purpose == purpose,
                    )
                )
            return True

        with session_scope() as session:
            session.execute(delete(OtpEntry).where(OtpEntry.expires_at <= now))
            result = session.execute(
                select(OtpEntry).where(
                    OtpEntry.identifier == normalized,
                    OtpEntry.purpose == purpose,
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return False
            if entry.expires_at <= now:
                session.delete(entry)
                return False
            if entry.code != clean_code:
                return False
            session.delete(entry)
            return True

    def _generate_code(self) -> str:
        value = secrets.randbelow(10**self._code_length)
        return str(value).zfill(self._code_length)


otp_store = OtpStore(settings.otp_ttl_seconds, settings.otp_length)
