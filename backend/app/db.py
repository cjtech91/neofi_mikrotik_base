from __future__ import annotations

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text

from .config import get_settings


def get_engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite:"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = get_engine()


def _sqlite_has_column(table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
    for row in rows:
        if str(row[1]) == column_name:
            return True
    return False


def _sqlite_add_column(table_name: str, column_def: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
        conn.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    settings = get_settings()
    if settings.database_url.startswith("sqlite:"):
        if not _sqlite_has_column("coindevice", "pending_pulses"):
            _sqlite_add_column("coindevice", "pending_pulses INTEGER NOT NULL DEFAULT 0")


def get_session():
    with Session(engine) as session:
        yield session
