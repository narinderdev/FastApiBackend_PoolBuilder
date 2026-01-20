import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.schemas.otp import OTP_LENGTH, OtpResponse
from app.schemas.users import UserCreate, UserResponse
from app.services.otp import otp_store
from app.services.sessions import session_store
from app.services.sms import SmsSendError, send_otp_sms
from app.services.tokens import TokenError, decode_access_token
from app.services.users import user_store,get_current_user_id


router = APIRouter(prefix="/users", tags=["users"])
LOGGER = logging.getLogger(__name__)



# @router.post("/otp/request", response_model=OtpResponse, response_model_exclude_none=True)
# def request_phone_otp(
#     payload: PhoneOtpRequest, user_id: int = Depends(get_current_user_id)
# ) -> OtpResponse:
#     LOGGER.info(
#         "Phone OTP request payload received country_code=%s phone_number=%s user_id=%s",
#         payload.country_code,
#         payload.phone_number,
#         user_id,
#     )
#     if user_store.is_phone_in_use(
#         payload.phone_number, payload.country_code, exclude_user_id=user_id
#     ):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="User already exists,use a different phone number",
#         )
#     identifier = f"{payload.country_code}{payload.phone_number}"
#     record = otp_store.request_otp(identifier, "onboarding")
#     try:
#         send_otp_sms(identifier, record.code, "onboarding")
#     except SmsSendError as exc:
#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=str(exc),
#         ) from exc
#     return OtpResponse(
#         message="OTP sent",
#         expires_in_seconds=settings.otp_ttl_seconds,
#         otp=record.code if settings.otp_debug else None,
#     )


# @router.post("/otp/verify", response_model=PhoneOtpVerifyResponse)
# def verify_phone_otp(
#     payload: PhoneOtpVerifyRequest, user_id: int = Depends(get_current_user_id)
# ) -> PhoneOtpVerifyResponse:
#     identifier = f"{payload.country_code}{payload.phone_number}"
#     verified = otp_store.verify_otp(identifier, "onboarding", payload.code)
#     if not verified:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid or expired OTP",
#         )
#     try:
#         user = user_store.verify_phone(
#             user_id, payload.phone_number, payload.country_code
#         )
#     except ValueError as exc:
#         detail = str(exc)
#         status_code = (
#             status.HTTP_404_NOT_FOUND
#             if "not found" in detail.lower()
#             else status.HTTP_400_BAD_REQUEST
#         )
#         raise HTTPException(status_code=status_code, detail=detail) from exc
#     return PhoneOtpVerifyResponse(
#         message="OTP verified",
#         phone_verified=bool(user.phone_verified),
#     )


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
