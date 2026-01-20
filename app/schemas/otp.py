from typing import Literal, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass
from datetime import datetime
from app.config import settings

OTP_LENGTH = settings.otp_length


class OtpRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    purpose: Literal["login", "onboarding"] = "login"


class OtpResponse(BaseModel):
    message: str
    expires_in_seconds: int
    otp: Optional[str] = None


class OtpVerifyRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    purpose: Literal["login", "onboarding"] = "login"
    code: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH)


class OtpVerifyResponse(BaseModel):
    message: str
    verified: bool
    role: Optional[Literal["admin", "onboarded_user"]] = None
    is_admin: Optional[bool] = None
    user_exists: Optional[bool] = None
    user_onboarded: Optional[bool] = None
    user_id: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    refresh_expires_in_seconds: Optional[int] = None

@dataclass(frozen=True)
class OtpRecord:
    code: str
    expires_at: datetime
    purpose: str