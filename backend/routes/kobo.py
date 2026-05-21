"""Kobo Toolbox webhook + listing."""
import os, uuid
from datetime import datetime, timezone
import json
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Header

from database import get_db
from auth import require_auth

router = APIRouter()


def _extract_field(payload, *names):
    for name in names:
        if name in payload and payload[name] not in (None, ""):
            return payload[name]
    for k, v in payload.items():
        for name in names:
            if k.endswith(f"/{name}") and v not in (None, ""):
                return v
    return None


def _extract_geo(payload):
    geo = payload.get("_geolocation")
    if isinstance(geo, list) and len(geo) >= 2 and geo[0] is not None:
        try: return float(geo[0]), float(geo[1])
        except: pass
    raw = _extract_field(payload, "geopoint", "location", "gps", "_geopoint")
    if raw and isinstance(raw, str):
        parts = raw.split()
        if len(parts) >= 2:
            try: return float(parts[0]), float(parts[1])
            except: pass
    lat = _extract_field(payload, "lat", "latitude")
    lng = _extract_field(payload, "lng", "lon", "longitude")
    try:
        return (float(lat) if lat is not None else None,
                float(lng) if lng is not None else None)
    except: return None, None


def _classify(payload, form_id):
    if form_id:
        fid = form_id.lower()
        if "verif" in fid: return "verification"
        if "infract" in fid: return "infraction"
    if _extract_field(payload, "alert_id", "id_alerte"): return "verification"
    return "observation"


@router.post("/kobo/webhook")
async def kobo_webhook(
    request: Request,
    x_kobo_token: Optional[str] = Header(None, alias="X-Kobo-Token"),
    db=Depends(get_db),
):
    secret = os.environ.get("KOBO_WEBHOOK_SECRET")
    if secret and x_kobo_token != secret:
        raise HTTPException(401, "Token webhook invalide")

    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(400, "Payload Kobo invalide")

    kobo_id = str(payload.get("_id") or payload.get("instanceID") or payload.get("meta/instanceID") or uuid.uuid4())
    form_id = payload.get("_xform_id_string") or payload.get("formId") or payload.get("form_id")
    form_type = _classify(payload, form_id)
    lat, lng = _extract_geo(payload)
    description = _extract_field(payload, "description", "comment", "notes", "remarks") or ""
    submitted_by = _extract_field(payload, "username", "_submitted_by") or payload.get("_submitted_by") or "Kobo"
    raw_dt = payload.get("_submission_time") or payload.get("end") or payload.get("start")
    submitted_at = None
    if raw_dt:
        try: submitted_at = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
        except: pass

    # Resolve forest
    forest_ref = _extract_field(payload, "forest_id", "id_foret", "foret", "forest_code", "code_foret")
    forest_id = None
    if forest_ref:
        f = await db.fetchrow("SELECT id FROM forets WHERE id=$1 OR code=$1 OR name=$1", forest_ref)
        if f: forest_id = f["id"]
    if not forest_id and lat is not None and lng is not None:
        nearest = await db.fetchrow(
            "SELECT id FROM forets ORDER BY (center_lat - $1)^2 + (center_lng - $2)^2 LIMIT 1",
            lat, lng,
        )
        if nearest: forest_id = nearest["id"]

    alert_ref = _extract_field(payload, "alert_id", "id_alerte")
    sub_id = str(uuid.uuid4())

    obs_id = None
    if lat is not None and lng is not None and forest_id and form_type in ("observation", "verification"):
        obs_type = _extract_field(payload, "observation_type", "type") or "autre"
        if obs_type not in {"deforestation","agriculture_illegale","feu_de_brousse","exploitation_illegale","defrichement","autre"}:
            obs_type = "autre"
        photo = _extract_field(payload, "photo", "image", "photo_url")
        obs_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO observations (id,forest_id,alert_id,observation_type,lat,lng,description,photo_url,agent_id,agent_name,source,kobo_submission_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'kobo',$11)""",
            obs_id, forest_id, alert_ref, obs_type, lat, lng,
            description or f"Soumission Kobo {kobo_id}",
            photo if isinstance(photo, str) and photo.startswith("http") else None,
            None, submitted_by or "Kobo", sub_id,
        )

    await db.execute(
        """INSERT INTO kobo_submissions (id,kobo_id,form_id,form_type,raw_payload,lat,lng,description,submitted_by,submitted_at,forest_id,alert_id,observation_id,processed)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
        sub_id, kobo_id, form_id, form_type, json.dumps(payload),
        lat, lng, description, submitted_by, submitted_at,
        forest_id, alert_ref, obs_id, obs_id is not None,
    )

    # Update alert if verification with alert_ref
    if form_type == "verification" and alert_ref:
        a = await db.fetchrow("SELECT history FROM alerts WHERE id=$1", alert_ref)
        if a:
            history = a["history"] if isinstance(a["history"], list) else json.loads(a["history"] or "[]")
            history.append({
                "status": "en_verification",
                "at": datetime.now(timezone.utc).isoformat(),
                "by": f"Kobo · {submitted_by or '—'}",
                "note": f"Vérification terrain: {description[:200]}",
            })
            await db.execute(
                "UPDATE alerts SET status='en_verification', history=$1::jsonb WHERE id=$2",
                json.dumps(history), alert_ref,
            )

    return {"ok": True, "submission_id": sub_id, "observation_id": obs_id, "form_type": form_type}


@router.get("/kobo/submissions")
async def list_submissions(request: Request, limit: int = 100, db=Depends(get_db)):
    require_auth(request)
    rows = await db.fetch("SELECT * FROM kobo_submissions ORDER BY received_at DESC LIMIT $1", limit)
    out = []
    for r in rows:
        d = dict(r)
        for k in ("received_at", "submitted_at"):
            if d.get(k): d[k] = d[k].isoformat()
        if isinstance(d.get("raw_payload"), str):
            try: d["raw_payload"] = json.loads(d["raw_payload"])
            except: pass
        out.append(d)
    return out


@router.get("/kobo/info")
async def kobo_info(request: Request):
    require_auth(request)
    base = os.environ.get("PUBLIC_BASE_URL")
    if not base:
        fp = request.headers.get("x-forwarded-proto", "https")
        fh = request.headers.get("x-forwarded-host") or request.headers.get("host")
        base = f"{fp}://{fh}" if fh else str(request.base_url).rstrip("/")
    base = base.rstrip("/")
    return {
        "webhook_url": f"{base}/api/kobo/webhook",
        "header_name": "X-Kobo-Token",
        "header_value": os.environ.get("KOBO_WEBHOOK_SECRET", ""),
        "instructions": [
            "1. kf.kobotoolbox.org → formulaire → Settings → REST Services → Register",
            "2. Service Name: GestPro",
            f"3. Endpoint URL: {base}/api/kobo/webhook",
            "4. Custom HTTP Headers: X-Kobo-Token = <token ci-dessus>",
            "5. Sauvegarder",
        ],
    }
