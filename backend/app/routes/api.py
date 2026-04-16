from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..mikrotik.routeros_rest import RouterAuth, RouterOSRest
from ..models import CoinDevice, CoinEvent, Plan, Voucher, Vendo, utcnow
from ..security import compute_hmac_hex, normalize_mac, secure_compare, gen_voucher_code


router = APIRouter(prefix="/api")


class CoinEventIn(BaseModel):
    device_id: UUID
    pulses: int = Field(ge=1, le=10000)
    ts: int
    nonce: str = Field(min_length=8, max_length=64)
    signature: str = Field(min_length=16, max_length=128)
    client_mac: Optional[str] = None


@router.get("/health")
def health():
    return {"ok": True}


class VendoResolvedOut(BaseModel):
    vendo_id: str
    vendo_name: str
    mikrotik_hotspot_server: Optional[str]
    vlan_id: Optional[int]
    coin_devices: list[dict[str, str]]
    plans: list[dict[str, int | str]]


@router.get("/vendo/resolve", response_model=VendoResolvedOut)
def resolve_vendo(
    session: Session = Depends(get_session),
    hotspot_server: Optional[str] = Query(default=None),
    vlan_id: Optional[int] = Query(default=None, ge=1, le=4094),
):
    hs = (hotspot_server or "").strip() or None
    candidates: list[Vendo] = []

    if hs is not None and vlan_id is not None:
        candidates = session.exec(
            select(Vendo).where(Vendo.mikrotik_hotspot_server == hs, Vendo.vlan_id == vlan_id).order_by(Vendo.created_at.desc())
        ).all()
    if not candidates and hs is not None:
        candidates = session.exec(
            select(Vendo).where(Vendo.mikrotik_hotspot_server == hs).order_by(Vendo.created_at.desc())
        ).all()
    if not candidates and vlan_id is not None:
        candidates = session.exec(select(Vendo).where(Vendo.vlan_id == vlan_id).order_by(Vendo.created_at.desc())).all()

    if not candidates:
        raise HTTPException(status_code=404, detail="No vendo match")

    vendo = candidates[0]
    devices = session.exec(
        select(CoinDevice).where(CoinDevice.vendo_id == vendo.id, CoinDevice.enabled == True).order_by(CoinDevice.created_at.desc())
    ).all()
    plans = session.exec(
        select(Plan).where(Plan.vendo_id == vendo.id, Plan.enabled == True).order_by(Plan.coins.asc())
    ).all()

    return VendoResolvedOut(
        vendo_id=str(vendo.id),
        vendo_name=vendo.name,
        mikrotik_hotspot_server=vendo.mikrotik_hotspot_server,
        vlan_id=vendo.vlan_id,
        coin_devices=[{"id": str(d.id), "name": d.name} for d in devices],
        plans=[{"id": str(p.id), "name": p.name, "coins": p.coins, "minutes": p.minutes} for p in plans],
    )


class PortalClaimIn(BaseModel):
    hotspot_server: Optional[str] = None
    vlan_id: Optional[int] = Field(default=None, ge=1, le=4094)
    client_mac: str


class PortalClaimOut(BaseModel):
    code: str
    minutes: int
    vendo_id: str


@router.post("/portal/claim", response_model=PortalClaimOut)
def portal_claim(payload: PortalClaimIn, session: Session = Depends(get_session)):
    client_mac = normalize_mac(payload.client_mac)
    if not client_mac:
        raise HTTPException(status_code=400, detail="Invalid client_mac")

    hs = (payload.hotspot_server or "").strip() or None
    candidates: list[Vendo] = []
    if hs is not None and payload.vlan_id is not None:
        candidates = session.exec(
            select(Vendo).where(Vendo.mikrotik_hotspot_server == hs, Vendo.vlan_id == payload.vlan_id).order_by(Vendo.created_at.desc())
        ).all()
    if not candidates and hs is not None:
        candidates = session.exec(
            select(Vendo).where(Vendo.mikrotik_hotspot_server == hs).order_by(Vendo.created_at.desc())
        ).all()
    if not candidates and payload.vlan_id is not None:
        candidates = session.exec(
            select(Vendo).where(Vendo.vlan_id == payload.vlan_id).order_by(Vendo.created_at.desc())
        ).all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No vendo match")

    vendo = candidates[0]
    voucher = session.exec(
        select(Voucher)
        .where(Voucher.vendo_id == vendo.id, Voucher.client_mac == client_mac, Voucher.redeemed_at == None)
        .order_by(Voucher.created_at.asc())
    ).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="No voucher yet")

    voucher.redeemed_at = utcnow()
    session.add(voucher)
    session.commit()
    base_url = (os.getenv("MIKROTIK_BASE_URL", "") or "").strip()
    username = (os.getenv("MIKROTIK_USERNAME", "") or "").strip()
    password = (os.getenv("MIKROTIK_PASSWORD", "") or "").strip()
    verify_tls = (os.getenv("MIKROTIK_VERIFY_TLS", "true") or "true").strip().lower() not in {"0", "false", "no"}
    if base_url and username and password:
        try:
            ros = RouterOSRest(RouterAuth(base_url=base_url, username=username, password=password, verify_tls=verify_tls))
            ros.create_hotspot_user(
                name=voucher.code,
                password=voucher.code,
                profile=None,
                limit_minutes=voucher.minutes,
                server=vendo.mikrotik_hotspot_server,
            )
        except httpx.HTTPError:
            pass
    return PortalClaimOut(code=voucher.code, minutes=voucher.minutes, vendo_id=str(voucher.vendo_id))



