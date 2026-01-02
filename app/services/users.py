from datetime import datetime, timezone
import re

from sqlalchemy import select

from app.database import session_scope
from app.models.user import UserEntry
from app.schemas.users import PermissionFlags, UserCreate, UserResponse


def _normalize_phone(phone_number: str) -> str:
    return re.sub(r"\D", "", phone_number)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _has_permission_flags(permissions: dict | None) -> bool:
    if not permissions:
        return False
    return any(permissions.values())


def _is_onboarded(entry: UserEntry) -> bool:
    return bool(
        entry.first_name
        and entry.address
        and entry.phone_number
        and _has_permission_flags(entry.permissions)
    )


class UserStore:
    def ensure_user_for_identifier(self, identifier: str) -> tuple[UserEntry, bool]:
        if "@" in identifier:
            key = _normalize_email(identifier)
            field = "email"
        else:
            key = _normalize_phone(identifier)
            field = "phone_number"
            if len(key) != 10:
                raise ValueError("Phone number must be 10 digits")

        with session_scope() as session:
            if field == "email":
                result = session.execute(select(UserEntry).where(UserEntry.email == key))
            else:
                result = session.execute(
                    select(UserEntry).where(UserEntry.phone_number == key)
                )
            entry = result.scalar_one_or_none()
            if entry:
                return entry, True

            now = datetime.now(timezone.utc)
            entry = UserEntry(
                email=key if field == "email" else None,
                phone_number=key if field == "phone_number" else None,
                permissions=None,
                created_at=now,
                updated_at=now,
                onboarded_at=None,
            )
            session.add(entry)
            session.flush()
            return entry, False

    def create_user(self, payload: UserCreate) -> UserResponse:
        now = datetime.now(timezone.utc)
        email = _normalize_email(payload.email) if payload.email else None
        phone_number = payload.phone_number
        permissions = payload.permissions.model_dump()

        with session_scope() as session:
            if email:
                existing = session.execute(
                    select(UserEntry).where(UserEntry.email == email)
                ).scalar_one_or_none()
                if existing:
                    raise ValueError("Email already in use")
            existing_phone = session.execute(
                select(UserEntry).where(UserEntry.phone_number == phone_number)
            ).scalar_one_or_none()
            if existing_phone:
                raise ValueError("Phone number already in use")

            entry = UserEntry(
                email=email,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone_number=phone_number,
                address=payload.address,
                job_title=payload.job_title,
                permissions=permissions,
                created_at=now,
                updated_at=now,
                onboarded_at=now if permissions else None,
            )
            if _is_onboarded(entry):
                entry.onboarded_at = now
            session.add(entry)
            session.flush()
            return self._to_response(entry)

    def update_user(self, user_id: int, payload: UserCreate) -> UserResponse:
        now = datetime.now(timezone.utc)
        email = _normalize_email(payload.email) if payload.email else None
        phone_number = payload.phone_number
        permissions = payload.permissions.model_dump()

        with session_scope() as session:
            entry = session.get(UserEntry, user_id)
            if entry is None:
                raise ValueError("User not found")

            if email and email != entry.email:
                existing = session.execute(
                    select(UserEntry).where(UserEntry.email == email)
                ).scalar_one_or_none()
                if existing and existing.id != user_id:
                    raise ValueError("Email already in use")
                entry.email = email

            if phone_number != entry.phone_number:
                existing_phone = session.execute(
                    select(UserEntry).where(UserEntry.phone_number == phone_number)
                ).scalar_one_or_none()
                if existing_phone and existing_phone.id != user_id:
                    raise ValueError("Phone number already in use")
                entry.phone_number = phone_number

            entry.first_name = payload.first_name
            entry.last_name = payload.last_name
            entry.address = payload.address
            entry.job_title = payload.job_title
            entry.permissions = permissions
            entry.updated_at = now
            if _is_onboarded(entry) and entry.onboarded_at is None:
                entry.onboarded_at = now

            session.flush()
            return self._to_response(entry)

    def list_users(self) -> list[UserResponse]:
        with session_scope() as session:
            result = session.execute(select(UserEntry).order_by(UserEntry.id))
            entries = result.scalars().all()
            return [self._to_response(entry) for entry in entries]

    def get_user(self, user_id: int) -> UserResponse | None:
        with session_scope() as session:
            entry = session.get(UserEntry, user_id)
            if entry is None:
                return None
            return self._to_response(entry)

    def exists_by_identifier(self, identifier: str) -> bool:
        if not identifier:
            return False
        if "@" in identifier:
            key = _normalize_email(identifier)
            field = UserEntry.email
        else:
            key = _normalize_phone(identifier)
            field = UserEntry.phone_number
        with session_scope() as session:
            result = session.execute(select(UserEntry).where(field == key))
            return result.scalar_one_or_none() is not None

    def _to_response(self, entry: UserEntry) -> UserResponse:
        permissions = entry.permissions or {}
        return UserResponse(
            id=entry.id,
            first_name=entry.first_name,
            last_name=entry.last_name,
            phone_number=entry.phone_number,
            address=entry.address,
            job_title=entry.job_title,
            permissions=PermissionFlags(**permissions),
            email=entry.email,
            created_at=entry.created_at,
            onboarded_at=entry.onboarded_at,
        )


user_store = UserStore()
