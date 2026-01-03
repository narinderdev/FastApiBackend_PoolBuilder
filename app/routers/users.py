import re

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.schemas.otp import OTP_LENGTH, OtpResponse
from app.schemas.users import UserCreate, UserResponse
from app.services.otp import otp_store
from app.services.sessions import session_store
from app.services.tokens import TokenError, decode_access_token
from app.services.users import user_store

router = APIRouter(prefix="/users", tags=["users"])


class PhoneOtpRequest(BaseModel):
    country_code: str = Field(min_length=1, max_length=8)
    phone_number: str = Field(min_length=10, max_length=10)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            raise ValueError("Phone number must be 10 digits")
        if digits.startswith("0"):
            raise ValueError("Phone number cannot start with 0")
        return digits

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 1 or len(digits) > 4:
            raise ValueError("Country code must be 1 to 4 digits")
        return f"+{digits}"


class PhoneOtpVerifyRequest(BaseModel):
    country_code: str = Field(min_length=1, max_length=8)
    phone_number: str = Field(min_length=10, max_length=10)
    code: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            raise ValueError("Phone number must be 10 digits")
        if digits.startswith("0"):
            raise ValueError("Phone number cannot start with 0")
        return digits

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 1 or len(digits) > 4:
            raise ValueError("Country code must be 1 to 4 digits")
        return f"+{digits}"


class PhoneOtpVerifyResponse(BaseModel):
    message: str
    phone_verified: bool


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
def request_phone_otp(
    payload: PhoneOtpRequest, user_id: int = Depends(get_current_user_id)
) -> OtpResponse:
    if user_store.is_phone_in_use(
        payload.phone_number, payload.country_code, exclude_user_id=user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists,use a different phone number",
        )
    identifier = f"{payload.country_code}{payload.phone_number}"
    record = otp_store.request_otp(identifier, "onboarding")
    return OtpResponse(
        message="OTP sent",
        expires_in_seconds=settings.otp_ttl_seconds,
        otp=record.code if settings.otp_debug else None,
    )


@router.post("/otp/verify", response_model=PhoneOtpVerifyResponse)
def verify_phone_otp(
    payload: PhoneOtpVerifyRequest, user_id: int = Depends(get_current_user_id)
) -> PhoneOtpVerifyResponse:
    identifier = f"{payload.country_code}{payload.phone_number}"
    verified = otp_store.verify_otp(identifier, "onboarding", payload.code)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )
    try:
        user = user_store.verify_phone(
            user_id, payload.phone_number, payload.country_code
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return PhoneOtpVerifyResponse(
        message="OTP verified",
        phone_verified=bool(user.phone_verified),
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
    if payload.phone_number:
        try:
            is_verified = user_store.is_phone_verified(
                user_id, payload.phone_number, payload.country_code
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        if not is_verified:
            if not payload.otp_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OTP is required when a phone number is provided",
                )
            identifier = f"{payload.country_code}{payload.phone_number}"
            if not otp_store.verify_otp(identifier, "onboarding", payload.otp_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired OTP",
                )
            user_store.verify_phone(user_id, payload.phone_number, payload.country_code)
    elif settings.require_onboarding_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP is required to create a user",
        )
    try:
        return user_store.update_user(user_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    payload: UserCreate, user_id: int, _: int = Depends(get_current_user_id)
) -> UserResponse:
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
    phone_verified = False
    if payload.phone_number:
        if not payload.otp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP is required when a phone number is provided",
            )
        identifier = f"{payload.country_code}{payload.phone_number}"
        if not otp_store.verify_otp(identifier, "onboarding", payload.otp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP",
            )
        phone_verified = True
    elif settings.require_onboarding_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP is required to create a user",
        )
    try:
        return user_store.create_user(payload, phone_verified=phone_verified)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
