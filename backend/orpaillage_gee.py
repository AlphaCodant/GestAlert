"""Détection des zones susceptibles d'être de l'orpaillage illégal avec Google Earth Engine.

Méthode (Sentinel-2 niveau 2A, 10 m) :
1. Deux composites médians sans nuages : période de référence et période récente.
2. Indices : NDVI (végétation), BSI (sol nu), MNDWI (eau), NDTI (turbidité de l'eau).
3. Pixels candidats : forte perte de végétation (dNDVI) ET sol nu ou bassin d'eau turbide
   sur l'image récente, hors zones bâties (ESA WorldCover) et hors eau permanente (JRC).
4. Les pixels candidats contigus sont regroupés en polygones ; les plus petits que la
   surface minimale sont écartés. Chaque polygone reçoit ses indices moyens et sa
   distance au réseau hydrographique (l'orpaillage alluvionnaire longe les cours d'eau).

Identification par compte de service Google : variables d'environnement
GEE_SERVICE_ACCOUNT (adresse e-mail du compte) et GEE_PRIVATE_KEY_FILE (chemin de la
clé JSON) ; GEE_PROJECT est facultatif.
"""
from __future__ import annotations

import os
from typing import Optional

_initialized = False


def gee_configured() -> bool:
    return bool(os.environ.get("GEE_SERVICE_ACCOUNT") and os.environ.get("GEE_PRIVATE_KEY_FILE"))


def _init():
    global _initialized
    if _initialized:
        return
    import ee  # import tardif : le module reste facultatif en mode simulation

    creds = ee.ServiceAccountCredentials(os.environ["GEE_SERVICE_ACCOUNT"], os.environ["GEE_PRIVATE_KEY_FILE"])
    project = os.environ.get("GEE_PROJECT")
    ee.Initialize(creds, project=project) if project else ee.Initialize(creds)
    _initialized = True


def _composite(ee, aoi, start: str, end: str, max_cloud: float):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
    )

    def mask(img):
        scl = img.select("SCL")
        # 3 ombre, 8-10 nuages / cirrus, 11 neige
        ok = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return img.select(["B2", "B3", "B4", "B8", "B11"]).updateMask(ok).divide(10000)

    return col.map(mask).median().clip(aoi), col


def _indices(img):
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
    bsi = img.expression(
        "((S + R) - (N + B)) / ((S + R) + (N + B))",
        {"S": img.select("B11"), "R": img.select("B4"), "N": img.select("B8"), "B": img.select("B2")},
    ).rename("bsi")
    mndwi = img.normalizedDifference(["B3", "B11"]).rename("mndwi")
    ndti = img.normalizedDifference(["B4", "B3"]).rename("ndti")
    return ndvi.addBands([bsi, mndwi, ndti])


def run_gee_detection(zone_geometry: dict, ref: tuple[str, str], recent: tuple[str, str], params: dict,
                      max_features: int = 500) -> dict:
    """Lance l'analyse et renvoie {"detections": [...], "images": {...}}.

    Chaque détection : geometry (GeoJSON), area_ha et indices moyens.
    """
    _init()
    import ee

    aoi = ee.Geometry(zone_geometry)
    max_cloud = float(params.get("max_cloud", 60))
    ref_img, ref_col = _composite(ee, aoi, ref[0], ref[1], max_cloud)
    rec_img, rec_col = _composite(ee, aoi, recent[0], recent[1], max_cloud)
    n_ref, n_rec = ref_col.size().getInfo(), rec_col.size().getInfo()
    if n_ref == 0 or n_rec == 0:
        raise RuntimeError(
            f"Pas assez d'images Sentinel-2 exploitables (référence : {n_ref}, récente : {n_rec}). "
            "Élargissez les périodes ou augmentez le seuil de nuages."
        )

    i_ref = _indices(ref_img)
    i_rec = _indices(rec_img)
    dndvi = i_ref.select("ndvi").subtract(i_rec.select("ndvi")).rename("dndvi")

    veg_loss = dndvi.gte(float(params.get("dndvi_min", 0.2)))
    was_vegetated = i_ref.select("ndvi").gte(0.4)
    bare = i_rec.select("bsi").gte(float(params.get("bsi_min", 0.05)))
    turbid_pond = i_rec.select("mndwi").gt(0).And(i_rec.select("ndti").gt(0))

    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    not_built = worldcover.neq(50)
    gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    not_permanent_water = gsw.select("occurrence").unmask(0).lt(80)

    candidate = (
        veg_loss.And(was_vegetated).And(bare.Or(turbid_pond))
        .And(not_built).And(not_permanent_water)
        .selfMask()
    )
    min_px = max(1, int(round(float(params.get("min_area_ha", 0.5)) * 10000 / 100)))
    size = candidate.connectedPixelCount(maxSize=1024, eightConnected=True)
    candidate = candidate.updateMask(size.gte(min_px))

    water = gsw.select("max_extent").unmask(0).gt(0).Or(i_rec.select("mndwi").gt(0.2))
    dist_water = (
        water.fastDistanceTransform(512).sqrt()
        .multiply(ee.Image.pixelArea().sqrt()).rename("dist_water_m")
    )

    vectors = candidate.reduceToVectors(
        geometry=aoi, scale=10, crs="EPSG:32630", geometryType="polygon", eightConnected=True,
        labelProperty="label", maxPixels=1e10, tileScale=4, bestEffort=False,
    ).limit(max_features)

    stack = dndvi.addBands(i_rec.select(["bsi", "mndwi", "ndti"])).addBands(dist_water)
    stats = stack.reduceRegions(collection=vectors, reducer=ee.Reducer.mean(), scale=10, crs="EPSG:32630", tileScale=4)
    info = stats.getInfo()

    detections = []
    for f in info.get("features", []):
        p = f.get("properties", {})
        detections.append({
            "geometry": f["geometry"],
            "indices": {
                "dndvi": _round(p.get("dndvi")),
                "bsi": _round(p.get("bsi")),
                "mndwi": _round(p.get("mndwi")),
                "ndti": _round(p.get("ndti")),
                "dist_water_m": _round(p.get("dist_water_m"), 0),
            },
        })
    return {"detections": detections, "images": {"reference": n_ref, "recente": n_rec, "source": "Sentinel-2 SR (10 m)"}}


def _round(v: Optional[float], nd: int = 3) -> Optional[float]:
    return None if v is None else round(float(v), nd)
