import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings

OTP_LENGTH = settings.otp_length


class PermissionFlags(BaseModel):
    sales_marketing: bool = False
    project_management: bool = False
    access_other_users: bool = False
    view_admin_panel: bool = False


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)
    country_code: Optional[str] = Field(default=None, max_length=8)
    phone_number: Optional[str] = Field(default=None, max_length=10)
    address: str = Field(min_length=1, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=100)
    permissions: PermissionFlags
    email: Optional[str] = None
    otp_code: Optional[str] = Field(
        default=None, min_length=OTP_LENGTH, max_length=OTP_LENGTH
    )

    @field_validator("first_name", "address")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required")
        return cleaned

    @field_validator("last_name", "job_title")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if not digits:
            return None
        if len(digits) != 10:
            raise ValueError("Phone number must be 10 digits")
        if digits.startswith("0"):
            raise ValueError("Phone number cannot start with 0")
        return digits

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if not digits:
            return None
        if len(digits) < 1 or len(digits) > 4:
            raise ValueError("Country code must be 1 to 4 digits")
        return f"+{digits}"

    @model_validator(mode="after")
    def validate_permissions(self) -> "UserCreate":
        if self.phone_number and not self.country_code:
            raise ValueError("Country code is required when phone number is provided")
        if not any(self.permissions.model_dump().values()):
            raise ValueError("At least one permission must be selected")
        return self


class UserResponse(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    job_title: Optional[str] = None
    permissions: PermissionFlags = Field(default_factory=PermissionFlags)
    email: Optional[str] = None
    role: Optional[str] = None
    country_code: Optional[str] = None
    phone_verified: Optional[bool] = None
    created_at: datetime
    onboarded_at: Optional[datetime] = None
