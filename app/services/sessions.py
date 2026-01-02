from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import delete, select, update

from app.config import settings
from app.database import session_scope
from app.models.session import SessionEntry


class SessionStore:
    def create_session(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        with session_scope() as session:
            session.execute(delete(SessionEntry).where(SessionEntry.expires_at <= now))
            session.add(
                SessionEntry(
                    token=token,
                    user_id=user_id,
                    created_at=now,
                    expires_at=expires_at,
                    revoked_at=None,
                )
            )
        return token

    def revoke_session(self, token: str) -> bool:
        now = datetime.now(timezone.utc)
        with session_scope() as session:
            result = session.execute(
                update(SessionEntry)
                .where(SessionEntry.token == token, SessionEntry.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            return result.rowcount > 0

    def get_user_id(self, token: str) -> int | None:
        now = datetime.now(timezone.utc)
        with session_scope() as session:
            session.execute(delete(SessionEntry).where(SessionEntry.expires_at <= now))
            result = session.execute(
                select(SessionEntry).where(
                    SessionEntry.token == token,
                    SessionEntry.revoked_at.is_(None),
                    SessionEntry.expires_at > now,
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return None
            return entry.user_id


session_store = SessionStore()
