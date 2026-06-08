from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, Float, BigInteger
from sqlalchemy.sql import func
from database import Base
import enum
from sqlalchemy.sql import func



class RoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True, index=True)
    username    = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email       = Column(String(100), unique=True, nullable=True)
    full_name   = Column(String(100), nullable=True)
    role        = Column(Enum(RoleEnum), default=RoleEnum.user, nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, nullable=False)
    title       = Column(String(200), nullable=False)
    message     = Column(Text, nullable=False)
    alert_type  = Column(String(50), default="info")  # info, warning, danger, success
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class History(Base):
    __tablename__ = "history"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, nullable=False)
    action      = Column(String(200), nullable=False)
    details     = Column(Text, nullable=True)
    ip_address  = Column(String(50), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class VoltageReading(Base):
    """
    Enregistrement envoyé par l'ESP32 toutes les SEND_INTERVAL_MS.

    Champs JSON reçus :
        U1, U2, U3          — tensions (V) des 3 sources (string → float)
        S1, S2, S3          — état OK de chaque source (bool)
        sourceActive        — numéro de la source utilisée (1, 2 ou 3)
        P1, P2, P3          — priorités attribuées à S1, S2, S3
        TA, TB              — temporisations (ms)
        uptime              — durée de fonctionnement ESP32 (s)
    """
    __tablename__ = "voltage_readings"

    id            = Column(Integer,     primary_key=True, index=True)

    # ── Tensions ──────────────────────────────────────────────────────────
    voltage_s1    = Column(Float,   nullable=True)   # U1 — ex : Réseau EDL
    voltage_s2    = Column(Float,   nullable=True)   # U2 — ex : Groupe électrogène
    voltage_s3    = Column(Float,   nullable=True)   # U3 — ex : Solaire / Batterie

    # ── États sources ─────────────────────────────────────────────────────
    source_s1_ok  = Column(Boolean, nullable=True)   # S1
    source_s2_ok  = Column(Boolean, nullable=True)   # S2
    source_s3_ok  = Column(Boolean, nullable=True)   # S3

    # ── Source active ─────────────────────────────────────────────────────
    active_source = Column(Integer, nullable=True)   # sourceActive (1, 2 ou 3)

    # ── Priorités ─────────────────────────────────────────────────────────
    priority_s1   = Column(Integer, nullable=True)   # P1
    priority_s2   = Column(Integer, nullable=True)   # P2
    priority_s3   = Column(Integer, nullable=True)   # P3

    # ── Temporisations ────────────────────────────────────────────────────
    delay_ta      = Column(BigInteger, nullable=True)  # TA (ms)
    delay_tb      = Column(BigInteger, nullable=True)  # TB (ms)

    # ── Uptime ESP32 ──────────────────────────────────────────────────────
    uptime        = Column(BigInteger, nullable=True)  # secondes

    # ── Fréquences (optionnel, non envoyé par l'ESP32 pour l'instant) ─────
    frequency_s1  = Column(Float,   nullable=True)
    frequency_s2  = Column(Float,   nullable=True)
    frequency_s3  = Column(Float,   nullable=True)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())




class InverterConfig(Base):
    __tablename__ = "inverter_config"

    id          = Column(Integer, primary_key=True, default=1)

    # Rang de chaque source (1 = prioritaire, 3 = dernier recours)
    priority_s1 = Column(Integer, nullable=False, default=1)
    priority_s2 = Column(Integer, nullable=False, default=2)
    priority_s3 = Column(Integer, nullable=False, default=3)

    # Noms affichés sur le LCD et les tableaux de bord
    name_s1     = Column(String(30), nullable=False, default="Source 1")
    name_s2     = Column(String(30), nullable=False, default="Source 2")
    name_s3     = Column(String(30), nullable=False, default="Source 3")

    # ── Synchronisation ESP32 ──────────────────────────────────────────────
    # Incrémenté à chaque modification (web ou ESP32).
    # L'ESP32 compare sa version locale à celle-ci pour détecter un changement.
    config_version = Column(Integer, nullable=False, default=1)

    # Origine de la dernière modification : "web" | "esp32"
    updated_by  = Column(String(10), nullable=False, default="web")

    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())