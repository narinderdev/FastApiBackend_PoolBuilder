from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String

from app.database import Base


class UserEntry(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=True, unique=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    country_code = Column(String(8), nullable=True)
    phone_number = Column(String(10), nullable=True, unique=True)
    address = Column(String(255), nullable=True)
    job_title = Column(String(100), nullable=True)
    permissions = Column(JSON, nullable=True)
    role = Column(String(50), nullable=True)
    phone_provided = Column(Boolean, nullable=True)
    phone_verified = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    onboarded_at = Column(DateTime(timezone=True), nullable=True)