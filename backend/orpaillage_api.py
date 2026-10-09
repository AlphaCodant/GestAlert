"""API du module « Orpaillage » : détection satellitaire des zones suspectes dans le Gôh."""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models as M
import orpaillage_core as core
import orpaillage_gee as gee
from db import SessionLocal, get_session

logger = logging.getLogger("gestpro.orpaillage")

DETECTION_STATUSES = ("presume", "precise", "confirme", "infirme")
LEVEL_TO_SEVERITY = {"forte": "haute", "moyenne": "moyenne", "faible": "faible"}


# -------------------- Schémas --------------------
class ZoneCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    geometry: Optional[dict] = None  # GeoJSON (Polygon, MultiPolygon, Feature, FeatureCollection)
    min_lat: Optional[float] = None
    min_lng: Optional[float] = None
    max_lat: Optional[float] = None
    max_lng: Optional[float] = None

    @model_validator(mode="after")
    def _geometry_or_bbox(self):
        has_bbox = None not in (self.min_lat, self.min_lng, self.max_lat, self.max_lng)
        if self.geometry is None and not has_bbox:
            raise ValueError("Fournir une géométrie GeoJSON ou une emprise (min/max latitude et longitude)")
        return self


class RunParams(BaseModel):
    dndvi_min: float = Field(core.DEFAULT_PARAMS["dndvi_min"], ge=0.05, le=0.8)
    bsi_min: float = Field(core.DEFAULT_PARAMS["bsi_min"], ge=-0.3, le=0.6)
    min_area_ha: float = Field(core.DEFAULT_PARAMS["min_area_ha"], ge=0.1, le=50)
    max_cloud: float = Field(core.DEFAULT_PARAMS["max_cloud"], ge=5, le=100)
    water_buffer_m: float = Field(core.DEFAULT_PARAMS["water_buffer_m"], ge=200, le=5000)
    known_site_radius_m: float = Field(core.DEFAULT_PARAMS["known_site_radius_m"], ge=50, le=2000)


class RunCreate(BaseModel):
    zone_id: str
    ref_start: date
    ref_end: date
    recent_start: date
    recent_end: date
    mode: Literal["auto", "gee", "simulation"] = "auto"
    params: RunParams = Field(default_factory=RunParams)

    @model_validator(mode="after")
    def _dates(self):
        if self.ref_start >= self.ref_end or self.recent_start >= self.recent_end:
            raise ValueError("Chaque période doit avoir une date de début antérieure à sa date de fin")
        if self.ref_end > self.recent_start:
            raise ValueError("La période de référence doit précéder la période récente")
        return self


class DetectionStatusUpdate(BaseModel):
    status: Literal["presume", "precise", "confirme", "infirme"]
    note: Optional[str] = None


class DetectionMissionCreate(BaseModel):
    planned_date: date
    pilot_id: Optional[str] = None
    radius_m: float = Field(300, ge=50, le=5000)


# -------------------- Sérialisation --------------------
def s_zone(z: M.SurveillanceZone) -> dict:
    return {
        "id": z.id, "name": z.name, "description": z.description, "geometry": z.geometry,
        "bbox": {"min_lat": z.min_lat, "min_lng": z.min_lng, "max_lat": z.max_lat, "max_lng": z.max_lng},
        "area_ha": round(core.area_ha(z.geometry)), "approximate": z.approximate,
        "created_at": z.created_at.isoformat() if z.created_at else None,
    }


