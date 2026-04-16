from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


def utcnow() -> datetime:
    return datetime.utcnow()


class Vendo(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    mikrotik_router_id: Optional[UUID] = Field(default=None, index=True)
    mikrotik_hotspot_server: Optional[str] = Field(default=None, index=True)
    vlan_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class MikrotikRouter(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    base_url: str
    username_env: str
    password_env: str
    verify_tls: bool = True
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CoinDevice(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vendo_id: UUID = Field(index=True)
    name: str
    secret: str
    pulses_per_coin: int = 1
    coins_per_pulse: int = 1
    pending_pulses: int = 0
    pending_coins: int = 0
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Plan(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vendo_id: UUID = Field(index=True)
    name: str
    coins: int
    minutes: int
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CoinEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    coin_device_id: UUID = Field(index=True)
    vendo_id: UUID = Field(index=True)
    pulses: int
    coins: int
    client_mac: Optional[str] = Field(default=None, index=True)
    nonce: str = Field(index=True)
    signature: str
    accepted: bool = False
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Voucher(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vendo_id: UUID = Field(index=True)
    code: str = Field(index=True)
    minutes: int
    coins: int
    client_mac: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    redeemed_at: Optional[datetime] = Field(default=None, index=True)
