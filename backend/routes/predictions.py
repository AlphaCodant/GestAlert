"""Prédictions de déforestation (mock)."""
import random
from fastapi import APIRouter, Request, Depends, HTTPException
from database import get_db
from auth import require_auth

router = APIRouter()


@router.get("/predictions/{forest_id}")
async def predictions(forest_id: str, request: Request, db=Depends(get_db)):
    require_auth(request)
    f = await db.fetchrow("SELECT * FROM forets WHERE id=$1", forest_id)
    if not f:
        raise HTTPException(404, "Forêt introuvable")
    rng = random.Random(forest_id + "pred")
    cells = []
    grid_size = 8
    spread = 0.15
    for i in range(grid_size):
        for j in range(grid_size):
            edge = max(abs(i - grid_size / 2), abs(j - grid_size / 2)) / (grid_size / 2)
            risk = min(0.95, max(0.05, rng.uniform(0.05, 0.4) + edge * 0.45))
            cells.append({
                "lat": f["center_lat"] + (i - grid_size / 2) * (spread / grid_size),
                "lng": f["center_lng"] + (j - grid_size / 2) * (spread / grid_size),
                "risk": round(risk, 3),
            })
    high = [c for c in cells if c["risk"] >= 0.7]
    return {
        "forest": {**dict(f), "created_at": f["created_at"].isoformat() if f["created_at"] else None},
        "cells": cells,
        "high_risk_count": len(high),
        "high_risk_zones": high[:10],
        "model": "Random Forest + Logistic Regression (historiques 2018-2025)",
        "horizon_days": 90,
    }
