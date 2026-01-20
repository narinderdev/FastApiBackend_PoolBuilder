from app.database import session_scope
from app.config import settings
from app.models.schema.db_config import Databases
from sqlalchemy import delete,select,update, and_, or_


def _delete_expired_record_(db, now):
    model = getattr(Databases, db)
    with session_scope() as session:
        session.execute(
            delete(model).where(model.expires_at <= now)
        )



def _delete_records(db: str, **kwargs):
    model = getattr(Databases, db)

    conditions = []
    for field, value in kwargs.items():
        if not hasattr(model, field):
            raise ValueError(
                f"{model.__name__} has no column '{field}'"
            )
        conditions.append(getattr(model, field) == value)

    with session_scope() as session:
        session.execute(
            delete(model).where(*conditions)
        )

def _add_record(db: str, **kwargs):
    model = getattr(Databases, db)

    instance = model(**kwargs)

    with session_scope() as session:
        session.add(instance)
        session.flush()
    return instance

def _select_records(db: str, *, order_by=None, **kwargs):
    model = getattr(Databases, db)

    conditions = [
        getattr(model, field) == value
        for field, value in kwargs.items()
    ]

    stmt = select(model).where(*conditions)

    if order_by is not None:
        stmt = stmt.order_by(getattr(model, order_by))

    with session_scope() as session:
        return session.execute(stmt).scalars().all()


def _select_one_or_none(db: str, **kwargs):
    model = getattr(Databases, db)

    conditions = []
    for field, value in kwargs.items():
        # If the value is a tuple, it's a complex condition (e.g., ("<", some_value))
        if isinstance(value, tuple):
            operator, condition_value = value
            if operator == ">":
                conditions.append(getattr(model, field) > condition_value)
            elif operator == "<":
                conditions.append(getattr(model, field) < condition_value)
            elif operator == "=":
                conditions.append(getattr(model, field) == condition_value)
            # Add other operators like >=, <=, != if needed
        else:
            conditions.append(getattr(model, field) == value)

    # Create the query with the constructed conditions
    with session_scope() as session:
        entry= session.execute(
            select(model).where(and_(*conditions))  # using `and_` for combining conditions
        ).scalar_one_or_none()
        session.flush()
        return entry

def _scalar_one_or_none_operation(
    *,
    db: str,
    now,
    clean_code,
    **filters
) -> bool:
    entry = _select_one_or_none(db, **filters)

    if entry is None:
        return False

    if entry.expires_at <= now:
        with session_scope() as session:
            session.delete(entry)
        return False

    if entry.code != clean_code:
        return False

    with session_scope() as session:
        session.delete(entry)

    return True


def _update_records(
    db: str,
    *,
    values: dict,
    **filters
):
    model = getattr(Databases, db)

    conditions = []
    for field, value in filters.items():
        if not hasattr(model, field):
            raise ValueError(
                f"{model.__name__} has no column '{field}'"
            )

        column = getattr(model, field)

        if value is None:
            conditions.append(column.is_(None))
        else:
            conditions.append(column == value)

    with session_scope() as session:
        result = session.execute(
            update(model)
            .where(*conditions)
            .values(**values)
        )

        return result.rowcount

