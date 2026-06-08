from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
from models import VoltageReading, InverterConfig
from pydantic import BaseModel, field_validator
from typing import Optional, Dict
import os
import logging

router = APIRouter(prefix="/api/inverter")

API_KEY = os.getenv("INVERTER_API_KEY", "changeme")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inverter")


# ─── Schéma entrant — données temps réel ESP32 ───────────────────────────────
class VoltageData(BaseModel):
    """
    Correspond exactement au JSON construit dans tacheEnvoiHTTP() :

        { "U1":"220.5", "U2":"0.0", "U3":"219.0",
          "S1":true, "S2":false, "S3":true,
          "sourceActive":3,
          "P1":1, "P2":3, "P3":2,
          "TA":5000, "TB":3000,
          "uptime":3600 }

    U1/U2/U3 arrivent en string (serialized() côté Arduino) — le validator
    les convertit automatiquement en float.
    """

    U1: Optional[str] = None
    U2: Optional[str] = None
    U3: Optional[str] = None

    S1: Optional[bool] = None
    S2: Optional[bool] = None
    S3: Optional[bool] = None

    sourceActive: Optional[int] = None

    P1: Optional[int] = None
    P2: Optional[int] = None
    P3: Optional[int] = None

    TA: Optional[int] = None
    TB: Optional[int] = None

    uptime: Optional[int] = None

    frequency_s1: Optional[float] = None
    frequency_s2: Optional[float] = None
    frequency_s3: Optional[float] = None

    @field_validator("U1", "U2", "U3", mode="before")
    @classmethod
    def parse_voltage(cls, v):
        if v is None:
            return None
        try:
            return str(float(v))
        except (ValueError, TypeError):
            raise ValueError(f"Tension invalide : {v!r}")

    def voltage_float(self, field: str) -> Optional[float]:
        val = getattr(self, field)
        return float(val) if val is not None else None


# ─── Schéma — configuration priorités & noms de sources ─────────────────────
class InverterConfigSchema(BaseModel):
    """
    Reçu depuis la page settings.html via POST /api/inverter/config.

    Exemple :
        {
          "priorities": [2, 1, 3],          // rang de chaque source (1=prioritaire)
          "source_names": {
            "S1": "Réseau EDF",
            "S2": "Groupe électrogène",
            "S3": "Panneau solaire"
          }
        }

    priorities[i] correspond à la source S(i+1).
    Ex : priorities=[2,1,3] → S2 est prioritaire, S1 seconde, S3 troisième.
    """
    priorities: list[int]           # longueur 3 attendue
    source_names: Dict[str, str]    # clés "S1", "S2", "S3"

    @field_validator("priorities")
    @classmethod
    def check_priorities(cls, v):
        if len(v) != 3:
            raise ValueError("priorities doit contenir exactement 3 valeurs")
        if sorted(v) != [1, 2, 3]:
            raise ValueError("priorities doit être une permutation de [1, 2, 3]")
        return v

    @field_validator("source_names")
    @classmethod
    def check_names(cls, v):
        for key in ("S1", "S2", "S3"):
            if key not in v:
                raise ValueError(f"source_names manque la clé '{key}'")
            name = v[key].strip()
            if not name:
                raise ValueError(f"Le nom de {key} ne peut pas être vide")
            if len(name) > 30:
                raise ValueError(f"Le nom de {key} dépasse 30 caractères")
            v[key] = name
        return v


