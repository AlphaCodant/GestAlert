"""GEE mock — indices NDVI/NBR/NDWI + landcover."""
import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_auth

router = APIRouter()


def _forest_dict(r):
    d = dict(r); d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d


@router.get("/gee/indices/{forest_id}")
async def gee_indices(forest_id: str, request: Request, db=Depends(get_db)):
    require_auth(request)
    f = await db.fetchrow("SELECT * FROM forets WHERE id=$1", forest_id)
    if not f:
        raise HTTPException(404, "Forêt introuvable")
    rng = random.Random(forest_id)
    months = []
    base = datetime.now(timezone.utc)
    for i in range(12, 0, -1):
        d = base - timedelta(days=30 * i)
        ndvi = max(0.2, round(rng.uniform(0.55, 0.85) - i * 0.005, 3))
        months.append({
            "month": d.strftime("%Y-%m"),
            "ndvi": ndvi,
            "nbr": round(rng.uniform(0.30, 0.65), 3),
            "ndwi": round(rng.uniform(0.10, 0.40), 3),
            "cloud_cover": round(rng.uniform(2, 25), 1),
        })
    return {
        "forest": _forest_dict(f),
        "satellite_sources": ["Sentinel-2 (10m, 5j)", "Landsat-9 (30m)", "MODIS (250m)"],
        "time_series": months,
        "summary": {
            "ndvi_current": months[-1]["ndvi"],
            "ndvi_trend": round(months[-1]["ndvi"] - months[0]["ndvi"], 3),
            "ndvi_status": "stable" if abs(months[-1]["ndvi"] - months[0]["ndvi"]) < 0.05 else "déclin",
        },
    }


@router.get("/gee/landcover/{forest_id}")
async def gee_landcover(forest_id: str, request: Request, db=Depends(get_db)):
    require_auth(request)
    f = await db.fetchrow("SELECT * FROM forets WHERE id=$1", forest_id)
    if not f:
        raise HTTPException(404, "Forêt introuvable")
    rng = random.Random(forest_id + "lc")
    classes = [
        {"name": "Forêt dense",         "color": "#1e5128", "percent": round(rng.uniform(45, 65), 1)},
        {"name": "Forêt dégradée",      "color": "#4f7942", "percent": round(rng.uniform(15, 25), 1)},
        {"name": "Agriculture (cacao)", "color": "#c9a66b", "percent": round(rng.uniform(8, 18), 1)},
        {"name": "Sol nu",              "color": "#a87e4a", "percent": round(rng.uniform(2, 8), 1)},
        {"name": "Zones brûlées",       "color": "#8b3a1a", "percent": round(rng.uniform(0.5, 4), 1)},
    ]
    total = sum(c["percent"] for c in classes)
    for c in classes: c["percent"] = round(c["percent"] * 100 / total, 1)
    return {"forest": _forest_dict(f), "classes": classes, "resolution_m": 10, "source": "Sentinel-2 + Random Forest"}