@router.post("/esp/coin-event")
def esp_coin_event(payload: CoinEventIn, session: Session = Depends(get_session)):
    device = session.get(CoinDevice, payload.device_id)
    if not device or not device.enabled:
        raise HTTPException(status_code=404, detail="Unknown device")

    client_mac = normalize_mac(payload.client_mac)
    if payload.client_mac and not client_mac:
        raise HTTPException(status_code=400, detail="Invalid client_mac")

    now = datetime.now(timezone.utc)
    ts_dt = datetime.fromtimestamp(payload.ts, tz=timezone.utc)
    if ts_dt < now - timedelta(minutes=10) or ts_dt > now + timedelta(minutes=2):
        raise HTTPException(status_code=400, detail="Timestamp out of range")

    existing_nonce = session.exec(
        select(CoinEvent).where(CoinEvent.coin_device_id == device.id, CoinEvent.nonce == payload.nonce)
    ).first()
    if existing_nonce:
        raise HTTPException(status_code=409, detail="Duplicate nonce")

    sign_message = f"{payload.device_id}|{payload.pulses}|{payload.ts}|{payload.nonce}|{client_mac or ''}"
    expected = compute_hmac_hex(device.secret, sign_message)
    if not secure_compare(expected, payload.signature.lower()):
        event = CoinEvent(
            coin_device_id=device.id,
            vendo_id=device.vendo_id,
            pulses=payload.pulses,
            coins=0,
            client_mac=client_mac,
            nonce=payload.nonce,
            signature=payload.signature,
            accepted=False,
        )
        session.add(event)
        session.commit()
        raise HTTPException(status_code=401, detail="Bad signature")

    total_pulses = device.pending_pulses + payload.pulses
    pulses_per_coin = max(1, device.pulses_per_coin)
    whole_coins = total_pulses // pulses_per_coin
    device.pending_pulses = total_pulses % pulses_per_coin

    coins = int(whole_coins) * max(1, device.coins_per_pulse)
    device.pending_coins += coins

    plans = session.exec(
        select(Plan).where(Plan.vendo_id == device.vendo_id, Plan.enabled == True).order_by(Plan.coins.desc())
    ).all()

    vouchers: list[dict[str, int | str]] = []
    remaining = device.pending_coins
    for plan in plans:
        if remaining < plan.coins:
            continue
        qty = remaining // plan.coins
        for _ in range(int(qty)):
            code = gen_voucher_code(8)
            voucher = Voucher(
                vendo_id=device.vendo_id,
                code=code,
                minutes=plan.minutes,
                coins=plan.coins,
                client_mac=client_mac,
            )
            session.add(voucher)
            vouchers.append({"code": code, "minutes": plan.minutes, "coins": plan.coins})
        remaining = remaining % plan.coins

    device.pending_coins = remaining
    event = CoinEvent(
        coin_device_id=device.id,
        vendo_id=device.vendo_id,
        pulses=payload.pulses,
        coins=coins,
        client_mac=client_mac,
        nonce=payload.nonce,
        signature=payload.signature,
        accepted=True,
    )
    session.add(event)
    session.add(device)
    session.commit()

    return {
        "accepted": True,
        "coins_added": coins,
        "pending_coins": device.pending_coins,
        "vouchers": vouchers,
    }

