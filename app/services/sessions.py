import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from app.config import settings
from app.models.schema.session import SessionEntry
from app.models.db_operation import _delete_expired_record_,_select_one_or_none,_update_records,_add_record



class SessionStore:
    def create_session(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        _delete_expired_record_(
            "session",
            now=now,
        )
        entry={
             "token":token,
            "user_id":user_id,
            "created_at":now,
            "expires_at":expires_at,
            "revoked_at":None
        }
        _add_record(
            "session",
            **entry
        )

        return token

    def revoke_session(self, token: str) -> bool:
        now = datetime.now(timezone.utc)
        _delete_expired_record_(
            "session",
            now=now,
        )
        result=_update_records(
            "session",
            token=token,
            revoked_at=None,
            values={
                "revoked_at": now,
            },
        )

        return result > 0

    def get_user_id(self, token: str) -> Optional[int]:
            now = datetime.now(timezone.utc)
            payload ={"token":token,
                            "revoked_at":None,
                            "expires_at":(">", now)}
            entry = _select_one_or_none(
                "session",
                **payload
            )

            if entry is None:
                return None

            return entry.user_id



session_store = SessionStore()
