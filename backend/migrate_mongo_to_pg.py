"""One-shot migration: copy existing data from MongoDB → PostgreSQL.
Usage: cd /app/backend && python migrate_mongo_to_pg.py
"""
import asyncio
import os
import ssl
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import models as M
from db import Base


async def main():
    # MongoDB
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    mc = AsyncIOMotorClient(mongo_url)
    mdb = mc[db_name]

    # PostgreSQL
    db_url = os.environ["DATABASE_URL"]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    pg = create_async_engine(db_url, connect_args={"ssl": ctx})
    async with pg.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(pg, class_=AsyncSession, expire_on_commit=False)

    counts = {"users": 0, "forests": 0, "alerts": 0, "observations": 0, "drone_missions": 0, "ai_analyses": 0}

    async with Session() as db:
        # Users
        async for u in mdb.users.find({}):
            r = await db.execute(select(M.User).where(M.User.email == u["email"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.User(
                id=u["id"],
                email=u["email"],
                password_hash=u["password_hash"],
                full_name=u.get("full_name", "—"),
                role=u.get("role", "agent_terrain"),
                active=u.get("active", True),
                created_at=_parse_dt(u.get("created_at")),
            ))
            counts["users"] += 1
        await db.commit()

        # Forests
        async for f in mdb.forests.find({}):
            r = await db.execute(select(M.Forest).where(M.Forest.id == f["id"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.Forest(
                id=f["id"], name=f["name"], code=f["code"], area_ha=f["area_ha"],
                region=f["region"], center_lat=f["center_lat"], center_lng=f["center_lng"],
                description=f["description"],
                created_at=_parse_dt(f.get("created_at")),
            ))
            counts["forests"] += 1
        await db.commit()

        # Alerts
        async for a in mdb.alerts.find({}):
            r = await db.execute(select(M.Alert).where(M.Alert.id == a["id"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.Alert(
                id=a["id"], forest_id=a["forest_id"], alert_type=a["alert_type"],
                severity=a["severity"], lat=a["lat"], lng=a["lng"], area_ha=a["area_ha"],
                description=a["description"], source=a.get("source", "satellite"),
                status=a.get("status", "detectee"), history=a.get("history", []),
                created_at=_parse_dt(a.get("created_at")), created_by=a.get("created_by"),
            ))
            counts["alerts"] += 1
        await db.commit()

        # Observations
        async for o in mdb.observations.find({}):
            r = await db.execute(select(M.Observation).where(M.Observation.id == o["id"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.Observation(
                id=o["id"], forest_id=o["forest_id"], alert_id=o.get("alert_id"),
                observation_type=o["observation_type"], lat=o["lat"], lng=o["lng"],
                description=o["description"], photo_url=o.get("photo_url"),
                agent_id=o.get("agent_id"), agent_name=o.get("agent_name", "—"),
                source="manuel",
                created_at=_parse_dt(o.get("created_at")),
            ))
            counts["observations"] += 1
        await db.commit()

        # Drone missions
        async for m in mdb.drone_missions.find({}):
            r = await db.execute(select(M.DroneMission).where(M.DroneMission.id == m["id"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.DroneMission(
                id=m["id"], forest_id=m["forest_id"], alert_id=m.get("alert_id"),
                pilot_id=m.get("pilot_id"),
                planned_date=_parse_dt(m["planned_date"]) or datetime.now(timezone.utc),
                target_lat=m["target_lat"], target_lng=m["target_lng"],
                radius_m=m.get("radius_m", 500), purpose=m["purpose"],
                status=m.get("status", "planifiee"), notes=m.get("notes", ""),
                ndvi_avg=m.get("ndvi_avg"),
                completed_at=_parse_dt(m.get("completed_at")),
                created_at=_parse_dt(m.get("created_at")), created_by=m.get("created_by"),
            ))
            counts["drone_missions"] += 1
        await db.commit()

        # AI analyses
        async for x in mdb.ai_analyses.find({}):
            r = await db.execute(select(M.AIAnalysis).where(M.AIAnalysis.id == x["id"]))
            if r.scalar_one_or_none():
                continue
            db.add(M.AIAnalysis(
                id=x["id"], user_id=x["user_id"], input_text=x["input_text"],
                context=x.get("context"), response=x["response"], model=x["model"],
                created_at=_parse_dt(x.get("created_at")),
            ))
            counts["ai_analyses"] += 1
        await db.commit()

    print("Migration MongoDB → PostgreSQL terminée")
    for k, v in counts.items():
        print(f"  {k}: +{v}")
    await pg.dispose()
    mc.close()


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    asyncio.run(main())
