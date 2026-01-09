import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    otp_length: int = int(os.getenv("OTP_LENGTH", "6"))
    otp_ttl_seconds: int = int(os.getenv("OTP_TTL_SECONDS", "300"))
    otp_debug: bool = _env_bool("OTP_DEBUG", False)
    require_onboarding_otp: bool = _env_bool("REQUIRE_ONBOARDING_OTP", False)
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    otp_email_sender: str = (
        os.getenv("OTP_EMAIL_SENDER")
        or os.getenv("GMAIL_SENDER")
        or os.getenv("FROM_EMAIL", "")
    )
    otp_email_subject: str = os.getenv(
        "OTP_EMAIL_SUBJECT", "Your Pool Builder OTP"
    )
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number: str = os.getenv(
        "TWILIO_PHONE_NUMBER", os.getenv("PHONE_NUMBER", "")
    )
    default_country_code: str = os.getenv("DEFAULT_COUNTRY_CODE", "+1")
    gmail_token_file: str = os.getenv("GMAIL_TOKEN_FILE", "")
    gmail_credentials_file: str = os.getenv(
        "GMAIL_CREDENTIALS_FILE", os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    )
    seed_email: str = os.getenv("SEED_EMAIL", "").strip().lower()
    seed_first_name: str = os.getenv("SEED_FIRST_NAME", "").strip()
    seed_last_name: str = os.getenv("SEED_LAST_NAME", "").strip()


settings = Settings()
