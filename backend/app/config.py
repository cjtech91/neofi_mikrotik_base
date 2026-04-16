from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_secret: str
    admin_username: str
    admin_password: str


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    session_secret = os.getenv("SESSION_SECRET", "change-me")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    return Settings(
        database_url=database_url,
        session_secret=session_secret,
        admin_username=admin_username,
        admin_password=admin_password,
    )

