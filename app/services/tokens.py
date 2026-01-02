from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessTokenData:
    user_id: int
    session_id: str


@dataclass(frozen=True)
class RefreshTokenData:
    user_id: int
    session_id: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, session_id: str) -> str:
    if not settings.jwt_secret:
        raise TokenError("JWT secret is not configured")
    now = _utcnow()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, session_id: str) -> str:
    if not settings.jwt_secret:
        raise TokenError("JWT secret is not configured")
    now = _utcnow()
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "jti": session_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AccessTokenData:
    payload = _decode_token(token, expected_type="access")
    session_id = payload.get("sid")
    if not session_id:
        raise TokenError("Access token is missing session id")
    return AccessTokenData(user_id=_parse_subject(payload), session_id=session_id)


def decode_refresh_token(token: str) -> RefreshTokenData:
    payload = _decode_token(token, expected_type="refresh")
    session_id = payload.get("jti")
    if not session_id:
        raise TokenError("Refresh token is missing session id")
    return RefreshTokenData(user_id=_parse_subject(payload), session_id=session_id)


def _decode_token(token: str, expected_type: str) -> dict:
    if not token:
        raise TokenError("Token is missing")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise TokenError("Invalid token type")
    return payload


def _parse_subject(payload: dict) -> int:
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token subject is missing")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenError("Invalid token subject") from exc
