from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import engine, SessionLocal
from models import Base, User, RoleEnum
from utils.auth import hash_password
from routers import auth, admin, user
from dotenv import load_dotenv
import os
from routers import inverter , command ,button

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Admin Dashboard", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(user.router)
app.include_router(inverter.router)
app.include_router(command.router)
app.include_router(button.router)

@app.on_event("startup")
async def create_default_admin():
    db = SessionLocal()
    try:
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin")
        existing = db.query(User).filter(User.username == admin_username).first()
        if not existing:
            admin = User(
                username=admin_username,
                password_hash=hash_password(admin_password),
                full_name="Administrateur",
                role=RoleEnum.admin,
                is_active=True
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin créé : {admin_username} / {admin_password}")
        else:
            print(f"✅ Admin existe déjà : {admin_username}")
    finally:
        db.close()
