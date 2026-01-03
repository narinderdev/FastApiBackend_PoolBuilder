from datetime import datetime, timezone
import re

from sqlalchemy import select

from app.config import settings
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


def _role_for_email(email: str | None) -> str:
    seed_email = settings.seed_email
    if not seed_email or not email:
        return "onboarded_user"
    return "admin" if email.strip().lower() == seed_email else "onboarded_user"


def _seed_profile_for_email(email: str | None) -> tuple[str | None, str | None]:
    seed_email = settings.seed_email
    if not seed_email or not email:
        return None, None
    if email.strip().lower() != seed_email:
        return None, None
    first_name = settings.seed_first_name or None
    last_name = settings.seed_last_name or None
    return first_name, last_name


def _apply_seed_profile(entry: UserEntry) -> bool:
    first_name, last_name = _seed_profile_for_email(entry.email)
    updated = False
    if first_name and not entry.first_name:
        entry.first_name = first_name
        updated = True
    if last_name and not entry.last_name:
        entry.last_name = last_name
        updated = True
    return updated


def _get_role(entry: UserEntry) -> str:
    return entry.role or "onboarded_user"


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
                role = _role_for_email(entry.email)
                if entry.role != role:
                    entry.role = role
                    entry.updated_at = datetime.now(timezone.utc)
                if _apply_seed_profile(entry):
                    entry.updated_at = datetime.now(timezone.utc)
                session.flush()
                return entry, True

            now = datetime.now(timezone.utc)
            role = _role_for_email(key if field == "email" else None)
            first_name, last_name = _seed_profile_for_email(
                key if field == "email" else None
            )
            entry = UserEntry(
                email=key if field == "email" else None,
                first_name=first_name,
                last_name=last_name,
                phone_number=key if field == "phone_number" else None,
                permissions=None,
                role=role,
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
                role=_role_for_email(email),
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
                entry.role = _role_for_email(entry.email)

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
            if entry.role is None:
                entry.role = _role_for_email(entry.email)
            _apply_seed_profile(entry)
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

    def ensure_roles(self) -> None:
        now = datetime.now(timezone.utc)
        with session_scope() as session:
            entries = session.execute(select(UserEntry)).scalars().all()
            for entry in entries:
                role = _role_for_email(entry.email)
                updated = False
                if entry.role != role:
                    entry.role = role
                    updated = True
                if _apply_seed_profile(entry):
                    updated = True
                if updated:
                    entry.updated_at = now
            session.flush()

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
            role=_get_role(entry),
            created_at=entry.created_at,
            onboarded_at=entry.onboarded_at,
        )


user_store = UserStore()
