from typing import Literal

from pydantic import BaseModel, Field

from app.config import settings

OTP_LENGTH = settings.otp_length


class OtpRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    purpose: Literal["login", "onboarding"] = "login"


class OtpResponse(BaseModel):
    message: str
    expires_in_seconds: int
    otp: str | None = None


class OtpVerifyRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    purpose: Literal["login", "onboarding"] = "login"
    code: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH)


class OtpVerifyResponse(BaseModel):
    message: str
    verified: bool
    role: Literal["admin", "onboarded_user"] | None = None
    is_admin: bool | None = None
    user_exists: bool | None = None
    user_onboarded: bool | None = None
    user_id: int | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in_seconds: int | None = None
    refresh_expires_in_seconds: int | None = None
