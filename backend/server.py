from dotenv import load_dotenv
load_dotenv()

import os
import logging
import uuid
import bcrypt
import jwt
import secrets
import random
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, status
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# -------------------- Setup --------------------
ROOT_DIR = Path(__file__).parent
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"
ROLES = ["admin", "analyste_sig", "agent_terrain", "pilote_drone"]

app = FastAPI(title="GestPro API", description="Plateforme de Surveillance des Forêts Classées de Gagnoa")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gestpro")


# -------------------- Auth Utilities --------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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


async def get_current_user(request: Request) -> dict:
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
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return user
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


# -------------------- Models --------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role: Literal["admin", "analyste_sig", "agent_terrain", "pilote_drone"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    role: str
    created_at: str


class Forest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str
    area_ha: float
    region: str
    center_lat: float
    center_lng: float
    description: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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


# -------------------- Auth Routes --------------------
@api.post("/auth/login")
async def login(data: UserLogin, response: Response):
    email = data.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    user_out = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    return {"user": user_out, "access_token": token}


@api.post("/auth/logout")
async def logout(response: Response, _user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"message": "Déconnecté"}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/register")
async def register(data: UserCreate, _admin: dict = Depends(require_roles("admin"))):
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user_doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "role": data.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    await db.users.insert_one(user_doc)
    return {k: v for k, v in user_doc.items() if k not in ("_id", "password_hash")}


@api.get("/users")
async def list_users(_admin: dict = Depends(require_roles("admin"))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_roles("admin"))):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {"message": "Utilisateur supprimé"}


# -------------------- Forests --------------------
@api.get("/forests")
async def get_forests(_user: dict = Depends(get_current_user)):
    forests = await db.forests.find({}, {"_id": 0}).to_list(100)
    return forests


@api.get("/forests/{forest_id}")
async def get_forest(forest_id: str, _user: dict = Depends(get_current_user)):
    forest = await db.forests.find_one({"id": forest_id}, {"_id": 0})
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")
    return forest


# -------------------- Alerts --------------------
@api.get("/alerts")
async def list_alerts(
    status_filter: Optional[str] = None,
    forest_id: Optional[str] = None,
    _user: dict = Depends(get_current_user),
):
    query = {}
    if status_filter:
        query["status"] = status_filter
    if forest_id:
        query["forest_id"] = forest_id
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return alerts


@api.post("/alerts")
async def create_alert(data: AlertCreate, user: dict = Depends(get_current_user)):
    alert = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "status": "detectee",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"],
        "history": [{
            "status": "detectee",
            "at": datetime.now(timezone.utc).isoformat(),
            "by": user["full_name"],
            "note": "Alerte créée",
        }],
    }
    await db.alerts.insert_one(alert)
    return {k: v for k, v in alert.items() if k != "_id"}


@api.patch("/alerts/{alert_id}/status")
async def update_alert_status(alert_id: str, data: AlertStatusUpdate, user: dict = Depends(get_current_user)):
    alert = await db.alerts.find_one({"id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    history_entry = {
        "status": data.status,
        "at": datetime.now(timezone.utc).isoformat(),
        "by": user["full_name"],
        "note": data.note or "",
    }
    await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {"status": data.status}, "$push": {"history": history_entry}},
    )
    updated = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    return updated


