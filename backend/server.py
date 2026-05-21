"""
GestPro — Backend FastAPI (architecture GESTREB)
Lancement : uvicorn server:app --host 0.0.0.0 --port 8001 --reload
"""
import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from database import get_pool, close_pool
from routes.auth         import router as auth_router
from routes.pages        import router as pages_router
from routes.alerts       import router as alerts_router
from routes.observations import router as observations_router
from routes.drones       import router as drones_router
from routes.gee          import router as gee_router
from routes.predictions  import router as predictions_router
from routes.ai           import router as ai_router
from routes.kobo         import router as kobo_router
from routes.users        import router as users_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s — %(message)s")
logger = logging.getLogger("gestpro")


# --------------------------------------------------------------------------- #
# Lifespan : pool DB + init schéma + seed
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Init pool PostgreSQL…")
    pool = await get_pool()
    async with pool.acquire() as db:
        await init_schema(db)
        await seed_data(db)
    logger.info("✅ PostgreSQL prêt — seed OK")
    yield
    await close_pool()


# --------------------------------------------------------------------------- #
# Schéma + seed
# --------------------------------------------------------------------------- #

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id           SERIAL PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    mp           TEXT NOT NULL,
    prenom       TEXT,
    nom          TEXT,
    full_name    TEXT,
    role         TEXT NOT NULL DEFAULT 'agent_terrain',
    token_y      TEXT UNIQUE,
    etat         TEXT DEFAULT 'deconnecte',
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forets (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    code         TEXT NOT NULL,
    area_ha      DOUBLE PRECISION NOT NULL,
    region       TEXT NOT NULL,
    center_lat   DOUBLE PRECISION NOT NULL,
    center_lng   DOUBLE PRECISION NOT NULL,
    description  TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id           TEXT PRIMARY KEY,
    forest_id    TEXT NOT NULL REFERENCES forets(id) ON DELETE CASCADE,
    alert_type   TEXT NOT NULL,
    severity     TEXT NOT NULL,
    lat          DOUBLE PRECISION NOT NULL,
    lng          DOUBLE PRECISION NOT NULL,
    area_ha      DOUBLE PRECISION NOT NULL,
    description  TEXT NOT NULL,
    source       TEXT DEFAULT 'satellite',
    status       TEXT DEFAULT 'detectee',
    history      JSONB DEFAULT '[]'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    created_by   TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_forest ON alerts(forest_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);

CREATE TABLE IF NOT EXISTS observations (
    id                  TEXT PRIMARY KEY,
    forest_id           TEXT NOT NULL REFERENCES forets(id) ON DELETE CASCADE,
    alert_id            TEXT,
    observation_type    TEXT NOT NULL,
    lat                 DOUBLE PRECISION NOT NULL,
    lng                 DOUBLE PRECISION NOT NULL,
    description         TEXT NOT NULL,
    photo_url           TEXT,
    agent_id            TEXT,
    agent_name          TEXT NOT NULL,
    source              TEXT DEFAULT 'manuel',
    kobo_submission_id  TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_obs_forest ON observations(forest_id);

CREATE TABLE IF NOT EXISTS drone_missions (
    id            TEXT PRIMARY KEY,
    forest_id     TEXT NOT NULL REFERENCES forets(id) ON DELETE CASCADE,
    alert_id      TEXT,
    pilot_id      TEXT,
    planned_date  TIMESTAMPTZ NOT NULL,
    target_lat    DOUBLE PRECISION NOT NULL,
    target_lng    DOUBLE PRECISION NOT NULL,
    radius_m      DOUBLE PRECISION DEFAULT 500,
    purpose       TEXT NOT NULL,
    status        TEXT DEFAULT 'planifiee',
    notes         TEXT DEFAULT '',
    ndvi_avg      DOUBLE PRECISION,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    created_by    TEXT
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    input_text  TEXT NOT NULL,
    context     TEXT,
    response    TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kobo_submissions (
    id                  TEXT PRIMARY KEY,
    kobo_id             TEXT NOT NULL,
    form_id             TEXT,
    form_type           TEXT DEFAULT 'observation',
    raw_payload         JSONB NOT NULL,
    lat                 DOUBLE PRECISION,
    lng                 DOUBLE PRECISION,
    description         TEXT,
    submitted_by        TEXT,
    submitted_at        TIMESTAMPTZ,
    forest_id           TEXT,
    alert_id            TEXT,
    observation_id      TEXT,
    processed           BOOLEAN DEFAULT FALSE,
    received_at         TIMESTAMPTZ DEFAULT NOW()
);
"""


async def init_schema(db):
    for stmt in SCHEMA_SQL.strip().split(";\n\n"):
        s = stmt.strip()
        if s:
            await db.execute(s)


async def seed_data(db):
    import bcrypt, uuid, random
    from datetime import datetime, timezone, timedelta

    admin_email = os.getenv("ADMIN_EMAIL", "admin@gestpro.ci")
    admin_pwd = os.getenv("ADMIN_PASSWORD", "GestPro2026!")

    def _hash(p):
        return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

    # Users
    existing = await db.fetchrow("SELECT id, mp FROM utilisateurs WHERE email=$1", admin_email)
    if not existing:
        await db.execute(
            "INSERT INTO utilisateurs (email, mp, full_name, role, token_y) VALUES ($1,$2,$3,$4,$5)",
            admin_email, _hash(admin_pwd), "Administrateur GestPro", "admin", uuid.uuid4().hex[:16],
        )
    elif not bcrypt.checkpw(admin_pwd.encode(), existing["mp"].encode()):
        await db.execute("UPDATE utilisateurs SET mp=$1 WHERE email=$2", _hash(admin_pwd), admin_email)

    demos = [
        ("analyste@gestpro.ci", "Analyste2026!", "Akissi Brou", "analyste_sig"),
        ("agent@gestpro.ci",    "Agent2026!",    "Kouamé Yao",   "agent_terrain"),
        ("pilote@gestpro.ci",   "Pilote2026!",   "Diomandé Sékou","pilote_drone"),
    ]
    for email, pwd, name, role in demos:
        if not await db.fetchrow("SELECT id FROM utilisateurs WHERE email=$1", email):
            await db.execute(
                "INSERT INTO utilisateurs (email, mp, full_name, role, token_y) VALUES ($1,$2,$3,$4,$5)",
                email, _hash(pwd), name, role, uuid.uuid4().hex[:16],
            )

    # Forests
    fcount = await db.fetchval("SELECT COUNT(*) FROM forets")
    if fcount == 0:
        await db.executemany(
            """INSERT INTO forets (id,name,code,area_ha,region,center_lat,center_lng,description)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            [
                (str(uuid.uuid4()), "Forêt Classée de Sangoué", "FC-SANG", 36200,
                 "Lôh-Djiboua / Gôh (Gagnoa)", 6.10, -5.95,
                 "Forêt classée de 36 200 ha sous la gestion du Centre de Gagnoa. Pression cacao + exploitation illégale."),
                (str(uuid.uuid4()), "Forêt Classée de Téné", "FC-TENE", 29700,
                 "Gôh (Gagnoa)", 6.30, -6.05,
                 "Forêt classée de 29 700 ha. Surveillance prioritaire des limites Nord-Est."),
            ],
        )

    # Alerts demo
    if await db.fetchval("SELECT COUNT(*) FROM alerts") == 0:
        forests = await db.fetch("SELECT id, name, center_lat, center_lng FROM forets")
        admin_id = await db.fetchval("SELECT token_y FROM utilisateurs WHERE email=$1", admin_email)
        types = ["deforestation","agriculture_illegale","feu_de_brousse","exploitation_illegale","defrichement"]
        statuses = ["detectee","en_verification","confirmee","resolue"]
        sevs = ["faible","moyenne","haute","critique"]
        rng = random.Random(42)
        rows = []
        for f in forests:
            for _ in range(7):
                at = datetime.now(timezone.utc) - timedelta(days=rng.randint(0,30))
                rows.append((
                    str(uuid.uuid4()), f["id"], rng.choice(types), rng.choice(sevs),
                    f["center_lat"]+rng.uniform(-0.08,0.08), f["center_lng"]+rng.uniform(-0.08,0.08),
                    round(rng.uniform(0.5,25),2),
                    f"Anomalie détectée par satellite Sentinel-2 dans {f['name']}",
                    rng.choice(["satellite","drone","terrain"]),
                    rng.choice(statuses),
                    '[{"status":"detectee","at":"'+at.isoformat()+'","by":"Système GEE","note":"Détection automatique"}]',
                    at, admin_id,
                ))
        await db.executemany(
            "INSERT INTO alerts (id,forest_id,alert_type,severity,lat,lng,area_ha,description,source,status,history,created_at,created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13)",
            rows,
        )

    # Observations demo
    if await db.fetchval("SELECT COUNT(*) FROM observations") == 0:
        forests = await db.fetch("SELECT id, center_lat, center_lng FROM forets")
        agent = await db.fetchrow("SELECT token_y, full_name FROM utilisateurs WHERE email='agent@gestpro.ci'")
        descs = [
            "Plantation de cacao récemment installée à l'intérieur du périmètre forestier.",
            "Traces de feu de brousse, environ 2 ha brûlés.",
            "Coupe de bois illégale observée, plusieurs souches récentes.",
            "Défrichement actif - tronçonneuses entendues.",
            "Forêt intacte, aucun signe d'activité illégale.",
        ]
        rng = random.Random(7)
        rows = []
        for f in forests:
            for _ in range(4):
                rows.append((
                    str(uuid.uuid4()), f["id"], None,
                    rng.choice(["deforestation","agriculture_illegale","feu_de_brousse","exploitation_illegale","autre"]),
                    f["center_lat"]+rng.uniform(-0.05,0.05),
                    f["center_lng"]+rng.uniform(-0.05,0.05),
                    rng.choice(descs), None,
                    agent["token_y"] if agent else None,
                    agent["full_name"] if agent else "Agent terrain",
                    "manuel",
                    datetime.now(timezone.utc)-timedelta(days=rng.randint(0,20)),
                ))
        await db.executemany(
            "INSERT INTO observations (id,forest_id,alert_id,observation_type,lat,lng,description,photo_url,agent_id,agent_name,source,created_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
            rows,
        )

    # Drone missions demo
    if await db.fetchval("SELECT COUNT(*) FROM drone_missions") == 0:
        forests = await db.fetch("SELECT id, center_lat, center_lng FROM forets")
        pilote = await db.fetchval("SELECT token_y FROM utilisateurs WHERE email='pilote@gestpro.ci'")
        rng = random.Random(11)
        rows = []
        for f in forests:
            for _ in range(3):
                status = rng.choice(["planifiee","en_cours","terminee"])
                rows.append((
                    str(uuid.uuid4()), f["id"], None, pilote,
                    datetime.now(timezone.utc)+timedelta(days=rng.randint(-10,14)),
                    f["center_lat"]+rng.uniform(-0.06,0.06),
                    f["center_lng"]+rng.uniform(-0.06,0.06),
                    rng.choice([300,500,1000]),
                    rng.choice(["Vérification d'alerte","Cartographie haute résolution","Suivi NDVI","Inspection de zone à risque"]),
                    status,
                    "Mission terminée avec succès." if status=="terminee" else "",
                    round(rng.uniform(0.4,0.85),2) if status=="terminee" else None,
                    datetime.now(timezone.utc) if status=="terminee" else None,
                    pilote,
                ))
        await db.executemany(
            "INSERT INTO drone_missions (id,forest_id,alert_id,pilot_id,planned_date,target_lat,target_lng,radius_m,purpose,status,notes,ndvi_avg,completed_at,created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
            rows,
        )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="GestPro",
    description="Plateforme de Surveillance des Forêts Classées de Gagnoa — architecture GESTREB",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("MY_SECRET", "mysecret_change_me"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_origin_regex=".*",
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Static
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/js",  StaticFiles(directory="static/js"),  name="js")
app.mount("/img", StaticFiles(directory="static/img"), name="img")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(pages_router)          # HTML pages (/, /connexion, /dashboard, ...)
app.include_router(auth_router)
app.include_router(alerts_router,       prefix="/api")
app.include_router(observations_router, prefix="/api")
app.include_router(drones_router,       prefix="/api")
app.include_router(gee_router,          prefix="/api")
app.include_router(predictions_router,  prefix="/api")
app.include_router(ai_router,           prefix="/api")
app.include_router(kobo_router,         prefix="/api")
app.include_router(users_router,        prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "GestPro v3 (GESTREB-style)"}


@app.get("/api/")
async def api_root():
    return {"app": "GestPro", "status": "ok", "version": "3.0.0", "db": "PostgreSQL", "style": "GESTREB"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
