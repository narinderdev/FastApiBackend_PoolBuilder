from datetime import datetime
import re

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
    last_name: str | None = Field(default=None, max_length=50)
    phone_number: str = Field(min_length=10, max_length=32)
    address: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=100)
    permissions: PermissionFlags
    email: str | None = None
    otp_code: str | None = Field(
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
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            raise ValueError("Phone number must be 10 digits")
        return digits

    @model_validator(mode="after")
    def validate_permissions(self) -> "UserCreate":
        if not any(self.permissions.model_dump().values()):
            raise ValueError("At least one permission must be selected")
        return self


class UserResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    job_title: str | None = None
    permissions: PermissionFlags = Field(default_factory=PermissionFlags)
    email: str | None = None
    created_at: datetime
    onboarded_at: datetime | None = None