# ─── POST /api/inverter/readings — données temps réel de l'ESP32 ─────────────
@router.post("/readings")
async def post_reading(
    data: VoltageData,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    logger.info("POST /readings reçu avec data: %s", data.dict())
    try:
        if x_api_key != API_KEY:
            logger.warning("Clé API invalide: %s", x_api_key)
            raise HTTPException(status_code=401, detail="Clé API invalide")

        reading = VoltageReading(
            voltage_s1   = data.voltage_float("U1"),
            voltage_s2   = data.voltage_float("U2"),
            voltage_s3   = data.voltage_float("U3"),
            source_s1_ok = data.S1,
            source_s2_ok = data.S2,
            source_s3_ok = data.S3,
            active_source = data.sourceActive,
            priority_s1  = data.P1,
            priority_s2  = data.P2,
            priority_s3  = data.P3,
            delay_ta     = data.TA,
            delay_tb     = data.TB,
            uptime       = data.uptime,
            frequency_s1 = data.frequency_s1,
            frequency_s2 = data.frequency_s2,
            frequency_s3 = data.frequency_s3,
        )

        db.add(reading)
        db.commit()
        db.refresh(reading)
        logger.info("Lecture enregistrée avec succès, id: %s", reading.id)
        return {"status": "ok", "id": reading.id}
    except Exception as e:
        logger.error("Erreur lors de l'enregistrement de la lecture: %s", e)
        raise


# ─── GET /api/inverter/readings/latest — 60 dernières mesures ────────────────
@router.get("/readings/latest")
async def get_latest(db: Session = Depends(get_db)):
    logger.info("GET /readings/latest reçu")
    try:
        readings = (
            db.query(VoltageReading)
            .order_by(VoltageReading.created_at.desc())
            .limit(60)
            .all()
        )
        readings.reverse()
        logger.info("%d lectures retournées.", len(readings))
        return readings
    except Exception as e:
        logger.error("Erreur lors de la récupération des lectures: %s", e)
        raise


# ─── POST /api/inverter/config — enregistre priorités + noms sources ─────────
@router.post("/config")
async def post_config(
    data: InverterConfigSchema,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Reçoit la configuration des priorités et des noms de sources depuis
    la page settings.html et la persiste dans la table inverter_config.

    La config active est la dernière ligne insérée (ou la seule si on
    adopte un schéma upsert — voir modèle InverterConfig).
    """
    logger.info("POST /config reçu: %s", data.dict())
    try:
        if x_api_key != API_KEY:
            logger.warning("Clé API invalide pour /config: %s", x_api_key)
            raise HTTPException(status_code=401, detail="Clé API invalide")

        # Upsert : on écrase la ligne unique de config (id=1)
        cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()
        if cfg is None:
            cfg = InverterConfig(id=1)
            db.add(cfg)

        cfg.priority_s1    = data.priorities[0]
        cfg.priority_s2    = data.priorities[1]
        cfg.priority_s3    = data.priorities[2]
        cfg.name_s1        = data.source_names["S1"]
        cfg.name_s2        = data.source_names["S2"]
        cfg.name_s3        = data.source_names["S3"]
        cfg.config_version = (cfg.config_version or 1) + 1
        cfg.updated_by     = "web"

        db.commit()
        db.refresh(cfg)
        logger.info("Config enregistrée: priorités=%s, noms=%s, version=%d",
                    data.priorities, data.source_names, cfg.config_version)
        return {
            "status": "ok",
            "priorities": data.priorities,
            "source_names": data.source_names,
            "config_version": cfg.config_version,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur lors de l'enregistrement de la config: %s", e)
        raise


# ─── GET /api/inverter/config — lit la config active ─────────────────────────
@router.get("/config")
async def get_config(
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Retourne la configuration courante (priorités + noms) pour pré-remplir
    la page settings.html au chargement.
    """
    logger.info("GET /config reçu")
    if x_api_key != API_KEY:
        logger.warning("Clé API invalide pour GET /config: %s", x_api_key)
        raise HTTPException(status_code=401, detail="Clé API invalide")
    cfg = db.query(InverterConfig).filter(InverterConfig.id == 1).first()
    if cfg is None:
        # Valeurs par défaut si jamais rien n'a encore été sauvegardé
        return {
            "priorities": [1, 2, 3],
            "source_names": {"S1": "Source 1", "S2": "Source 2", "S3": "Source 3"},
            "config_version": 1,
            "updated_by": "web",
            "updated_at": None,
        }
    return {
        "priorities": [cfg.priority_s1, cfg.priority_s2, cfg.priority_s3],
        "source_names": {"S1": cfg.name_s1, "S2": cfg.name_s2, "S3": cfg.name_s3},
        "config_version": cfg.config_version,
        "updated_by": cfg.updated_by,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }