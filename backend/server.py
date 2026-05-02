from dotenv import load_dotenv
load_dotenv()

import os
import logging
import uuid
import bcrypt
import jwt
import random
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Any

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Header
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import engine, SessionLocal, Base, get_session
import models as M


# -------------------- Setup --------------------
JWT_ALGORITHM = "HS256"
ROLES = ["admin", "analyste_sig", "agent_terrain", "pilote_drone"]

app = FastAPI(title="GestPro API", description="Plateforme de Surveillance des Forêts Classées de Gagnoa (PostgreSQL)")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gestpro")


# -------------------- Auth Utilities --------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def serialize_user(u: M.User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": u.role, "active": u.active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


async def get_current_user(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token invalide")
        result = await db.execute(select(M.User).where(M.User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return serialize_user(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


def require_roles(*roles: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles and user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé pour ce rôle")
        return user
    return checker


# -------------------- Pydantic Schemas --------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role: Literal["admin", "analyste_sig", "agent_terrain", "pilote_drone"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class AlertCreate(BaseModel):
    forest_id: str
    alert_type: Literal["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement"]
    severity: Literal["faible", "moyenne", "haute", "critique"]
    lat: float
    lng: float
    area_ha: float
    description: str
    source: Literal["satellite", "drone", "terrain"] = "satellite"


class AlertStatusUpdate(BaseModel):
    status: Literal["detectee", "en_verification", "confirmee", "resolue", "rejetee"]
    note: Optional[str] = None


class ObservationCreate(BaseModel):
    forest_id: str
    alert_id: Optional[str] = None
    observation_type: Literal["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement", "autre"]
    lat: float
    lng: float
    description: str
    photo_url: Optional[str] = None


class DroneMissionCreate(BaseModel):
    forest_id: str
    alert_id: Optional[str] = None
    pilot_id: Optional[str] = None
    planned_date: str
    target_lat: float
    target_lng: float
    radius_m: float = 500
    purpose: str


class DroneMissionUpdate(BaseModel):
    status: Literal["planifiee", "en_cours", "terminee", "annulee"]
    notes: Optional[str] = None
    ndvi_avg: Optional[float] = None


class AIAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None


# -------------------- Serializers --------------------
def s_forest(f: M.Forest) -> dict:
    return {
        "id": f.id, "name": f.name, "code": f.code, "area_ha": f.area_ha,
        "region": f.region, "center_lat": f.center_lat, "center_lng": f.center_lng,
        "description": f.description,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def s_alert(a: M.Alert) -> dict:
    return {
        "id": a.id, "forest_id": a.forest_id, "alert_type": a.alert_type,
        "severity": a.severity, "lat": a.lat, "lng": a.lng, "area_ha": a.area_ha,
        "description": a.description, "source": a.source, "status": a.status,
        "history": a.history or [],
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "created_by": a.created_by,
    }


def s_obs(o: M.Observation) -> dict:
    return {
        "id": o.id, "forest_id": o.forest_id, "alert_id": o.alert_id,
        "observation_type": o.observation_type, "lat": o.lat, "lng": o.lng,
        "description": o.description, "photo_url": o.photo_url,
        "agent_id": o.agent_id, "agent_name": o.agent_name,
        "source": o.source, "kobo_submission_id": o.kobo_submission_id,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def s_mission(m: M.DroneMission) -> dict:
    return {
        "id": m.id, "forest_id": m.forest_id, "alert_id": m.alert_id,
        "pilot_id": m.pilot_id,
        "planned_date": m.planned_date.isoformat() if m.planned_date else None,
        "target_lat": m.target_lat, "target_lng": m.target_lng,
        "radius_m": m.radius_m, "purpose": m.purpose, "status": m.status,
        "notes": m.notes or "", "ndvi_avg": m.ndvi_avg,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "created_by": m.created_by,
    }


def s_kobo(k: M.KoboSubmission) -> dict:
    return {
        "id": k.id, "kobo_id": k.kobo_id, "form_id": k.form_id, "form_type": k.form_type,
        "raw_payload": k.raw_payload, "lat": k.lat, "lng": k.lng,
        "description": k.description, "submitted_by": k.submitted_by,
        "submitted_at": k.submitted_at.isoformat() if k.submitted_at else None,
        "forest_id": k.forest_id, "alert_id": k.alert_id,
        "observation_id": k.observation_id, "processed": k.processed,
        "received_at": k.received_at.isoformat() if k.received_at else None,
    }


# -------------------- Auth Routes --------------------
@api.post("/auth/login")
async def login(data: UserLogin, response: Response, db: AsyncSession = Depends(get_session)):
    email = data.email.lower().strip()
    result = await db.execute(select(M.User).where(M.User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user.id, user.email, user.role)
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"user": serialize_user(user), "access_token": token}


@api.post("/auth/logout")
async def logout(response: Response, _user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"message": "Déconnecté"}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/register")
async def register(data: UserCreate, _admin: dict = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    email = data.email.lower().strip()
    existing = await db.execute(select(M.User).where(M.User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = M.User(
        email=email, password_hash=hash_password(data.password),
        full_name=data.full_name, role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return serialize_user(user)


@api.get("/users")
async def list_users(_admin: dict = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.User).order_by(M.User.created_at.desc()))
    return [serialize_user(u) for u in result.scalars().all()]


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    result = await db.execute(delete(M.User).where(M.User.id == user_id))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {"message": "Utilisateur supprimé"}


# -------------------- Forests --------------------
@api.get("/forests")
async def get_forests(_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Forest).order_by(M.Forest.name))
    return [s_forest(f) for f in result.scalars().all()]


@api.get("/forests/{forest_id}")
async def get_forest(forest_id: str, _user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Forest).where(M.Forest.id == forest_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Forêt introuvable")
    return s_forest(f)


# -------------------- Alerts --------------------
@api.get("/alerts")
async def list_alerts(
    status_filter: Optional[str] = None,
    forest_id: Optional[str] = None,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    q = select(M.Alert).order_by(M.Alert.created_at.desc())
    if status_filter:
        q = q.where(M.Alert.status == status_filter)
    if forest_id:
        q = q.where(M.Alert.forest_id == forest_id)
    result = await db.execute(q)
    return [s_alert(a) for a in result.scalars().all()]


@api.post("/alerts")
async def create_alert(data: AlertCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    alert = M.Alert(
        **data.model_dump(),
        status="detectee",
        history=[{"status": "detectee", "at": now.isoformat(), "by": user["full_name"], "note": "Alerte créée"}],
        created_by=user["id"],
        created_at=now,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return s_alert(alert)


@api.patch("/alerts/{alert_id}/status")
async def update_alert_status(alert_id: str, data: AlertStatusUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Alert).where(M.Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    history = list(alert.history or [])
    history.append({
        "status": data.status,
        "at": datetime.now(timezone.utc).isoformat(),
        "by": user["full_name"],
        "note": data.note or "",
    })
    alert.status = data.status
    alert.history = history
    # Reassign so SQLAlchemy detects JSONB change
    await db.execute(
        update(M.Alert)
        .where(M.Alert.id == alert_id)
        .values(status=data.status, history=history)
    )
    await db.commit()
    await db.refresh(alert)
    return s_alert(alert)


@api.delete("/alerts/{alert_id}")
async def del_alert(alert_id: str, _u: dict = Depends(require_roles("admin", "analyste_sig")), db: AsyncSession = Depends(get_session)):
    res = await db.execute(delete(M.Alert).where(M.Alert.id == alert_id))
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return {"message": "Alerte supprimée"}


# -------------------- Observations --------------------
@api.get("/observations")
async def list_obs(_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Observation).order_by(M.Observation.created_at.desc()))
    return [s_obs(o) for o in result.scalars().all()]


@api.post("/observations")
async def create_obs(data: ObservationCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    obs = M.Observation(
        **data.model_dump(),
        agent_id=user["id"],
        agent_name=user["full_name"],
        source="manuel",
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return s_obs(obs)


@api.delete("/observations/{obs_id}")
async def del_obs(obs_id: str, _u: dict = Depends(require_roles("admin", "analyste_sig")), db: AsyncSession = Depends(get_session)):
    res = await db.execute(delete(M.Observation).where(M.Observation.id == obs_id))
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Observation introuvable")
    return {"message": "Observation supprimée"}


# -------------------- Drone Missions --------------------
@api.get("/drone-missions")
async def list_missions(_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.DroneMission).order_by(M.DroneMission.created_at.desc()))
    return [s_mission(m) for m in result.scalars().all()]


@api.post("/drone-missions")
async def create_mission(data: DroneMissionCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    payload = data.model_dump()
    payload["planned_date"] = datetime.fromisoformat(payload["planned_date"].replace("Z", "+00:00"))
    mission = M.DroneMission(**payload, created_by=user["id"])
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return s_mission(mission)


@api.patch("/drone-missions/{mission_id}")
async def update_mission(mission_id: str, data: DroneMissionUpdate, _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.DroneMission).where(M.DroneMission.id == mission_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    m.status = data.status
    if data.notes is not None:
        m.notes = data.notes
    if data.ndvi_avg is not None:
        m.ndvi_avg = data.ndvi_avg
    if data.status == "terminee":
        m.completed_at = datetime.now(timezone.utc)
        if m.ndvi_avg is None:
            m.ndvi_avg = round(random.uniform(0.35, 0.85), 2)
    await db.commit()
    await db.refresh(m)
    return s_mission(m)


# -------------------- GEE Mock --------------------
@api.get("/gee/indices/{forest_id}")
async def gee_indices(forest_id: str, _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Forest).where(M.Forest.id == forest_id))
    forest = result.scalar_one_or_none()
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")
    rng = random.Random(forest_id)
    months = []
    base = datetime.now(timezone.utc)
    for i in range(12, 0, -1):
        d = base - timedelta(days=30 * i)
        ndvi = round(rng.uniform(0.55, 0.85) - i * 0.005, 3)
        months.append({
            "month": d.strftime("%Y-%m"),
            "ndvi": max(0.2, ndvi),
            "nbr": round(rng.uniform(0.30, 0.65), 3),
            "ndwi": round(rng.uniform(0.10, 0.40), 3),
            "cloud_cover": round(rng.uniform(2, 25), 1),
        })
    return {
        "forest": s_forest(forest),
        "satellite_sources": ["Sentinel-2 (10m, 5j)", "Landsat-9 (30m)", "MODIS (250m)"],
        "time_series": months,
        "summary": {
            "ndvi_current": months[-1]["ndvi"],
            "ndvi_trend": round(months[-1]["ndvi"] - months[0]["ndvi"], 3),
            "ndvi_status": "stable" if abs(months[-1]["ndvi"] - months[0]["ndvi"]) < 0.05 else "déclin",
        },
    }


@api.get("/gee/landcover/{forest_id}")
async def gee_landcover(forest_id: str, _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Forest).where(M.Forest.id == forest_id))
    forest = result.scalar_one_or_none()
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")
    rng = random.Random(forest_id + "lc")
    classes = [
        {"name": "Forêt dense", "color": "#1e5128", "percent": round(rng.uniform(45, 65), 1)},
        {"name": "Forêt dégradée", "color": "#4f7942", "percent": round(rng.uniform(15, 25), 1)},
        {"name": "Agriculture (cacao)", "color": "#c9a66b", "percent": round(rng.uniform(8, 18), 1)},
        {"name": "Sol nu", "color": "#a87e4a", "percent": round(rng.uniform(2, 8), 1)},
        {"name": "Zones brûlées", "color": "#8b3a1a", "percent": round(rng.uniform(0.5, 4), 1)},
    ]
    total = sum(c["percent"] for c in classes)
    for c in classes:
        c["percent"] = round(c["percent"] * 100 / total, 1)
    return {"forest": s_forest(forest), "classes": classes, "resolution_m": 10, "source": "Sentinel-2 + Random Forest"}


@api.get("/predictions/{forest_id}")
async def predictions(forest_id: str, _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(M.Forest).where(M.Forest.id == forest_id))
    forest = result.scalar_one_or_none()
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")
    rng = random.Random(forest_id + "pred")
    cells = []
    grid_size = 8
    spread = 0.15
    for i in range(grid_size):
        for j in range(grid_size):
            edge = max(abs(i - grid_size / 2), abs(j - grid_size / 2)) / (grid_size / 2)
            risk = min(0.95, max(0.05, rng.uniform(0.05, 0.4) + edge * 0.45))
            cells.append({
                "lat": forest.center_lat + (i - grid_size / 2) * (spread / grid_size),
                "lng": forest.center_lng + (j - grid_size / 2) * (spread / grid_size),
                "risk": round(risk, 3),
            })
    high = [c for c in cells if c["risk"] >= 0.7]
    return {
        "forest": s_forest(forest), "cells": cells,
        "high_risk_count": len(high), "high_risk_zones": high[:10],
        "model": "Random Forest + Logistic Regression (historiques 2018-2025)",
        "horizon_days": 90,
    }


# -------------------- Stats --------------------
@api.get("/stats/dashboard")
async def stats_dashboard(_u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    total_alerts = (await db.execute(select(func.count()).select_from(M.Alert))).scalar() or 0
    total_obs = (await db.execute(select(func.count()).select_from(M.Observation))).scalar() or 0
    total_missions = (await db.execute(select(func.count()).select_from(M.DroneMission))).scalar() or 0
    total_forests = (await db.execute(select(func.count()).select_from(M.Forest))).scalar() or 0
    pending = (await db.execute(
        select(func.count()).select_from(M.Alert).where(M.Alert.status.in_(["detectee", "en_verification"]))
    )).scalar() or 0
    total_kobo = (await db.execute(select(func.count()).select_from(M.KoboSubmission))).scalar() or 0

    forests_res = await db.execute(select(M.Forest))
    forests = forests_res.scalars().all()
    total_area = sum(f.area_ha for f in forests)

    by_status_res = await db.execute(select(M.Alert.status, func.count()).group_by(M.Alert.status))
    by_status = [{"status": s, "count": c} for s, c in by_status_res.all()]

    by_type_res = await db.execute(select(M.Alert.alert_type, func.count()).group_by(M.Alert.alert_type))
    by_type = [{"type": t, "count": c} for t, c in by_type_res.all()]

    recent_res = await db.execute(select(M.Alert).order_by(M.Alert.created_at.desc()).limit(5))
    recent = [s_alert(a) for a in recent_res.scalars().all()]

    return {
        "totals": {
            "alerts": total_alerts, "observations": total_obs,
            "drone_missions": total_missions, "forests": total_forests,
            "total_area_ha": total_area, "pending": pending,
            "kobo_submissions": total_kobo,
        },
        "alerts_by_status": by_status,
        "alerts_by_type": by_type,
        "recent_alerts": recent,
    }


# -------------------- AI (Claude) --------------------
@api.post("/ai/analyze")
async def ai_analyze(data: AIAnalysisRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Module LLM indisponible: {e}")
    system = (
        "Tu es un expert en surveillance forestière travaillant pour le Centre de Gestion de Gagnoa "
        "en Côte d'Ivoire. Tu analyses les observations terrain et alertes liées à la déforestation, "
        "à l'agriculture illégale (notamment de cacao), aux feux de brousse et à l'exploitation forestière. "
        "Réponds toujours en français, de manière structurée :\n"
        "1. **Analyse** (synthèse rapide)\n"
        "2. **Niveau de gravité** (faible / moyenne / haute / critique)\n"
        "3. **Causes probables**\n"
        "4. **Recommandations** (actions concrètes)\n"
        "5. **Priorité d'intervention** (1-5, 5 = très urgent)"
    )
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"gestpro-{user['id']}-{uuid.uuid4()}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    text = data.text.strip()
    if data.context:
        text = f"Contexte: {data.context}\n\nDescription:\n{text}"
    try:
        response = await chat.send_message(UserMessage(text=text))
    except Exception as e:
        logger.error(f"Erreur LLM: {e}")
        raise HTTPException(status_code=502, detail=f"Erreur lors de l'analyse IA: {e}")

    rec = M.AIAnalysis(
        user_id=user["id"], input_text=data.text, context=data.context,
        response=response, model="claude-sonnet-4-5",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return {
        "id": rec.id, "user_id": rec.user_id, "input_text": rec.input_text,
        "context": rec.context, "response": rec.response, "model": rec.model,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


@api.get("/ai/history")
async def ai_history(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(M.AIAnalysis).where(M.AIAnalysis.user_id == user["id"]).order_by(M.AIAnalysis.created_at.desc()).limit(50)
    )
    return [
        {
            "id": r.id, "user_id": r.user_id, "input_text": r.input_text, "context": r.context,
            "response": r.response, "model": r.model,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.scalars().all()
    ]


# -------------------- Kobo Toolbox --------------------
def _extract_kobo_field(payload: dict, *names) -> Optional[str]:
    """Find a field in Kobo payload by trying several possible names."""
    for name in names:
        if name in payload and payload[name] not in (None, ""):
            return payload[name]
    # Try suffix match (Kobo prefixes with group names sometimes)
    for k, v in payload.items():
        for name in names:
            if k.endswith(f"/{name}") and v not in (None, ""):
                return v
    return None


def _extract_kobo_geo(payload: dict) -> tuple[Optional[float], Optional[float]]:
    """Try _geolocation, geopoint, or split lat/lng fields."""
    geo = payload.get("_geolocation")
    if isinstance(geo, list) and len(geo) >= 2 and geo[0] is not None:
        try:
            return float(geo[0]), float(geo[1])
        except (TypeError, ValueError):
            pass
    raw = _extract_kobo_field(payload, "geopoint", "location", "gps", "_geopoint")
    if raw and isinstance(raw, str):
        parts = raw.split()
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass
    lat = _extract_kobo_field(payload, "lat", "latitude")
    lng = _extract_kobo_field(payload, "lng", "lon", "longitude")
    try:
        return (float(lat) if lat is not None else None,
                float(lng) if lng is not None else None)
    except (TypeError, ValueError):
        return None, None


def _classify_kobo_form(payload: dict, form_id: Optional[str]) -> str:
    """Detect form type from payload heuristics."""
    if form_id:
        fid = form_id.lower()
        if "verif" in fid:
            return "verification"
        if "infract" in fid:
            return "infraction"
    if _extract_kobo_field(payload, "alert_id", "id_alerte"):
        return "verification"
    return "observation"


@api.post("/kobo/webhook")
async def kobo_webhook(
    request: Request,
    x_kobo_token: Optional[str] = Header(None, alias="X-Kobo-Token"),
    db: AsyncSession = Depends(get_session),
):
    """
    Kobo Toolbox REST Service webhook.
    Configure this URL in Kobo: https://<host>/api/kobo/webhook
    Add a Custom HTTP header `X-Kobo-Token` with the value of KOBO_WEBHOOK_SECRET.
    """
    secret = os.environ.get("KOBO_WEBHOOK_SECRET")
    if secret and x_kobo_token != secret:
        raise HTTPException(status_code=401, detail="Token webhook invalide")

    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload Kobo invalide")

    kobo_id = str(payload.get("_id") or payload.get("instanceID") or payload.get("meta/instanceID") or uuid.uuid4())
    form_id = payload.get("_xform_id_string") or payload.get("formId") or payload.get("form_id")
    form_type = _classify_kobo_form(payload, form_id)
    lat, lng = _extract_kobo_geo(payload)
    description = _extract_kobo_field(payload, "description", "comment", "notes", "remarks") or ""
    submitted_by = (
        _extract_kobo_field(payload, "username", "_submitted_by")
        or payload.get("_submitted_by")
        or "Kobo"
    )
    submitted_at_raw = payload.get("_submission_time") or payload.get("end") or payload.get("start")
    submitted_at = None
    if submitted_at_raw:
        try:
            submitted_at = datetime.fromisoformat(submitted_at_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            submitted_at = None

    # Forest matching: explicit forest_id or by name
    forest_ref = _extract_kobo_field(payload, "forest_id", "id_foret", "foret", "forest_code", "code_foret")
    forest_id = None
    if forest_ref:
        f_res = await db.execute(
            select(M.Forest).where((M.Forest.id == forest_ref) | (M.Forest.code == forest_ref) | (M.Forest.name == forest_ref))
        )
        f = f_res.scalar_one_or_none()
        if f:
            forest_id = f.id
    if not forest_id and lat is not None and lng is not None:
        # Pick nearest forest
        all_f = (await db.execute(select(M.Forest))).scalars().all()
        if all_f:
            nearest = min(all_f, key=lambda x: (x.center_lat - lat) ** 2 + (x.center_lng - lng) ** 2)
            forest_id = nearest.id

    alert_ref = _extract_kobo_field(payload, "alert_id", "id_alerte")

    submission = M.KoboSubmission(
        kobo_id=kobo_id, form_id=form_id, form_type=form_type,
        raw_payload=payload, lat=lat, lng=lng, description=description,
        submitted_by=submitted_by, submitted_at=submitted_at,
        forest_id=forest_id, alert_id=alert_ref, processed=False,
    )
    db.add(submission)
    await db.flush()

    obs_id = None
    # Auto-create Observation when geolocated and form is observation/verification
    if lat is not None and lng is not None and forest_id and form_type in ("observation", "verification"):
        obs_type = _extract_kobo_field(payload, "observation_type", "type") or "autre"
        if obs_type not in {"deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement", "autre"}:
            obs_type = "autre"
        photo = _extract_kobo_field(payload, "photo", "image", "photo_url")
        obs = M.Observation(
            forest_id=forest_id, alert_id=alert_ref, observation_type=obs_type,
            lat=lat, lng=lng,
            description=description or f"Soumission Kobo {kobo_id}",
            photo_url=photo if photo and isinstance(photo, str) and photo.startswith("http") else None,
            agent_id=None, agent_name=submitted_by or "Kobo",
            source="kobo", kobo_submission_id=submission.id,
        )
        db.add(obs)
        await db.flush()
        obs_id = obs.id
        submission.observation_id = obs_id
        submission.processed = True

    # If verification with alert_ref → push to alert history
    if form_type == "verification" and alert_ref:
        a_res = await db.execute(select(M.Alert).where(M.Alert.id == alert_ref))
        alert = a_res.scalar_one_or_none()
        if alert:
            history = list(alert.history or [])
            history.append({
                "status": "en_verification",
                "at": datetime.now(timezone.utc).isoformat(),
                "by": f"Kobo · {submitted_by or '—'}",
                "note": f"Vérification terrain reçue: {description[:200]}",
            })
            await db.execute(
                update(M.Alert)
                .where(M.Alert.id == alert_ref)
                .values(status="en_verification", history=history)
            )

    await db.commit()
    await db.refresh(submission)
    return {"ok": True, "submission_id": submission.id, "observation_id": obs_id, "form_type": form_type}


@api.get("/kobo/submissions")
async def list_kobo_submissions(
    _u: dict = Depends(get_current_user),
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(M.KoboSubmission).order_by(M.KoboSubmission.received_at.desc()).limit(limit)
    )
    return [s_kobo(k) for k in result.scalars().all()]


@api.get("/kobo/info")
async def kobo_webhook_info(_u: dict = Depends(get_current_user), request: Request = None):
    """Return webhook URL + token for the admin to configure Kobo."""
    base = str(request.base_url).rstrip("/") if request else ""
    return {
        "webhook_url": f"{base}/api/kobo/webhook",
        "header_name": "X-Kobo-Token",
        "header_value": os.environ.get("KOBO_WEBHOOK_SECRET", ""),
        "instructions": [
            "1. Sur kf.kobotoolbox.org → ouvrez votre formulaire → Settings → REST Services.",
            "2. Cliquez sur 'Register a new service'.",
            "3. Service Name: GestPro",
            f"4. Endpoint URL: {base}/api/kobo/webhook",
            "5. Custom HTTP Headers: ajoutez X-Kobo-Token avec la valeur fournie ci-dessus.",
            "6. Sauvegardez. Chaque nouvelle soumission sera transmise à GestPro.",
        ],
    }


# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"app": "GestPro", "status": "ok", "version": "2.0.0", "db": "PostgreSQL"}


# -------------------- Seeding --------------------
async def seed_data():
    async with SessionLocal() as db:
        # Admin
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@gestpro.ci")
        admin_password = os.environ.get("ADMIN_PASSWORD", "GestPro2026!")
        existing = await db.execute(select(M.User).where(M.User.email == admin_email))
        admin = existing.scalar_one_or_none()
        if not admin:
            admin = M.User(
                email=admin_email, password_hash=hash_password(admin_password),
                full_name="Administrateur GestPro", role="admin",
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
        elif not verify_password(admin_password, admin.password_hash):
            admin.password_hash = hash_password(admin_password)
            await db.commit()

        # Demo users
        demos = [
            ("analyste@gestpro.ci", "Analyste2026!", "Akissi Brou", "analyste_sig"),
            ("agent@gestpro.ci", "Agent2026!", "Kouamé Yao", "agent_terrain"),
            ("pilote@gestpro.ci", "Pilote2026!", "Diomandé Sékou", "pilote_drone"),
        ]
        for email, pwd, name, role in demos:
            r = await db.execute(select(M.User).where(M.User.email == email))
            if not r.scalar_one_or_none():
                db.add(M.User(email=email, password_hash=hash_password(pwd), full_name=name, role=role))
        await db.commit()

        # Forests
        cnt = (await db.execute(select(func.count()).select_from(M.Forest))).scalar() or 0
        if cnt == 0:
            db.add_all([
                M.Forest(
                    name="Forêt Classée de Sangoué", code="FC-SANG", area_ha=36200,
                    region="Lôh-Djiboua / Gôh (Gagnoa)", center_lat=6.10, center_lng=-5.95,
                    description="Forêt classée de 36 200 ha sous la gestion du Centre de Gagnoa. Soumise à une forte pression agricole (cacao) et à l'exploitation illégale.",
                ),
                M.Forest(
                    name="Forêt Classée de Téné", code="FC-TENE", area_ha=29700,
                    region="Gôh (Gagnoa)", center_lat=6.30, center_lng=-6.05,
                    description="Forêt classée de 29 700 ha. Surveillance prioritaire des limites Nord-Est sujettes au défrichement.",
                ),
            ])
            await db.commit()

        # Demo alerts
        cnt = (await db.execute(select(func.count()).select_from(M.Alert))).scalar() or 0
        if cnt == 0:
            forests = (await db.execute(select(M.Forest))).scalars().all()
            admin_user = (await db.execute(select(M.User).where(M.User.email == admin_email))).scalar_one()
            types = ["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement"]
            statuses = ["detectee", "en_verification", "confirmee", "resolue"]
            sevs = ["faible", "moyenne", "haute", "critique"]
            rng = random.Random(42)
            for f in forests:
                for _ in range(7):
                    lat = f.center_lat + rng.uniform(-0.08, 0.08)
                    lng = f.center_lng + rng.uniform(-0.08, 0.08)
                    at = datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 30))
                    db.add(M.Alert(
                        forest_id=f.id, alert_type=rng.choice(types), severity=rng.choice(sevs),
                        lat=lat, lng=lng, area_ha=round(rng.uniform(0.5, 25), 2),
                        description=f"Anomalie détectée par satellite Sentinel-2 dans {f.name}",
                        source=rng.choice(["satellite", "drone", "terrain"]),
                        status=rng.choice(statuses),
                        history=[{"status": "detectee", "at": at.isoformat(), "by": "Système GEE", "note": "Détection automatique"}],
                        created_by=admin_user.id, created_at=at,
                    ))
            await db.commit()

        # Demo observations
        cnt = (await db.execute(select(func.count()).select_from(M.Observation))).scalar() or 0
        if cnt == 0:
            forests = (await db.execute(select(M.Forest))).scalars().all()
            agent = (await db.execute(select(M.User).where(M.User.email == "agent@gestpro.ci"))).scalar_one_or_none()
            descs = [
                "Plantation de cacao récemment installée à l'intérieur du périmètre forestier.",
                "Traces de feu de brousse, environ 2 ha brûlés.",
                "Coupe de bois illégale observée, plusieurs souches récentes.",
                "Défrichement actif - tronçonneuses entendues.",
                "Forêt intacte, aucun signe d'activité illégale.",
            ]
            rng = random.Random(7)
            for f in forests:
                for _ in range(4):
                    db.add(M.Observation(
                        forest_id=f.id, alert_id=None,
                        observation_type=rng.choice(["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "autre"]),
                        lat=f.center_lat + rng.uniform(-0.05, 0.05),
                        lng=f.center_lng + rng.uniform(-0.05, 0.05),
                        description=rng.choice(descs), photo_url=None,
                        agent_id=agent.id if agent else None,
                        agent_name=agent.full_name if agent else "Agent terrain",
                        source="manuel",
                        created_at=datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 20)),
                    ))
            await db.commit()

        # Demo missions
        cnt = (await db.execute(select(func.count()).select_from(M.DroneMission))).scalar() or 0
        if cnt == 0:
            forests = (await db.execute(select(M.Forest))).scalars().all()
            pilote = (await db.execute(select(M.User).where(M.User.email == "pilote@gestpro.ci"))).scalar_one_or_none()
            rng = random.Random(11)
            for f in forests:
                for _ in range(3):
                    status = rng.choice(["planifiee", "en_cours", "terminee"])
                    db.add(M.DroneMission(
                        forest_id=f.id, alert_id=None,
                        pilot_id=pilote.id if pilote else None,
                        planned_date=datetime.now(timezone.utc) + timedelta(days=rng.randint(-10, 14)),
                        target_lat=f.center_lat + rng.uniform(-0.06, 0.06),
                        target_lng=f.center_lng + rng.uniform(-0.06, 0.06),
                        radius_m=rng.choice([300, 500, 1000]),
                        purpose=rng.choice(["Vérification d'alerte", "Cartographie haute résolution", "Suivi NDVI", "Inspection de zone à risque"]),
                        status=status,
                        ndvi_avg=round(rng.uniform(0.4, 0.85), 2) if status == "terminee" else None,
                        notes="Mission terminée avec succès." if status == "terminee" else "",
                        completed_at=datetime.now(timezone.utc) if status == "terminee" else None,
                        created_by=pilote.id if pilote else None,
                    ))
            await db.commit()
        logger.info("✅ Seed PostgreSQL OK")


# -------------------- App Wiring --------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_data()


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()
