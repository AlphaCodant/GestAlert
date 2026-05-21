"""API alertes — asyncpg brut."""
import uuid, json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_auth

router = APIRouter()


def _row(r):
    d = dict(r)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    h = d.get("history")
    if isinstance(h, str):
        try: d["history"] = json.loads(h)
        except: d["history"] = []
    return d


@router.get("/forests")
async def list_forests(request: Request, db=Depends(get_db)):
    require_auth(request)
    rows = await db.fetch("SELECT * FROM forets ORDER BY name")
    return [_row(r) for r in rows]


@router.get("/alerts")
async def list_alerts(request: Request, status_filter: str = None, forest_id: str = None, db=Depends(get_db)):
    require_auth(request)
    q = "SELECT * FROM alerts WHERE 1=1"
    args = []
    if status_filter:
        args.append(status_filter); q += f" AND status=${len(args)}"
    if forest_id:
        args.append(forest_id); q += f" AND forest_id=${len(args)}"
    q += " ORDER BY created_at DESC"
    rows = await db.fetch(q, *args)
    return [_row(r) for r in rows]


@router.post("/alerts")
async def create_alert(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    data = await request.json()
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    history = [{"status": "detectee", "at": now.isoformat(), "by": user["full_name"], "note": "Alerte créée"}]
    await db.execute(
        """INSERT INTO alerts (id,forest_id,alert_type,severity,lat,lng,area_ha,description,source,status,history,created_by,created_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'detectee',$10::jsonb,$11,$12)""",
        aid, data["forest_id"], data["alert_type"], data["severity"],
        float(data["lat"]), float(data["lng"]), float(data["area_ha"]),
        data["description"], data.get("source", "satellite"),
        json.dumps(history), user["tokenY"], now,
    )
    row = await db.fetchrow("SELECT * FROM alerts WHERE id=$1", aid)
    return _row(row)


@router.patch("/alerts/{alert_id}/status")
async def update_status(alert_id: str, request: Request, db=Depends(get_db)):
    user = require_auth(request)
    data = await request.json()
    new_status = data["status"]
    note = data.get("note", "")
    row = await db.fetchrow("SELECT history FROM alerts WHERE id=$1", alert_id)
    if not row:
        raise HTTPException(404, "Alerte introuvable")
    history = row["history"] if isinstance(row["history"], list) else json.loads(row["history"] or "[]")
    history.append({"status": new_status, "at": datetime.now(timezone.utc).isoformat(), "by": user["full_name"], "note": note})
    await db.execute("UPDATE alerts SET status=$1, history=$2::jsonb WHERE id=$3",
                     new_status, json.dumps(history), alert_id)
    return _row(await db.fetchrow("SELECT * FROM alerts WHERE id=$1", alert_id))


@router.delete("/alerts/{alert_id}")
async def del_alert(alert_id: str, request: Request, db=Depends(get_db)):
    user = require_auth(request)
    if user["role"] not in ("admin", "analyste_sig"):
        raise HTTPException(403, "Accès refusé")
    res = await db.execute("DELETE FROM alerts WHERE id=$1", alert_id)
    if res.endswith("0"):
        raise HTTPException(404, "Alerte introuvable")
    return {"message": "Alerte supprimée"}


@router.get("/stats/dashboard")
async def stats_dashboard(request: Request, db=Depends(get_db)):
    require_auth(request)
    totals = {
        "alerts": await db.fetchval("SELECT COUNT(*) FROM alerts"),
        "observations": await db.fetchval("SELECT COUNT(*) FROM observations"),
        "drone_missions": await db.fetchval("SELECT COUNT(*) FROM drone_missions"),
        "forests": await db.fetchval("SELECT COUNT(*) FROM forets"),
        "total_area_ha": await db.fetchval("SELECT COALESCE(SUM(area_ha),0) FROM forets"),
        "pending": await db.fetchval("SELECT COUNT(*) FROM alerts WHERE status IN ('detectee','en_verification')"),
        "kobo_submissions": await db.fetchval("SELECT COUNT(*) FROM kobo_submissions"),
    }
    by_status = [{"status": r["status"], "count": r["count"]} for r in await db.fetch("SELECT status, COUNT(*) AS count FROM alerts GROUP BY status")]
    by_type   = [{"type":   r["alert_type"], "count": r["count"]} for r in await db.fetch("SELECT alert_type, COUNT(*) AS count FROM alerts GROUP BY alert_type")]
    recent    = [_row(r) for r in await db.fetch("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 5")]
    return {"totals": totals, "alerts_by_status": by_status, "alerts_by_type": by_type, "recent_alerts": recent}
