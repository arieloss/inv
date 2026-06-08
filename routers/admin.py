from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User, History, Alert
from utils.auth import hash_password, decode_token
from datetime import datetime

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

def get_admin_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username, User.role == "admin").first()
    return user

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_user(request, db)
    if not admin:
        return RedirectResponse("/login", status_code=302)

    total_users = db.query(User).filter(User.role == "user").count()
    active_users = db.query(User).filter(User.role == "user", User.is_active == True).count()
    users = db.query(User).filter(User.role == "user").order_by(User.created_at.desc()).all()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": admin,
        "total_users": total_users,
        "active_users": active_users,
        "users": users
    })

@router.post("/create-user", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    full_name: str = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_user(request, db)
    if not admin:
        return RedirectResponse("/login", status_code=302)

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        total_users = db.query(User).filter(User.role == "user").count()
        active_users = db.query(User).filter(User.role == "user", User.is_active == True).count()
        users = db.query(User).filter(User.role == "user").order_by(User.created_at.desc()).all()
        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "admin": admin,
            "total_users": total_users,
            "active_users": active_users,
            "users": users,
            "error": f"Le nom d'utilisateur '{username}' existe déjà.",
            "show_modal": True
        })

    new_user = User(
        username=username,
        password_hash=hash_password(password),
        email=email if email else None,
        full_name=full_name if full_name else None,
        role="user",
        is_active=True
    )
    db.add(new_user)

    history = History(
        user_id=admin.id,
        action="Création d'utilisateur",
        details=f"Admin '{admin.username}' a créé l'utilisateur '{username}'",
        ip_address=request.client.host
    )
    db.add(history)
    db.commit()

    return RedirectResponse("/admin/dashboard?success=1", status_code=302)

@router.post("/toggle-user/{user_id}")
async def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_user(request, db)
    if not admin:
        return JSONResponse({"error": "Non autorisé"}, status_code=401)

    user = db.query(User).filter(User.id == user_id, User.role == "user").first()
    if not user:
        return JSONResponse({"error": "Utilisateur introuvable"}, status_code=404)

    user.is_active = not user.is_active
    db.commit()
    return JSONResponse({"status": "active" if user.is_active else "inactive"})

@router.delete("/delete-user/{user_id}")
async def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_user(request, db)
    if not admin:
        return JSONResponse({"error": "Non autorisé"}, status_code=401)

    user = db.query(User).filter(User.id == user_id, User.role == "user").first()
    if not user:
        return JSONResponse({"error": "Utilisateur introuvable"}, status_code=404)

    db.delete(user)
    history = History(
        user_id=admin.id,
        action="Suppression d'utilisateur",
        details=f"Admin '{admin.username}' a supprimé l'utilisateur '{user.username}'",
        ip_address=request.client.host
    )
    db.add(history)
    db.commit()
    return JSONResponse({"success": True})
