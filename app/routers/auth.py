from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.schemas.otp import OtpRequest, OtpResponse, OtpVerifyRequest, OtpVerifyResponse
from app.schemas.tokens import TokenRefreshRequest, TokenRefreshResponse
from app.services.email import EmailSendError, send_otp_email
from app.services.otp import otp_store
from app.services.sessions import session_store
from app.services.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.services.users import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", response_model=OtpResponse, response_model_exclude_none=True)
def request_otp(payload: OtpRequest) -> OtpResponse:
    record = otp_store.request_otp(payload.identifier, payload.purpose)
    identifier = payload.identifier.strip()
    if "@" in identifier:
        try:
            send_otp_email(identifier, record.code, payload.purpose)
        except EmailSendError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
    response = OtpResponse(
        message="OTP sent",
        expires_in_seconds=settings.otp_ttl_seconds,
        otp=record.code if settings.otp_debug else None,
    )
    return response


@router.post("/otp/verify", response_model=OtpVerifyResponse, response_model_exclude_none=True)
def verify_otp(payload: OtpVerifyRequest) -> OtpVerifyResponse:
    verified = otp_store.verify_otp(payload.identifier, payload.purpose, payload.code)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )
    try:
        user_entry, existed = user_store.ensure_user_for_identifier(payload.identifier)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    role = user_entry.role or "onboarded_user"
    is_admin = role == "admin"
    session_id = session_store.create_session(user_entry.id)
    try:
        access_token = create_access_token(user_entry.id, session_id)
        refresh_token = create_refresh_token(user_entry.id, session_id)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return OtpVerifyResponse(
        message="OTP verified",
        verified=True,
        role=role,
        is_admin=is_admin,
        user_exists=existed,
        user_onboarded=user_entry.onboarded_at is not None,
        user_id=user_entry.id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_seconds=settings.access_token_expire_minutes * 60,
        refresh_expires_in_seconds=settings.refresh_token_expire_days * 86400,
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_tokens(payload: TokenRefreshRequest) -> TokenRefreshResponse:
    try:
        refresh_data = decode_refresh_token(payload.refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    user_id = session_store.get_user_id(refresh_data.session_id)
    if user_id is None or user_id != refresh_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    try:
        access_token = create_access_token(refresh_data.user_id, refresh_data.session_id)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return TokenRefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )
    try:
        refresh_data = decode_refresh_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    revoked = session_store.revoke_session(refresh_data.session_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )
    return {"message": "Logged out"}
