from typing import Type
from pydantic import BaseModel
from app.models.schema.otp import OtpEntry
from app.models.schema.session import SessionEntry
from app.models.schema.user import UserEntry

class Databases:
    session = SessionEntry
    otp = OtpEntry
    user = UserEntry

