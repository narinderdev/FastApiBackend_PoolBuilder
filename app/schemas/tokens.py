from typing import Optional

from pydantic import BaseModel, Field


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2048)


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_token: Optional[str] = None
