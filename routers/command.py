from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
from models import InverterConfig
from pydantic import BaseModel, field_validator
from typing import Optional, Dict
import os
import logging

router = APIRouter(prefix="/api/inverter")

API_KEY = os.getenv("INVERTER_API_KEY", "changeme")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("command")


# ─── Schéma — push de config depuis l'ESP32 ──────────────────────────────────
class ESP32ConfigPush(BaseModel):
    """
    Envoyé par l'ESP32 quand l'utilisateur appuie sur BP1 et que le WiFi
    est disponible, ou lors de la synchronisation différée après reconnexion.

    Exemple :
        {
          "priorities":     [2, 1, 3],
          "local_version":  4,          // version que l'ESP32 avait avant la modif
          "source_names":   {"S1": "EDF", "S2": "Groupe", "S3": "Solaire"}
        }

    Le serveur n'accepte le push que si local_version == config_version en base
    (contrôle de concurrence optimiste) OU si force=true.
    """
    priorities:    list[int]
    local_version: int
    source_names:  Optional[Dict[str, str]] = None   # facultatif : l'ESP32 peut ne pas connaître les noms
    force:         bool = False                       # écrase sans vérification de version

    @field_validator("priorities")
    @classmethod
    def check_priorities(cls, v):
        if len(v) != 3:
            raise ValueError("priorities doit contenir exactement 3 valeurs")
        if sorted(v) != [1, 2, 3]:
            raise ValueError("priorities doit être une permutation de [1, 2, 3]")
        return v


# ─── Schéma — acquittement ESP32 ─────────────────────────────────────────────
class ESP32Ack(BaseModel):
    """
    Envoyé par l'ESP32 après avoir appliqué une config reçue du serveur.

    Exemple :
        { "applied_version": 5 }
    """
    applied_version: int


# ─── GET /api/inverter/command — l'ESP32 interroge si sa config est à jour ───
@router.get("/command")
async def get_command(
    local_version: int,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    L'ESP32 appelle cet endpoint périodiquement (toutes les CONFIG_SYNC_INTERVAL_MS).
    Il transmet sa version locale via le query-param ?local_version=N.

    Réponses possibles :
      • { "action": "none" }
            → la config est à jour, l'ESP32 ne fait rien.

      • { "action": "update",
          "config_version": 7,
          "priorities": [2, 1, 3],
          "source_names": { "S1": "EDF", ... } }
            → le serveur a une version plus récente ; l'ESP32 doit l'appliquer
              puis appeler POST /command/ack.

    Architecture :
        ESP32 ──GET /command?local_version=N──► Serveur
               ◄── { action, [nouvelle config] } ──
        Si action == "update" :
        ESP32 applique localement + sauvegarde Preferences
        ESP32 ──POST /command/ack { applied_version }──► Serveur
    """
    logger.info("GET /command — local_version=%d", local_version)

    if x_api_key != API_KEY:
        logger.warning("Clé API invalide pour GET /command: %s", x_api_key)
        raise HTTPException(status_code=401, detail="Clé API invalide")

    cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()

    # Pas encore de config en base → rien à synchroniser
    if cfg is None:
        return {"action": "none"}

    # Config à jour côté ESP32
    if local_version >= cfg.config_version:
        return {"action": "none"}

    # Le serveur a une version plus récente → l'envoyer à l'ESP32
    logger.info(
        "Config distante v%d > locale v%d — envoi mise à jour à l'ESP32",
        cfg.config_version, local_version,
    )
    return {
        "action":         "update",
        "config_version": cfg.config_version,
        "priorities":     [cfg.priority_s1, cfg.priority_s2, cfg.priority_s3],
        "source_names":   {
            "S1": cfg.name_s1,
            "S2": cfg.name_s2,
            "S3": cfg.name_s3,
        },
        "updated_by":     cfg.updated_by,
    }


# ─── POST /api/inverter/command/push — l'ESP32 pousse sa nouvelle config ─────
@router.post("/command/push")
async def push_config(
    data: ESP32ConfigPush,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Appelé par l'ESP32 dans deux situations :
      1. Immédiatement après un appui BP1 si le WiFi est disponible.
      2. En différé, dès que la connexion revient, si une modif avait été
         faite hors-ligne (pending_push dans Preferences).

    Contrôle de concurrence optimiste :
      - Si local_version == version en base  → le push est accepté.
      - Si local_version <  version en base  → conflit : le serveur est plus
        récent ; le push est refusé avec 409 et la config serveur est renvoyée
        pour que l'ESP32 se mette à jour.
      - Si force == true                     → le push est accepté sans
        vérification (utile en cas de récupération manuelle).
    """
    logger.info("POST /command/push — %s", data.dict())

    if x_api_key != API_KEY:
        logger.warning("Clé API invalide pour /command/push: %s", x_api_key)
        raise HTTPException(status_code=401, detail="Clé API invalide")

    cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()
    if cfg is None:
        cfg = InverterConfig(id=1)
        db.add(cfg)

    # ── Contrôle de concurrence ───────────────────────────────────────────
    if not data.force and data.local_version < (cfg.config_version or 1):
        logger.warning(
            "Conflit push ESP32 : local_version=%d < server_version=%d",
            data.local_version, cfg.config_version,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error":          "version_conflict",
                "server_version": cfg.config_version,
                "priorities":     [cfg.priority_s1, cfg.priority_s2, cfg.priority_s3],
                "source_names":   {
                    "S1": cfg.name_s1,
                    "S2": cfg.name_s2,
                    "S3": cfg.name_s3,
                },
            },
        )

    # ── Appliquer la nouvelle config ──────────────────────────────────────
    cfg.priority_s1    = data.priorities[0]
    cfg.priority_s2    = data.priorities[1]
    cfg.priority_s3    = data.priorities[2]
    cfg.config_version = (cfg.config_version or 1) + 1
    cfg.updated_by     = "esp32"

    # Ne pas écraser les noms si l'ESP32 ne les envoie pas
    if data.source_names:
        for key in ("S1", "S2", "S3"):
            if key in data.source_names:
                name = data.source_names[key].strip()
                if name:
                    setattr(cfg, f"name_{key.lower()}", name[:30])

    db.commit()
    db.refresh(cfg)

    logger.info(
        "Push ESP32 accepté — nouvelle version=%d, priorités=%s",
        cfg.config_version, data.priorities,
    )
    return {
        "status":         "ok",
        "config_version": cfg.config_version,
        "priorities":     data.priorities,
    }


# ─── POST /api/inverter/command/ack — ESP32 confirme l'application ───────────
@router.post("/command/ack")
async def ack_config(
    data: ESP32Ack,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Envoyé par l'ESP32 après avoir appliqué avec succès une config reçue via
    GET /command (action == "update").

    Permet au serveur de logger la confirmation et de vérifier que l'ESP32
    a bien la dernière version.
    """
    logger.info("POST /command/ack — applied_version=%d", data.applied_version)

    if x_api_key != API_KEY:
        logger.warning("Clé API invalide pour /command/ack: %s", x_api_key)
        raise HTTPException(status_code=401, detail="Clé API invalide")

    cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()

    if cfg is None:
        raise HTTPException(status_code=404, detail="Aucune configuration en base")

    if data.applied_version != cfg.config_version:
        logger.warning(
            "ACK version mismatch : esp32 applied v%d mais serveur est à v%d",
            data.applied_version, cfg.config_version,
        )
        return {
            "status":         "version_mismatch",
            "server_version": cfg.config_version,
        }

    logger.info("ESP32 synchronisé sur la version %d ✓", data.applied_version)
    return {"status": "ok", "synced_version": data.applied_version}