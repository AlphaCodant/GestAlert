"""API observations."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_auth

router = APIRouter()


def _row(r):
    d = dict(r)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d


@router.get("/observations")
async def list_obs(request: Request, db=Depends(get_db)):
    require_auth(request)
    rows = await db.fetch("SELECT * FROM observations ORDER BY created_at DESC")
    return [_row(r) for r in rows]


@router.post("/observations")
async def create_obs(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    d = await request.json()
    oid = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO observations (id,forest_id,alert_id,observation_type,lat,lng,description,photo_url,agent_id,agent_name,source)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'manuel')""",
        oid, d["forest_id"], d.get("alert_id"), d["observation_type"],
        float(d["lat"]), float(d["lng"]), d["description"],
        d.get("photo_url"), user["tokenY"], user["full_name"],
    )
    return _row(await db.fetchrow("SELECT * FROM observations WHERE id=$1", oid))


@router.delete("/observations/{obs_id}")
async def del_obs(obs_id: str, request: Request, db=Depends(get_db)):
    user = require_auth(request)
    if user["role"] not in ("admin", "analyste_sig"):
        raise HTTPException(403, "Accès refusé")
    res = await db.execute("DELETE FROM observations WHERE id=$1", obs_id)
    if res.endswith("0"):
        raise HTTPException(404, "Introuvable")
    return {"message": "Supprimée"}
