from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.schemas.otp import OtpResponse
from app.schemas.users import UserCreate, UserResponse
from app.services.otp import otp_store
from app.services.sessions import session_store
from app.services.tokens import TokenError, decode_access_token
from app.services.users import user_store

router = APIRouter(prefix="/users", tags=["users"])


class PhoneOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=10)


def get_current_user_id(authorization: str | None = Header(default=None)) -> int:
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
        access_data = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    user_id = session_store.get_user_id(access_data.session_id)
    if user_id is None or user_id != access_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )
    return access_data.user_id


@router.post("/otp/request", response_model=OtpResponse, response_model_exclude_none=True)
def request_phone_otp(payload: PhoneOtpRequest) -> OtpResponse:
    record = otp_store.request_otp(payload.phone_number, "onboarding")
    return OtpResponse(
        message="OTP sent",
        expires_in_seconds=settings.otp_ttl_seconds,
        otp=record.code if settings.otp_debug else None,
    )


@router.get("", response_model=list[UserResponse])
def list_users(_: int = Depends(get_current_user_id)) -> list[UserResponse]:
    return user_store.list_users()


@router.get("/me", response_model=UserResponse)
def get_me(user_id: int = Depends(get_current_user_id)) -> UserResponse:
    user = user_store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/me", response_model=UserResponse)
def update_me(payload: UserCreate, user_id: int = Depends(get_current_user_id)) -> UserResponse:
    try:
        return user_store.update_user(user_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, user_id: int = Depends(get_current_user_id)
) -> UserResponse:
    if payload.otp_code:
        if not otp_store.verify_otp(payload.phone_number, "onboarding", payload.otp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP",
            )
    elif settings.require_onboarding_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP is required to create a user",
        )
    try:
        return user_store.create_user(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