def s_run(r: M.DetectionRun) -> dict:
    return {
        "id": r.id, "zone_id": r.zone_id, "mode": r.mode, "status": r.status,
        "ref_start": r.ref_start, "ref_end": r.ref_end,
        "recent_start": r.recent_start, "recent_end": r.recent_end,
        "params": r.params, "detections_count": r.detections_count, "images_used": r.images_used,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


def s_detection(d: M.MiningDetection) -> dict:
    return {
        "id": d.id, "code": d.code, "run_id": d.run_id, "zone_id": d.zone_id,
        "geometry": d.geometry, "lat": d.lat, "lng": d.lng, "area_ha": d.area_ha,
        "score": d.score, "level": d.level, "indices": d.indices or {},
        "known_site_id": d.known_site_id, "known_site_distance_m": d.known_site_distance_m,
        "status": d.status, "history": d.history or [],
        "alert_id": d.alert_id, "mission_id": d.mission_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def s_site(s: M.KnownMiningSite) -> dict:
    return {"id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng, "locality": s.locality,
            "status": s.status, "notes": s.notes}


def _zone_prefix(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", ascii_name) if w and w.lower() not in ("zone", "de", "du", "la", "le", "region", "des")]
    base = (words[-1] if words else "ZON")[:3].upper()
    return base.ljust(3, "X")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------- Traitement d'une analyse --------------------
async def process_run(run_id: str) -> None:
    async with SessionLocal() as db:
        run = (await db.execute(select(M.DetectionRun).where(M.DetectionRun.id == run_id))).scalar_one()
        zone = (await db.execute(select(M.SurveillanceZone).where(M.SurveillanceZone.id == run.zone_id))).scalar_one()
        try:
            if run.mode == "gee":
                result = await asyncio.to_thread(
                    gee.run_gee_detection, zone.geometry,
                    (run.ref_start, run.ref_end), (run.recent_start, run.recent_end), run.params,
                )
                raw, images = result["detections"], result["images"]
            else:
                raw = core.simulate_detections(zone.geometry, seed=f"{zone.id}:{run.recent_end}", params=run.params)
                images = {"source": "Simulation (données fictives)"}

            sites = (await db.execute(select(M.KnownMiningSite))).scalars().all()
            existing = (await db.execute(
                select(M.MiningDetection).where(
                    M.MiningDetection.zone_id == zone.id, M.MiningDetection.status != "infirme"
                )
            )).scalars().all()
            seq = (await db.execute(
                select(func.count()).select_from(M.MiningDetection).where(M.MiningDetection.zone_id == zone.id)
            )).scalar() or 0
            prefix = _zone_prefix(zone.name)
            radius = float(run.params.get("known_site_radius_m", 300))
            created = 0
            for item in raw:
                geom = item["geometry"]
                lat, lng = core.centroid(geom)
                if not core.point_in_geometry(lat, lng, zone.geometry):
                    continue
                dup = next((e for e in existing if core.point_in_geometry(lat, lng, e.geometry)), None)
                if dup:
                    dup.history = (dup.history or []) + [{
                        "status": dup.status, "at": _now_iso(), "by": "Analyse satellitaire",
                        "note": f"Toujours détecté lors de l'analyse du {run.recent_start} au {run.recent_end}",
                    }]
                    continue
                a = item.get("area_ha") or core.area_ha(geom)
                ind = item.get("indices") or {}
                site, dist = core.nearest_known_site(lat, lng, sites)
                near = dist is not None and dist <= radius
                score = core.suspicion_score(
                    ind.get("dndvi") or 0, ind.get("bsi") or 0, ind.get("ndti"), ind.get("dist_water_m"),
                    a, float(run.params.get("water_buffer_m", 1000)), near,
                )
                seq += 1
                db.add(M.MiningDetection(
                    code=f"{prefix}-{seq:04d}", run_id=run.id, zone_id=zone.id, geometry=geom,
                    lat=round(lat, 6), lng=round(lng, 6), area_ha=round(a, 2), score=score,
                    level=core.score_level(score), indices=ind,
                    known_site_id=site.id if near else None,
                    known_site_distance_m=round(dist, 1) if dist is not None else None,
                    status="presume",
                    history=[{"status": "presume", "at": _now_iso(), "by": "Analyse satellitaire",
                              "note": "Simulation (fictif)" if run.mode == "simulation" else "Sentinel-2 via GEE"}],
                ))
                created += 1
            run.status = "terminee"
            run.detections_count = created
            run.images_used = images
        except Exception as e:  # l'échec est enregistré et affiché dans l'interface
            logger.exception("Analyse %s en échec", run_id)
            await db.rollback()
            run = (await db.execute(select(M.DetectionRun).where(M.DetectionRun.id == run_id))).scalar_one()
            run.status = "echec"
            run.error = str(e)[:2000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()


# -------------------- Routeur --------------------
def build_router(get_current_user, require_roles) -> APIRouter:
    r = APIRouter(prefix="/orpaillage", tags=["orpaillage"])
    analyst = require_roles("analyste_sig")

    @r.get("/config")
    async def config(_u: dict = Depends(get_current_user)):
        return {
            "gee_configured": gee.gee_configured(),
            "default_params": core.DEFAULT_PARAMS,
            "levels": {name: th for name, th in core.LEVELS},
            "statuses": core.STATUS_LABEL,
        }

    # ---- Zones ----
    @r.get("/zones")
    async def list_zones(_u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
        res = await db.execute(select(M.SurveillanceZone).order_by(M.SurveillanceZone.created_at))
        return [s_zone(z) for z in res.scalars().all()]

    @r.post("/zones")
    async def create_zone(data: ZoneCreate, user: dict = Depends(analyst), db: AsyncSession = Depends(get_session)):
        try:
            geom = (core.normalize_zone_geometry(data.geometry) if data.geometry
                    else core.bbox_polygon(data.min_lat, data.min_lng, data.max_lat, data.max_lng))
            bb = core.bbox(geom)
            if core.area_ha(geom) <= 0:
                raise ValueError("La zone a une surface nulle")
        except (ValueError, KeyError, TypeError, IndexError) as e:
            raise HTTPException(status_code=400, detail=f"Géométrie invalide : {e}")
        z = M.SurveillanceZone(name=data.name, description=data.description, geometry=geom,
                               created_by=user["id"], **bb)
        db.add(z)
        await db.commit()
        await db.refresh(z)
        return s_zone(z)

    @r.delete("/zones/{zone_id}")
    async def delete_zone(zone_id: str, _u: dict = Depends(analyst), db: AsyncSession = Depends(get_session)):
        z = (await db.execute(select(M.SurveillanceZone).where(M.SurveillanceZone.id == zone_id))).scalar_one_or_none()
        if not z:
            raise HTTPException(status_code=404, detail="Zone introuvable")
        await db.delete(z)
        await db.commit()
        return {"ok": True}

    # ---- Analyses ----
    @r.post("/runs")
    async def create_run(data: RunCreate, background: BackgroundTasks, user: dict = Depends(analyst),
                         db: AsyncSession = Depends(get_session)):
        z = (await db.execute(select(M.SurveillanceZone).where(M.SurveillanceZone.id == data.zone_id))).scalar_one_or_none()
        if not z:
            raise HTTPException(status_code=404, detail="Zone introuvable")
        mode = data.mode
        if mode == "auto":
            mode = "gee" if gee.gee_configured() else "simulation"
        if mode == "gee" and not gee.gee_configured():
            raise HTTPException(status_code=400, detail="Google Earth Engine n'est pas configuré sur le serveur (compte de service manquant)")
        busy = (await db.execute(select(func.count()).select_from(M.DetectionRun).where(
            M.DetectionRun.zone_id == z.id, M.DetectionRun.status == "en_cours"))).scalar() or 0
        if busy:
            raise HTTPException(status_code=409, detail="Une analyse est déjà en cours sur cette zone")
        run = M.DetectionRun(
            zone_id=z.id, mode=mode, status="en_cours",
            ref_start=data.ref_start.isoformat(), ref_end=data.ref_end.isoformat(),
            recent_start=data.recent_start.isoformat(), recent_end=data.recent_end.isoformat(),
            params=data.params.model_dump(), created_by=user["id"],
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        background.add_task(process_run, run.id)
        return s_run(run)

    @r.get("/runs")
    async def list_runs(zone_id: Optional[str] = None, _u: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
        q = select(M.DetectionRun).order_by(M.DetectionRun.started_at.desc()).limit(50)
        if zone_id:
            q = q.where(M.DetectionRun.zone_id == zone_id)
        return [s_run(x) for x in (await db.execute(q)).scalars().all()]

    @r.get("/runs/{run_id}")
    async def get_run(run_id: str, _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
        run = (await db.execute(select(M.DetectionRun).where(M.DetectionRun.id == run_id))).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Analyse introuvable")
        return s_run(run)

    # ---- Détections ----
    async def _query_detections(db, zone_id, run_id, status, level, min_score):
        q = select(M.MiningDetection).order_by(M.MiningDetection.score.desc())
        if zone_id:
            q = q.where(M.MiningDetection.zone_id == zone_id)
        if run_id:
            q = q.where(M.MiningDetection.run_id == run_id)
        if status:
            q = q.where(M.MiningDetection.status == status)
        if level:
            q = q.where(M.MiningDetection.level == level)
        if min_score is not None:
            q = q.where(M.MiningDetection.score >= min_score)
        return (await db.execute(q)).scalars().all()

    @r.get("/detections")
    async def list_detections(
        zone_id: Optional[str] = None, run_id: Optional[str] = None,
        status: Optional[Literal["presume", "precise", "confirme", "infirme"]] = None,
        level: Optional[Literal["forte", "moyenne", "faible"]] = None,
        min_score: Optional[float] = Query(None, ge=0, le=1),
        _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session),
    ):
        return [s_detection(d) for d in await _query_detections(db, zone_id, run_id, status, level, min_score)]

    async def _get_detection(db, det_id) -> M.MiningDetection:
        d = (await db.execute(select(M.MiningDetection).where(M.MiningDetection.id == det_id))).scalar_one_or_none()
        if not d:
            raise HTTPException(status_code=404, detail="Détection introuvable")
        return d

    @r.patch("/detections/{det_id}/status")
    async def update_status(det_id: str, data: DetectionStatusUpdate, user: dict = Depends(get_current_user),
                            db: AsyncSession = Depends(get_session)):
        d = await _get_detection(db, det_id)
        d.status = data.status
        d.history = (d.history or []) + [{"status": data.status, "at": _now_iso(), "by": user["full_name"],
                                          "note": data.note or ""}]
        await db.commit()
        await db.refresh(d)
        return s_detection(d)

    async def _nearest_forest(db, lat, lng) -> M.Forest:
        forests = (await db.execute(select(M.Forest))).scalars().all()
        if not forests:
            raise HTTPException(status_code=400, detail="Aucune forêt classée enregistrée pour rattacher l'alerte")
        return min(forests, key=lambda f: core.haversine_m(lat, lng, f.center_lat, f.center_lng))

    @r.post("/detections/{det_id}/alert")
    async def detection_to_alert(det_id: str, user: dict = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_session)):
        d = await _get_detection(db, det_id)
        if d.alert_id:
            raise HTTPException(status_code=409, detail="Une alerte existe déjà pour cette détection")
        forest = await _nearest_forest(db, d.lat, d.lng)
        at = _now_iso()
        alert = M.Alert(
            forest_id=forest.id, alert_type="orpaillage", severity=LEVEL_TO_SEVERITY.get(d.level, "moyenne"),
            lat=d.lat, lng=d.lng, area_ha=d.area_ha, source="satellite", status="detectee",
            description=(f"Zone susceptible d'orpaillage {d.code} (score {d.score}, {d.area_ha} ha). "
                         f"Rattachée à la forêt classée la plus proche : {forest.name}."),
            history=[{"status": "detectee", "at": at, "by": user["full_name"], "note": f"Créée depuis la détection {d.code}"}],
            created_by=user["id"],
        )
        db.add(alert)
        await db.flush()
        d.alert_id = alert.id
        d.history = (d.history or []) + [{"status": d.status, "at": at, "by": user["full_name"], "note": "Alerte créée"}]
        await db.commit()
        return {"alert_id": alert.id, "detection": s_detection(d)}

    @r.post("/detections/{det_id}/drone-mission")
    async def detection_to_mission(det_id: str, data: DetectionMissionCreate, user: dict = Depends(get_current_user),
                                   db: AsyncSession = Depends(get_session)):
        d = await _get_detection(db, det_id)
        forest = await _nearest_forest(db, d.lat, d.lng)
        planned = datetime(data.planned_date.year, data.planned_date.month, data.planned_date.day, 8, tzinfo=timezone.utc)
        m = M.DroneMission(
            forest_id=forest.id, alert_id=d.alert_id, pilot_id=data.pilot_id, planned_date=planned,
            target_lat=d.lat, target_lng=d.lng, radius_m=data.radius_m,
            purpose=f"Survol de la zone suspecte d'orpaillage {d.code} ({d.area_ha} ha)",
            status="planifiee", created_by=user["id"],
        )
        db.add(m)
        await db.flush()
        d.mission_id = m.id
        d.history = (d.history or []) + [{"status": d.status, "at": _now_iso(), "by": user["full_name"],
                                          "note": f"Mission drone planifiée le {data.planned_date.isoformat()}"}]
        await db.commit()
        return {"mission_id": m.id, "detection": s_detection(d)}

    # ---- Exports ----
    @r.get("/export")
    async def export(
        format: Literal["geojson", "kml", "csv", "gpx"] = "geojson",
        zone_id: Optional[str] = None, run_id: Optional[str] = None,
        status: Optional[Literal["presume", "precise", "confirme", "infirme"]] = None,
        level: Optional[Literal["forte", "moyenne", "faible"]] = None,
        min_score: Optional[float] = Query(None, ge=0, le=1),
        _u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session),
    ):
        dets = [s_detection(d) for d in await _query_detections(db, zone_id, run_id, status, level, min_score)]
        zone_name = "toutes-zones"
        if zone_id:
            z = (await db.execute(select(M.SurveillanceZone).where(M.SurveillanceZone.id == zone_id))).scalar_one_or_none()
            if z:
                zone_name = z.name
        title = f"Zones suspectes d'orpaillage - {zone_name}"
        slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", zone_name).encode("ascii", "ignore").decode().lower()).strip("-")
        fname = f"orpaillage_{slug}_{date.today().isoformat()}"
        if format == "geojson":
            import json
            body, media = json.dumps(core.to_geojson(dets), ensure_ascii=False), "application/geo+json"
        elif format == "kml":
            body, media = core.to_kml(dets, title), "application/vnd.google-earth.kml+xml"
        elif format == "gpx":
            body, media = core.to_gpx(dets, title), "application/gpx+xml"
        else:
            body, media = "﻿" + core.to_csv(dets), "text/csv; charset=utf-8"
        return Response(content=body, media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="{fname}.{format}"'})

    # ---- Sites connus ----
    @r.get("/known-sites")
    async def list_sites(_u: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
        return [s_site(s) for s in (await db.execute(select(M.KnownMiningSite).order_by(M.KnownMiningSite.name))).scalars().all()]

    @r.post("/known-sites/import")
    async def import_sites(file: UploadFile = File(...), _u: dict = Depends(analyst),
                           db: AsyncSession = Depends(get_session)):
        content = await file.read()
        if len(content) > 5_000_000:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux (5 Mo maximum)")
        try:
            sites, errors = core.parse_known_sites(file.filename or "sites.csv", content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Fichier illisible : {e}")
        for s in sites:
            db.add(M.KnownMiningSite(**s))
        await db.commit()
        return {"imported": len(sites), "errors": errors[:50]}

    @r.delete("/known-sites/{site_id}")
    async def delete_site(site_id: str, _u: dict = Depends(analyst), db: AsyncSession = Depends(get_session)):
        s = (await db.execute(select(M.KnownMiningSite).where(M.KnownMiningSite.id == site_id))).scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="Site introuvable")
        await db.delete(s)
        await db.commit()
        return {"ok": True}

    # ---- Statistiques ----
    @r.get("/stats")
    async def stats(zone_id: Optional[str] = None, _u: dict = Depends(get_current_user),
                    db: AsyncSession = Depends(get_session)):
        q = select(M.MiningDetection.status, M.MiningDetection.level, func.count(), func.sum(M.MiningDetection.area_ha))
        if zone_id:
            q = q.where(M.MiningDetection.zone_id == zone_id)
        rows = (await db.execute(q.group_by(M.MiningDetection.status, M.MiningDetection.level))).all()
        by_status = {s: 0 for s in DETECTION_STATUSES}
        by_level = {"forte": 0, "moyenne": 0, "faible": 0}
        total = 0
        area = 0.0
        area_confirmed = 0.0
        for st, lv, n, a in rows:
            by_status[st] = by_status.get(st, 0) + n
            by_level[lv] = by_level.get(lv, 0) + n
            total += n
            area += a or 0
            if st == "confirme":
                area_confirmed += a or 0
        checked = by_status["confirme"] + by_status["infirme"]
        return {
            "total": total, "by_status": by_status, "by_level": by_level,
            "area_ha": round(area, 1), "area_confirmed_ha": round(area_confirmed, 1),
            "confirmation_rate": round(by_status["confirme"] / checked, 3) if checked else None,
            "known_sites": (await db.execute(select(func.count()).select_from(M.KnownMiningSite))).scalar() or 0,
        }

    return r


async def seed_zones(created_by: Optional[str] = None) -> None:
    """Crée la zone « Région du Gôh » (emprise approximative) si aucune zone n'existe."""
    async with SessionLocal() as db:
        n = (await db.execute(select(func.count()).select_from(M.SurveillanceZone))).scalar() or 0
        if n:
            return
        bb = core.GOH_APPROX_BBOX
        geom = core.bbox_polygon(bb["min_lat"], bb["min_lng"], bb["max_lat"], bb["max_lng"])
        db.add(M.SurveillanceZone(
            name="Région du Gôh", approximate=True, geometry=geom, created_by=created_by,
            description=("Emprise rectangulaire approximative des départements de Gagnoa et d'Oumé. "
                         "Remplacez-la par la limite officielle (GeoJSON) pour des résultats précis."),
            **core.bbox(geom),
        ))
        await db.commit()
