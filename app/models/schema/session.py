from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class SessionEntry(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
