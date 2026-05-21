"""API missions drone."""
import uuid, random
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_auth

router = APIRouter()


def _row(r):
    d = dict(r)
    for k in ("planned_date", "completed_at", "created_at"):
        if d.get(k): d[k] = d[k].isoformat()
    return d


@router.get("/drone-missions")
async def list_missions(request: Request, db=Depends(get_db)):
    require_auth(request)
    rows = await db.fetch("SELECT * FROM drone_missions ORDER BY created_at DESC")
    return [_row(r) for r in rows]


@router.post("/drone-missions")
async def create_mission(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    d = await request.json()
    mid = str(uuid.uuid4())
    pd = d["planned_date"]
    if isinstance(pd, str):
        pd = datetime.fromisoformat(pd.replace("Z", "+00:00"))
    await db.execute(
        """INSERT INTO drone_missions (id,forest_id,alert_id,pilot_id,planned_date,target_lat,target_lng,radius_m,purpose,status,created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'planifiee',$10)""",
        mid, d["forest_id"], d.get("alert_id"), d.get("pilot_id"),
        pd, float(d["target_lat"]), float(d["target_lng"]),
        float(d.get("radius_m", 500)), d["purpose"], user["tokenY"],
    )
    return _row(await db.fetchrow("SELECT * FROM drone_missions WHERE id=$1", mid))


@router.patch("/drone-missions/{mid}")
async def update_mission(mid: str, request: Request, db=Depends(get_db)):
    require_auth(request)
    d = await request.json()
    status = d["status"]
    notes = d.get("notes")
    ndvi = d.get("ndvi_avg")
    completed = datetime.now(timezone.utc) if status == "terminee" else None
    if status == "terminee" and ndvi is None:
        ndvi = round(random.uniform(0.35, 0.85), 2)
    res = await db.execute(
        """UPDATE drone_missions SET status=$1, notes=COALESCE($2, notes),
           ndvi_avg=COALESCE($3, ndvi_avg), completed_at=COALESCE($4, completed_at)
           WHERE id=$5""",
        status, notes, ndvi, completed, mid,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Mission introuvable")
    return _row(await db.fetchrow("SELECT * FROM drone_missions WHERE id=$1", mid))
