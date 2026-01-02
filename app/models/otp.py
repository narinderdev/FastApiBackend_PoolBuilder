from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint

from app.database import Base


class OtpEntry(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    identifier = Column(String(255), nullable=False)
    purpose = Column(String(32), nullable=False)
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("identifier", "purpose", name="uq_otp_identifier_purpose"),
        Index("ix_otp_expires_at", "expires_at"),
    )
