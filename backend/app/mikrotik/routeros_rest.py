from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Optional

import httpx


def minutes_to_ros_duration(minutes: int) -> str:
    if minutes <= 0:
        return "0s"
    seconds = minutes * 60
    parts: list[str] = []
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs:
        parts.append(f"{secs}s")
    return "".join(parts)


@dataclass(frozen=True)
class RouterAuth:
    base_url: str
    username: str
    password: str
    verify_tls: bool = True


def resolve_router_auth(base_url: str, username_env: str, password_env: str, verify_tls: bool = True) -> RouterAuth:
    username = os.getenv(username_env, "")
    password = os.getenv(password_env, "")
    return RouterAuth(base_url=base_url, username=username, password=password, verify_tls=verify_tls)


class RouterOSRest:
    def __init__(self, auth: RouterAuth):
        self._auth = auth

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._auth.base_url.rstrip("/"),
            auth=(self._auth.username, self._auth.password),
            verify=self._auth.verify_tls,
            timeout=10.0,
        )

    def create_hotspot_user(
        self,
        name: str,
        password: str,
        profile: Optional[str],
        limit_minutes: int,
        server: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "password": password,
            "limit-uptime": minutes_to_ros_duration(limit_minutes),
        }
        if profile:
            payload["profile"] = profile
        if server:
            payload["server"] = server
        with self._client() as client:
            r = client.post("/rest/ip/hotspot/user", json=payload)
            r.raise_for_status()
            return r.json()

    def list_hotspot_active(self, server: Optional[str] = None) -> list[dict[str, Any]]:
        with self._client() as client:
            r = client.get("/rest/ip/hotspot/active")
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                return []
            if not server:
                return data
            return [x for x in data if x.get("server") == server]

