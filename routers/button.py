from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import os

router = APIRouter(prefix="/api/inverter/command")
API_KEY = os.getenv("INVERTER_API_KEY", "changeme")

# Flag en mémoire — True = un appui web est en attente
_pending = False

@router.post("/button")
async def web_button_press(x_api_key: str = Header(None)):
    """Appelé par le site web quand l'utilisateur clique sur le bouton."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    global _pending
    _pending = True
    return {"status": "ok"}

@router.get("/button")
async def esp32_poll_button(x_api_key: str = Header(None)):
    """Interrogé par l'ESP32 toutes les 500ms."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    global _pending
    if _pending:
        _pending = False   # consommé
        return {"pending": True}
    return {"pending": False}