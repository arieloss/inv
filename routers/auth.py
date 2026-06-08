from fastapi import APIRouter, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User, History
from utils.auth import verify_password, create_access_token, decode_token
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

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

@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse("/admin/dashboard", status_code=302)
        return RedirectResponse("/user/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse("/admin/dashboard", status_code=302)
        return RedirectResponse("/user/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nom d'utilisateur ou mot de passe incorrect"
        })
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Compte désactivé. Contactez l'administrateur."
        })

    # Log history
    history = History(
        user_id=user.id,
        action="Connexion",
        details=f"Connexion réussie de {username}",
        ip_address=request.client.host
    )
    db.add(history)
    db.commit()

    token = create_access_token({"sub": user.username, "role": user.role})
    if user.role == "admin":
        redirect_url = "/admin/dashboard"
    else:
        redirect_url = "/user/dashboard"

    response = RedirectResponse(redirect_url, status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=3600)
    return response

@router.get("/logout")
async def logout(response: Response):
    redirect = RedirectResponse("/login", status_code=302)
    redirect.delete_cookie("access_token")
    return redirect
