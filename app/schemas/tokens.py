from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2048)


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_token: Optional[str] = None

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

