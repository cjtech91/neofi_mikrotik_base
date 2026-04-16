from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from typing import Optional


MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([:-]?[0-9A-Fa-f]{2}){5}$")


def normalize_mac(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower().replace("-", ":")
    if len(v) == 12 and ":" not in v:
        v = ":".join(v[i : i + 2] for i in range(0, 12, 2))
    if not MAC_RE.match(v):
        return None
    return v


def compute_hmac_hex(secret: str, message: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def gen_voucher_code(length: int = 8) -> str:
    raw = base64.b32encode(secrets.token_bytes(16)).decode("ascii")
    raw = raw.replace("=", "")
    return raw[:length]
