import os
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User, History, Alert
from utils.auth import decode_token, hash_password, verify_password
from models import VoltageReading
import json

router = APIRouter(prefix="/user")
templates = Jinja2Templates(directory="templates")
_INVERTER_API_KEY = os.getenv("INVERTER_API_KEY", "changeme")

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    return user

@router.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role == "admin":
        return RedirectResponse("/login", status_code=302)

    unread_alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read == False).count()

    # Récupère les 60 dernières mesures de tension (20 par source)
    
    readings = db.query(VoltageReading).order_by(VoltageReading.created_at.desc()).limit(60).all()
    readings.reverse()  # ordre chronologique

    
    chart_data = {
        "labels": [r.created_at.strftime('%H:%M:%S') for r in readings],
        "source1": [r.voltage_s1 for r in readings],
        "source2": [r.voltage_s2 for r in readings],
        "source3": [r.voltage_s3 for r in readings],
    }

    # Dernière lecture pour les cartes de statut
    last = readings[-1] if readings else None

    from models import InverterConfig
    cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()
    source_names = {
        "S1": cfg.name_s1 if cfg and cfg.name_s1 else "Source 1",
        "S2": cfg.name_s2 if cfg and cfg.name_s2 else "Source 2",
        "S3": cfg.name_s3 if cfg and cfg.name_s3 else "Source 3",
    }

    return templates.TemplateResponse("user/dashboard.html", {
        "request": request,
        "user": user,
        "unread_alerts": unread_alerts,
        "active_page": "dashboard",
        "last_reading": last,
        "chart_data": json.dumps(chart_data),
        "source_names": source_names,
        "inverter_api_key": _INVERTER_API_KEY,
    })

@router.get("/history", response_class=HTMLResponse)
async def user_history(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role == "admin":
        return RedirectResponse("/login", status_code=302)

    history = db.query(History).filter(History.user_id == user.id).order_by(History.created_at.desc()).all()
    unread_alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read == False).count()

    return templates.TemplateResponse("user/history.html", {
        "request": request,
        "user": user,
        "history": history,
        "unread_alerts": unread_alerts,
        "active_page": "history"
    })

@router.get("/alerts", response_class=HTMLResponse)
async def user_alerts(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role == "admin":
        return RedirectResponse("/login", status_code=302)

    alerts = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).all()
    unread_count = sum(1 for a in alerts if not a.is_read)

    # Mark all as read
    for alert in alerts:
        alert.is_read = True
    db.commit()

    return templates.TemplateResponse("user/alerts.html", {
        "request": request,
        "user": user,
        "alerts": alerts,
        "unread_alerts": unread_count,
        "active_page": "alerts"
    })

@router.get("/settings", response_class=HTMLResponse)
async def user_settings(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role == "admin":
        return RedirectResponse("/login", status_code=302)

    unread_alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read == False).count()

    return templates.TemplateResponse("user/settings.html", {
        "request": request,
        "user": user,
        "unread_alerts": unread_alerts,
        "inverter_api_key": _INVERTER_API_KEY,
        "active_page": "settings"
    })

@router.post("/settings/update-profile")
async def update_profile(
    request: Request,
    full_name: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    user.full_name = full_name
    user.email = email

    history = History(
        user_id=user.id,
        action="Mise à jour du profil",
        details="Informations de profil modifiées",
        ip_address=request.client.host
    )
    db.add(history)
    db.commit()

    return RedirectResponse("/user/settings?success=1", status_code=302)

@router.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if not verify_password(current_password, user.password_hash):
        unread_alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read == False).count()
        return templates.TemplateResponse("user/settings.html", {
            "request": request,
            "user": user,
            "unread_alerts": unread_alerts,
            "active_page": "settings",
            "pwd_error": "Mot de passe actuel incorrect"
        })

    user.password_hash = hash_password(new_password)
    history = History(
        user_id=user.id,
        action="Changement de mot de passe",
        details="Mot de passe modifié avec succès",
        ip_address=request.client.host
    )
    db.add(history)
    db.commit()

    return RedirectResponse("/user/settings?pwd_success=1", status_code=302)
