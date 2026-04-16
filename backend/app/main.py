from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import init_db
from .routes.admin import router as admin_router
from .routes.api import router as api_router


def ensure_sqlite_dir() -> None:
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///./data/"):
        os.makedirs("./data", exist_ok=True)


app = FastAPI(title="NeoFi MikroTik Hotspot Manager")

settings = get_settings()
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, https_only=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_sqlite_dir()
    init_db()


app.include_router(admin_router)
app.include_router(api_router)
