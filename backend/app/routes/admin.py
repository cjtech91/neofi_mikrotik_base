from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..models import CoinDevice, Plan, Vendo


templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("admin"))


@router.get("/login")
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = get_settings()
    if username == settings.admin_username and password == settings.admin_password:
        request.session["admin"] = True
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid login"})


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/admin")
def dashboard(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    vendos = session.exec(select(Vendo)).all()
    devices = session.exec(select(CoinDevice)).all()
    plans = session.exec(select(Plan)).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "nav": "dashboard",
            "vendo_count": len(vendos),
            "device_count": len(devices),
            "plan_count": len(plans),
        },
    )


@router.get("/admin/vendos")
def vendos_page(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    vendos = session.exec(select(Vendo).order_by(Vendo.created_at.desc())).all()
    return templates.TemplateResponse(
        "vendos.html",
        {"request": request, "nav": "vendos", "vendos": vendos},
    )


@router.post("/admin/vendos")
def vendos_create(
    request: Request,
    name: str = Form(...),
    mikrotik_hotspot_server: str | None = Form(None),
    vlan_id: int | None = Form(None),
    session: Session = Depends(get_session),
):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    vendo = Vendo(
        name=name.strip(),
        mikrotik_hotspot_server=(mikrotik_hotspot_server or "").strip() or None,
        vlan_id=vlan_id,
    )
    session.add(vendo)
    session.commit()
    return RedirectResponse(url="/admin/vendos", status_code=302)


@router.get("/admin/plans")
def plans_page(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    vendos = session.exec(select(Vendo).order_by(Vendo.created_at.desc())).all()
    plans = session.exec(select(Plan).order_by(Plan.created_at.desc())).all()
    return templates.TemplateResponse(
        "plans.html",
        {"request": request, "nav": "plans", "vendos": vendos, "plans": plans},
    )


@router.post("/admin/plans")
def plans_create(
    request: Request,
    vendo_id: str = Form(...),
    name: str = Form(...),
    coins: int = Form(...),
    minutes: int = Form(...),
    session: Session = Depends(get_session),
):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    plan = Plan(vendo_id=vendo_id, name=name.strip(), coins=coins, minutes=minutes, enabled=True)
    session.add(plan)
    session.commit()
    return RedirectResponse(url="/admin/plans", status_code=302)


@router.get("/admin/devices")
def devices_page(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    vendos = session.exec(select(Vendo).order_by(Vendo.created_at.desc())).all()
    devices = session.exec(select(CoinDevice).order_by(CoinDevice.created_at.desc())).all()
    return templates.TemplateResponse(
        "devices.html",
        {"request": request, "nav": "devices", "vendos": vendos, "devices": devices},
    )


@router.post("/admin/devices")
def devices_create(
    request: Request,
    vendo_id: str = Form(...),
    name: str = Form(...),
    secret: str | None = Form(None),
    pulses_per_coin: int = Form(1),
    coins_per_pulse: int = Form(1),
    session: Session = Depends(get_session),
):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    device = CoinDevice(
        vendo_id=vendo_id,
        name=name.strip(),
        secret=(secret or "").strip() or secrets.token_hex(16),
        pulses_per_coin=max(1, pulses_per_coin),
        coins_per_pulse=max(1, coins_per_pulse),
        enabled=True,
    )
    session.add(device)
    session.commit()
    return RedirectResponse(url="/admin/devices", status_code=302)
