import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _build_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL", "")
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


DATABASE_URL = _build_database_url()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

Base = declarative_base()


def init_db() -> None:
    # Import models ONLY so SQLAlchemy knows them
    from app.models.schema import otp as _otp  # noqa: F401
    from app.models.schema  import session as _session  # noqa: F401
    from app.models.schema  import user as _user  # noqa: F401

    # 🚫 NO create_all
    # 🚫 NO inspect
    # 🚫 NO ALTER TABLE
    # 🚫 NO UPDATE queries
    return


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