@api.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, _admin: dict = Depends(require_roles("admin", "analyste_sig"))):
    res = await db.alerts.delete_one({"id": alert_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return {"message": "Alerte supprimée"}


# -------------------- Observations --------------------
@api.get("/observations")
async def list_observations(_user: dict = Depends(get_current_user)):
    obs = await db.observations.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return obs


@api.post("/observations")
async def create_observation(data: ObservationCreate, user: dict = Depends(get_current_user)):
    obs = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "agent_id": user["id"],
        "agent_name": user["full_name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.observations.insert_one(obs)
    return {k: v for k, v in obs.items() if k != "_id"}


@api.delete("/observations/{obs_id}")
async def delete_observation(obs_id: str, _user: dict = Depends(require_roles("admin", "analyste_sig"))):
    res = await db.observations.delete_one({"id": obs_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Observation introuvable")
    return {"message": "Observation supprimée"}


# -------------------- Drone Missions --------------------
@api.get("/drone-missions")
async def list_missions(_user: dict = Depends(get_current_user)):
    missions = await db.drone_missions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return missions


@api.post("/drone-missions")
async def create_mission(data: DroneMissionCreate, user: dict = Depends(get_current_user)):
    mission = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "status": "planifiee",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"],
        "ndvi_avg": None,
        "notes": "",
    }
    await db.drone_missions.insert_one(mission)
    return {k: v for k, v in mission.items() if k != "_id"}


@api.patch("/drone-missions/{mission_id}")
async def update_mission(mission_id: str, data: DroneMissionUpdate, _user: dict = Depends(get_current_user)):
    update_doc = {"status": data.status}
    if data.notes is not None:
        update_doc["notes"] = data.notes
    if data.ndvi_avg is not None:
        update_doc["ndvi_avg"] = data.ndvi_avg
    if data.status == "terminee":
        update_doc["completed_at"] = datetime.now(timezone.utc).isoformat()
        if data.ndvi_avg is None:
            update_doc["ndvi_avg"] = round(random.uniform(0.35, 0.85), 2)
    res = await db.drone_missions.update_one({"id": mission_id}, {"$set": update_doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return await db.drone_missions.find_one({"id": mission_id}, {"_id": 0})


# -------------------- GEE Mock Indices --------------------
@api.get("/gee/indices/{forest_id}")
async def gee_indices(forest_id: str, _user: dict = Depends(get_current_user)):
    """Mocked GEE indices (NDVI, NBR, NDWI) - simulates Sentinel-2 / Landsat / MODIS analysis."""
    forest = await db.forests.find_one({"id": forest_id}, {"_id": 0})
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")

    # Generate a 12-month time series (mocked)
    rng = random.Random(forest_id)
    months = []
    base = datetime.now(timezone.utc)
    for i in range(12, 0, -1):
        d = base - timedelta(days=30 * i)
        ndvi = round(rng.uniform(0.55, 0.85) - i * 0.005, 3)
        nbr = round(rng.uniform(0.30, 0.65), 3)
        ndwi = round(rng.uniform(0.10, 0.40), 3)
        months.append({
            "month": d.strftime("%Y-%m"),
            "ndvi": max(0.2, ndvi),
            "nbr": nbr,
            "ndwi": ndwi,
            "cloud_cover": round(rng.uniform(2, 25), 1),
        })

    return {
        "forest": forest,
        "satellite_sources": ["Sentinel-2 (10m, 5j)", "Landsat-9 (30m)", "MODIS (250m)"],
        "time_series": months,
        "summary": {
            "ndvi_current": months[-1]["ndvi"],
            "ndvi_trend": round(months[-1]["ndvi"] - months[0]["ndvi"], 3),
            "ndvi_status": "stable" if abs(months[-1]["ndvi"] - months[0]["ndvi"]) < 0.05 else "déclin",
        },
    }


@api.get("/gee/landcover/{forest_id}")
async def gee_landcover(forest_id: str, _user: dict = Depends(get_current_user)):
    """Mocked land cover classification."""
    forest = await db.forests.find_one({"id": forest_id}, {"_id": 0})
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
    return {"forest": forest, "classes": classes, "resolution_m": 10, "source": "Sentinel-2 + Random Forest"}


# -------------------- Deforestation Predictions --------------------
@api.get("/predictions/{forest_id}")
async def predictions(forest_id: str, _user: dict = Depends(get_current_user)):
    """Mocked deforestation risk grid."""
    forest = await db.forests.find_one({"id": forest_id}, {"_id": 0})
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt introuvable")

    rng = random.Random(forest_id + "pred")
    cells = []
    grid_size = 8
    spread = 0.15
    for i in range(grid_size):
        for j in range(grid_size):
            # Skewed risk - higher on edges (proxy for road/agriculture pressure)
            edge_factor = max(abs(i - grid_size / 2), abs(j - grid_size / 2)) / (grid_size / 2)
            risk = min(0.95, max(0.05, rng.uniform(0.05, 0.4) + edge_factor * 0.45))
            cells.append({
                "lat": forest["center_lat"] + (i - grid_size / 2) * (spread / grid_size),
                "lng": forest["center_lng"] + (j - grid_size / 2) * (spread / grid_size),
                "risk": round(risk, 3),
            })
    high = [c for c in cells if c["risk"] >= 0.7]
    return {
        "forest": forest,
        "cells": cells,
        "high_risk_count": len(high),
        "high_risk_zones": high[:10],
        "model": "Random Forest + Logistic Regression (historiques 2018-2025)",
        "horizon_days": 90,
    }


# -------------------- Stats --------------------
@api.get("/stats/dashboard")
async def stats_dashboard(_user: dict = Depends(get_current_user)):
    pipeline_status = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    pipeline_type = [{"$group": {"_id": "$alert_type", "count": {"$sum": 1}}}]

    alert_status = await db.alerts.aggregate(pipeline_status).to_list(20)
    alert_type = await db.alerts.aggregate(pipeline_type).to_list(20)

    total_alerts = await db.alerts.count_documents({})
    total_observations = await db.observations.count_documents({})
    total_missions = await db.drone_missions.count_documents({})
    total_forests = await db.forests.count_documents({})
    pending_verifications = await db.alerts.count_documents({"status": {"$in": ["detectee", "en_verification"]}})

    forests = await db.forests.find({}, {"_id": 0}).to_list(50)
    total_area = sum(f.get("area_ha", 0) for f in forests)

    # Recent activity
    recent_alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)

    return {
        "totals": {
            "alerts": total_alerts,
            "observations": total_observations,
            "drone_missions": total_missions,
            "forests": total_forests,
            "total_area_ha": total_area,
            "pending": pending_verifications,
        },
        "alerts_by_status": [{"status": x["_id"], "count": x["count"]} for x in alert_status],
        "alerts_by_type": [{"type": x["_id"], "count": x["count"]} for x in alert_type],
        "recent_alerts": recent_alerts,
    }


# -------------------- AI Analysis (Claude) --------------------
@api.post("/ai/analyze")
async def ai_analyze(data: AIAnalysisRequest, user: dict = Depends(get_current_user)):
    """Use Claude Sonnet 4.5 to analyze field observations / alert descriptions."""
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
    session_id = f"gestpro-{user['id']}-{uuid.uuid4()}"
    api_key = os.environ["EMERGENT_LLM_KEY"]

    chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system).with_model(
        "anthropic", "claude-sonnet-4-5-20250929"
    )

    text = data.text.strip()
    if data.context:
        text = f"Contexte: {data.context}\n\nDescription de l'observation:\n{text}"

    try:
        response = await chat.send_message(UserMessage(text=text))
    except Exception as e:
        logger.error(f"Erreur LLM: {e}")
        raise HTTPException(status_code=502, detail=f"Erreur lors de l'analyse IA: {e}")

    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "input_text": data.text,
        "context": data.context,
        "response": response,
        "model": "claude-sonnet-4-5",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_analyses.insert_one(record)
    return {k: v for k, v in record.items() if k != "_id"}


@api.get("/ai/history")
async def ai_history(user: dict = Depends(get_current_user)):
    history = await db.ai_analyses.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    return history


# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"app": "GestPro", "status": "ok", "version": "1.0.0"}


# -------------------- Seeding --------------------
async def seed_data():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.alerts.create_index("forest_id")
    await db.alerts.create_index("status")
    await db.observations.create_index("forest_id")
    await db.drone_missions.create_index("forest_id")

    # Admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@gestpro.ci")
    admin_password = os.environ.get("ADMIN_PASSWORD", "GestPro2026!")
    existing_admin = await db.users.find_one({"email": admin_email})
    if not existing_admin:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "full_name": "Administrateur GestPro",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        })
    elif not verify_password(admin_password, existing_admin["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )

    # Demo users (one per role)
    demo_users = [
        ("analyste@gestpro.ci", "Analyste2026!", "Akissi Brou", "analyste_sig"),
        ("agent@gestpro.ci", "Agent2026!", "Kouamé Yao", "agent_terrain"),
        ("pilote@gestpro.ci", "Pilote2026!", "Diomandé Sékou", "pilote_drone"),
    ]
    for email, pwd, name, role in demo_users:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "password_hash": hash_password(pwd),
                "full_name": name,
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "active": True,
            })

    # Forests
    if await db.forests.count_documents({}) == 0:
        forests = [
            {
                "id": str(uuid.uuid4()),
                "name": "Forêt Classée de Sangoué",
                "code": "FC-SANG",
                "area_ha": 36200,
                "region": "Lôh-Djiboua / Gôh (Gagnoa)",
                "center_lat": 6.10,
                "center_lng": -5.95,
                "description": "Forêt classée de 36 200 ha sous la gestion du Centre de Gagnoa. Soumise à une forte pression agricole (cacao) et à l'exploitation illégale.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Forêt Classée de Téné",
                "code": "FC-TENE",
                "area_ha": 29700,
                "region": "Gôh (Gagnoa)",
                "center_lat": 6.30,
                "center_lng": -6.05,
                "description": "Forêt classée de 29 700 ha. Surveillance prioritaire des limites Nord-Est sujettes au défrichement.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        await db.forests.insert_many(forests)

    # Demo alerts
    if await db.alerts.count_documents({}) == 0:
        forests = await db.forests.find({}, {"_id": 0}).to_list(10)
        admin = await db.users.find_one({"email": admin_email}, {"_id": 0})
        alert_types = ["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement"]
        statuses = ["detectee", "en_verification", "confirmee", "resolue"]
        severities = ["faible", "moyenne", "haute", "critique"]
        rng = random.Random(42)
        sample_alerts = []
        for f in forests:
            for i in range(7):
                lat = f["center_lat"] + rng.uniform(-0.08, 0.08)
                lng = f["center_lng"] + rng.uniform(-0.08, 0.08)
                at = (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 30))).isoformat()
                a_type = rng.choice(alert_types)
                a_status = rng.choice(statuses)
                sample_alerts.append({
                    "id": str(uuid.uuid4()),
                    "forest_id": f["id"],
                    "alert_type": a_type,
                    "severity": rng.choice(severities),
                    "lat": lat,
                    "lng": lng,
                    "area_ha": round(rng.uniform(0.5, 25), 2),
                    "description": f"Anomalie détectée par satellite Sentinel-2 dans {f['name']}",
                    "source": rng.choice(["satellite", "drone", "terrain"]),
                    "status": a_status,
                    "created_at": at,
                    "created_by": admin["id"],
                    "history": [{"status": "detectee", "at": at, "by": "Système GEE", "note": "Détection automatique"}],
                })
        await db.alerts.insert_many(sample_alerts)

    # Demo observations
    if await db.observations.count_documents({}) == 0:
        forests = await db.forests.find({}, {"_id": 0}).to_list(10)
        agent = await db.users.find_one({"email": "agent@gestpro.ci"}, {"_id": 0})
        rng = random.Random(7)
        obs_list = []
        descriptions = [
            "Plantation de cacao récemment installée à l'intérieur du périmètre forestier.",
            "Traces de feu de brousse, environ 2 ha brûlés.",
            "Coupe de bois illégale observée, plusieurs souches récentes.",
            "Défrichement actif - tronçonneuses entendues.",
            "Forêt intacte, aucun signe d'activité illégale.",
        ]
        for f in forests:
            for i in range(4):
                obs_list.append({
                    "id": str(uuid.uuid4()),
                    "forest_id": f["id"],
                    "alert_id": None,
                    "observation_type": rng.choice(["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "autre"]),
                    "lat": f["center_lat"] + rng.uniform(-0.05, 0.05),
                    "lng": f["center_lng"] + rng.uniform(-0.05, 0.05),
                    "description": rng.choice(descriptions),
                    "photo_url": None,
                    "agent_id": agent["id"] if agent else None,
                    "agent_name": agent["full_name"] if agent else "Agent terrain",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 20))).isoformat(),
                })
        await db.observations.insert_many(obs_list)

    # Demo drone missions
    if await db.drone_missions.count_documents({}) == 0:
        forests = await db.forests.find({}, {"_id": 0}).to_list(10)
        pilote = await db.users.find_one({"email": "pilote@gestpro.ci"}, {"_id": 0})
        rng = random.Random(11)
        missions = []
        for f in forests:
            for i in range(3):
                status_m = rng.choice(["planifiee", "en_cours", "terminee"])
                m = {
                    "id": str(uuid.uuid4()),
                    "forest_id": f["id"],
                    "alert_id": None,
                    "pilot_id": pilote["id"] if pilote else None,
                    "planned_date": (datetime.now(timezone.utc) + timedelta(days=rng.randint(-10, 14))).isoformat(),
                    "target_lat": f["center_lat"] + rng.uniform(-0.06, 0.06),
                    "target_lng": f["center_lng"] + rng.uniform(-0.06, 0.06),
                    "radius_m": rng.choice([300, 500, 1000]),
                    "purpose": rng.choice(["Vérification d'alerte", "Cartographie haute résolution", "Suivi NDVI", "Inspection de zone à risque"]),
                    "status": status_m,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": pilote["id"] if pilote else None,
                    "ndvi_avg": round(rng.uniform(0.4, 0.85), 2) if status_m == "terminee" else None,
                    "notes": "Mission terminée avec succès." if status_m == "terminee" else "",
                }
                missions.append(m)
        await db.drone_missions.insert_many(missions)

    logger.info("✅ Seeding terminé")


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
    await seed_data()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
