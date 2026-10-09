"""Logique métier de la détection d'orpaillage, indépendante de la base et de GEE.

Contient : géométrie simple (aire, centroïde, point dans polygone, distance),
le score de suspicion, la simulation de démonstration, l'import des sites connus
et les exports (GeoJSON, KML, CSV, GPX).
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
from typing import Iterable, Optional
from xml.sax.saxutils import escape

EARTH_RADIUS_M = 6_371_008.8

# Emprise approximative de la Région du Gôh (départements de Gagnoa et d'Oumé).
# À remplacer par la limite officielle (import GeoJSON) dès qu'elle est disponible.
GOH_APPROX_BBOX = {"min_lat": 5.55, "max_lat": 6.75, "min_lng": -6.40, "max_lng": -5.10}

# Seuils par défaut de la détection (modifiables à chaque analyse).
DEFAULT_PARAMS = {
    "dndvi_min": 0.20,      # perte de végétation minimale (NDVI référence - NDVI récent)
    "bsi_min": 0.05,        # indice de sol nu minimal sur l'image récente
    "min_area_ha": 0.5,     # surface minimale d'une zone suspecte
    "max_cloud": 60,        # % de nuages maximal par scène (les nuages restants sont masqués pixel par pixel)
    "water_buffer_m": 1000, # au-delà, la proximité d'un cours d'eau n'apporte plus de points
    "known_site_radius_m": 300,  # distance pour rattacher une détection à un site connu
}

LEVELS = (("forte", 0.70), ("moyenne", 0.45), ("faible", 0.0))


# -------------------- Géométrie --------------------
def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _outer_rings(geometry: dict) -> list[list[list[float]]]:
    t = geometry.get("type")
    if t == "Polygon":
        return [geometry["coordinates"][0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in geometry["coordinates"]]
    raise ValueError("La géométrie doit être un Polygon ou un MultiPolygon GeoJSON")


def _ring_area_m2(ring: list[list[float]]) -> float:
    """Aire géodésique approchée d'un anneau (lng, lat) en m²."""
    if len(ring) < 4:
        return 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        lng1, lat1 = ring[i][0], ring[i][1]
        lng2, lat2 = ring[i + 1][0], ring[i + 1][1]
        total += math.radians(lng2 - lng1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total * EARTH_RADIUS_M ** 2 / 2)


def area_ha(geometry: dict) -> float:
    t = geometry.get("type")
    if t == "Polygon":
        rings = geometry["coordinates"]
        a = _ring_area_m2(rings[0]) - sum(_ring_area_m2(r) for r in rings[1:])
    elif t == "MultiPolygon":
        a = sum(_ring_area_m2(p[0]) - sum(_ring_area_m2(r) for r in p[1:]) for p in geometry["coordinates"])
    else:
        raise ValueError("Géométrie non surfacique")
    return a / 10_000


def centroid(geometry: dict) -> tuple[float, float]:
    """Centroïde (lat, lng) pondéré par l'aire des anneaux extérieurs."""
    sx = sy = sw = 0.0
    for ring in _outer_rings(geometry):
        a = cx = cy = 0.0
        for i in range(len(ring) - 1):
            x0, y0 = ring[i][0], ring[i][1]
            x1, y1 = ring[i + 1][0], ring[i + 1][1]
            f = x0 * y1 - x1 * y0
            a += f
            cx += (x0 + x1) * f
            cy += (y0 + y1) * f
        a *= 0.5
        if abs(a) < 1e-14:  # anneau dégénéré : moyenne des sommets
            pts = ring[:-1] or ring
            gx = sum(p[0] for p in pts) / len(pts)
            gy = sum(p[1] for p in pts) / len(pts)
            w = 1e-14
        else:
            gx, gy, w = cx / (6 * a), cy / (6 * a), abs(a)
        sx += gx * w
        sy += gy * w
        sw += w
    return (sy / sw, sx / sw)


def bbox(geometry: dict) -> dict:
    pts = [p for ring in _outer_rings(geometry) for p in ring]
    return {
        "min_lng": min(p[0] for p in pts), "max_lng": max(p[0] for p in pts),
        "min_lat": min(p[1] for p in pts), "max_lat": max(p[1] for p in pts),
    }


def bbox_polygon(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> dict:
    if min_lat >= max_lat or min_lng >= max_lng:
        raise ValueError("Emprise invalide : les minimums doivent être inférieurs aux maximums")
    return {"type": "Polygon", "coordinates": [[
        [min_lng, min_lat], [max_lng, min_lat], [max_lng, max_lat], [min_lng, max_lat], [min_lng, min_lat],
    ]]}


def point_in_geometry(lat: float, lng: float, geometry: dict) -> bool:
    def in_ring(ring):
        inside = False
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi:
                inside = not inside
            j = i
        return inside

    t = geometry.get("type")
    polys = [geometry["coordinates"]] if t == "Polygon" else geometry["coordinates"]
    for poly in polys:
        if in_ring(poly[0]) and not any(in_ring(h) for h in poly[1:]):
            return True
    return False


def normalize_zone_geometry(geojson: dict) -> dict:
    """Accepte Polygon, MultiPolygon, Feature ou FeatureCollection et renvoie une géométrie."""
    t = geojson.get("type")
    if t == "FeatureCollection":
        geoms = [f.get("geometry") for f in geojson.get("features", []) if f.get("geometry")]
        polys = []
        for g in geoms:
            if g["type"] == "Polygon":
                polys.append(g["coordinates"])
            elif g["type"] == "MultiPolygon":
                polys.extend(g["coordinates"])
        if not polys:
            raise ValueError("Aucun polygone trouvé dans le fichier GeoJSON")
        geom = polys[0] if len(polys) == 1 else None
        return {"type": "Polygon", "coordinates": geom} if geom else {"type": "MultiPolygon", "coordinates": polys}
    if t == "Feature":
        return normalize_zone_geometry(geojson["geometry"])
    if t in ("Polygon", "MultiPolygon"):
        _outer_rings(geojson)
        return {"type": t, "coordinates": geojson["coordinates"]}
    raise ValueError("Format GeoJSON non reconnu (Polygon, MultiPolygon, Feature ou FeatureCollection attendu)")


# -------------------- Score de suspicion --------------------
def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def suspicion_score(
    dndvi: float, bsi: float, ndti: Optional[float], dist_water_m: Optional[float],
    area: float, water_buffer_m: float = 1000, near_known_site: bool = False,
) -> float:
    """Combine les indicateurs en un score 0-1.

    - perte de végétation (dNDVI)            35 %
    - sol nu sur l'image récente (BSI)       25 %
    - eau turbide / bassins (NDTI)           10 %
    - proximité d'un cours d'eau             20 %
    - surface de la zone                     10 %
    Un site connu à proximité ajoute 0,10 (plafonné à 1).
    """
    s_veg = _clip01(dndvi / 0.5)
    s_bare = _clip01((bsi + 0.05) / 0.35)
    s_turb = _clip01((ndti or 0) / 0.2)
    if dist_water_m is None:
        s_water = 0.3
    else:
        s_water = _clip01(1 - max(0.0, dist_water_m - 100) / max(1.0, water_buffer_m - 100))
    s_area = _clip01(area / 5.0)
    score = 0.35 * s_veg + 0.25 * s_bare + 0.10 * s_turb + 0.20 * s_water + 0.10 * s_area
    if near_known_site:
        score += 0.10
    return round(_clip01(score), 3)


def score_level(score: float) -> str:
    for name, threshold in LEVELS:
        if score >= threshold:
            return name
    return "faible"


def nearest_known_site(lat: float, lng: float, sites: Iterable) -> tuple[Optional[object], Optional[float]]:
    best, best_d = None, None
    for s in sites:
        d = haversine_m(lat, lng, s.lat, s.lng)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


# -------------------- Simulation (sans compte GEE) --------------------
def _blob(lat: float, lng: float, radius_m: float, rng: random.Random, n: int = 9) -> dict:
    dlat = radius_m / 111_320
    dlng = radius_m / (111_320 * math.cos(math.radians(lat)))
    ring = []
    for k in range(n):
        ang = 2 * math.pi * k / n
        r = rng.uniform(0.6, 1.15)
        ring.append([round(lng + dlng * r * math.cos(ang), 6), round(lat + dlat * r * math.sin(ang), 6)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def simulate_detections(zone_geometry: dict, seed: str, params: dict) -> list[dict]:
    """Génère des détections FICTIVES pour démontrer l'outil sans compte GEE.

    Les zones suivent des « cours d'eau » imaginaires traversant l'emprise,
    comme le ferait de l'orpaillage alluvionnaire. Elles ne correspondent à
    aucune observation réelle.
    """
    rng = random.Random(seed)
    bb = bbox(zone_geometry)
    span_lat = bb["max_lat"] - bb["min_lat"]
    span_lng = bb["max_lng"] - bb["min_lng"]
    zone_area = area_ha(zone_geometry)
    n_target = max(6, min(60, int(zone_area / 4000)))
    rivers = []
    for _ in range(3):
        a = (bb["min_lat"] + rng.random() * span_lat, bb["min_lng"])
        b = (bb["min_lat"] + rng.random() * span_lat, bb["max_lng"])
        rivers.append((a, b))
    out = []
    tries = 0
    while len(out) < n_target and tries < n_target * 30:
        tries += 1
        (la1, lo1), (la2, lo2) = rng.choice(rivers)
        t = rng.random()
        lat = la1 + (la2 - la1) * t + rng.gauss(0, span_lat * 0.01)
        lng = lo1 + (lo2 - lo1) * t + rng.gauss(0, span_lng * 0.004)
        if not point_in_geometry(lat, lng, zone_geometry):
            continue
        radius = rng.choice([40, 60, 80, 120, 160])
        geom = _blob(lat, lng, radius, rng)
        a = area_ha(geom)
        if a < params.get("min_area_ha", 0.5):
            continue
        dist_water = abs(rng.gauss(0, 220))
        out.append({
            "geometry": geom,
            "area_ha": round(a, 2),
            "indices": {
                "dndvi": round(rng.uniform(params.get("dndvi_min", 0.2), 0.55), 3),
                "bsi": round(rng.uniform(params.get("bsi_min", 0.05), 0.30), 3),
                "mndwi": round(rng.uniform(-0.25, 0.25), 3),
                "ndti": round(rng.uniform(-0.05, 0.20), 3),
                "dist_water_m": round(dist_water, 0),
            },
        })
    return out


# -------------------- Import des sites connus --------------------
_LAT_KEYS = ("lat", "latitude", "y", "lat_dd", "coord_y", "coordonnee_y")
_LNG_KEYS = ("lng", "lon", "long", "longitude", "x", "lng_dd", "coord_x", "coordonnee_x")
_NAME_KEYS = ("nom", "name", "site", "nom_site", "libelle", "code")
_LOC_KEYS = ("localite", "localité", "village", "foret", "forêt", "zone", "locality")
_STATUS_KEYS = ("statut", "status", "etat", "état")


def _pick(row: dict, keys) -> Optional[str]:
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for k in keys:
        if k in low and str(low[k]).strip() != "":
            return str(low[k]).strip()
    return None


def _num(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v.replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def parse_known_sites(filename: str, content: bytes) -> tuple[list[dict], list[str]]:
    """Lit un CSV (séparateur , ou ;) ou un GeoJSON de points. Renvoie (sites, erreurs)."""
    text = content.decode("utf-8-sig", errors="replace")
    sites, errors = [], []
    if filename.lower().endswith((".geojson", ".json")):
        data = json.loads(text)
        feats = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
        for i, f in enumerate(feats, 1):
            g = f.get("geometry") or {}
            if g.get("type") != "Point":
                errors.append(f"Entité {i} ignorée : géométrie {g.get('type')} (Point attendu)")
                continue
            lng, lat = g["coordinates"][:2]
            props = f.get("properties") or {}
            sites.append({
                "name": _pick(props, _NAME_KEYS) or f"Site {i}", "lat": lat, "lng": lng,
                "locality": _pick(props, _LOC_KEYS) or "", "status": _pick(props, _STATUS_KEYS) or "actif",
            })
    else:
        sample = text[:2048]
        delim = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        for i, row in enumerate(reader, 2):
            lat, lng = _num(_pick(row, _LAT_KEYS)), _num(_pick(row, _LNG_KEYS))
            if lat is None or lng is None:
                errors.append(f"Ligne {i} ignorée : latitude/longitude manquantes ou illisibles")
                continue
            sites.append({
                "name": _pick(row, _NAME_KEYS) or f"Site ligne {i}", "lat": lat, "lng": lng,
                "locality": _pick(row, _LOC_KEYS) or "", "status": _pick(row, _STATUS_KEYS) or "actif",
            })
    valid = []
    for s in sites:
        if not (-90 <= s["lat"] <= 90 and -180 <= s["lng"] <= 180):
            errors.append(f"{s['name']} ignoré : coordonnées hors limites (degrés décimaux WGS84 attendus)")
            continue
        valid.append(s)
    return valid, errors


# -------------------- Exports --------------------
STATUS_LABEL = {"presume": "Présumé (satellite)", "precise": "Précisé (drone)", "confirme": "Confirmé (terrain)", "infirme": "Infirmé (terrain)"}


def to_geojson(detections: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": d["geometry"],
                "properties": {k: v for k, v in d.items() if k not in ("geometry", "history")},
            }
            for d in detections
        ],
    }


def to_csv(detections: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["code", "latitude", "longitude", "surface_ha", "score", "niveau", "statut",
                "perte_ndvi", "sol_nu_bsi", "distance_eau_m", "site_connu_m"])
    for d in detections:
        ind = d.get("indices") or {}
        w.writerow([
            d["code"], f"{d['lat']:.6f}", f"{d['lng']:.6f}", d["area_ha"], d["score"], d["level"],
            STATUS_LABEL.get(d["status"], d["status"]), ind.get("dndvi", ""), ind.get("bsi", ""),
            ind.get("dist_water_m", ""), "" if d.get("known_site_distance_m") is None else round(d["known_site_distance_m"]),
        ])
    return buf.getvalue()


def to_kml(detections: list[dict], title: str) -> str:
    colors = {"forte": "ff1c1cdc", "moyenne": "ff0b9ef5", "faible": "ff16cc84"}
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f"<name>{escape(title)}</name>",
    ]
    for lvl, col in colors.items():
        parts.append(
            f'<Style id="{lvl}"><LineStyle><color>{col}</color><width>2</width></LineStyle>'
            f"<PolyStyle><color>55{col[2:]}</color></PolyStyle></Style>"
        )
    for d in detections:
        desc = (
            f"Score {d['score']} ({d['level']}) - {d['area_ha']} ha - "
            f"{STATUS_LABEL.get(d['status'], d['status'])}"
        )
        rings = _outer_rings(d["geometry"])
        polys = "".join(
            "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
            + " ".join(f"{p[0]},{p[1]},0" for p in ring)
            + "</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            for ring in rings
        )
        parts.append(
            f"<Placemark><name>{escape(d['code'])}</name><description>{escape(desc)}</description>"
            f"<styleUrl>#{d['level']}</styleUrl><MultiGeometry>"
            f"<Point><coordinates>{d['lng']},{d['lat']},0</coordinates></Point>{polys}"
            f"</MultiGeometry></Placemark>"
        )
    parts.append("</Document></kml>")
    return "".join(parts)


def to_gpx(detections: list[dict], title: str) -> str:
    """Points de passage pour GPS Garmin : un point par zone suspecte (centroïde)."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="GestPro" xmlns="http://www.topografix.com/GPX/1/1">',
        f"<metadata><name>{escape(title)}</name></metadata>",
    ]
    for d in detections:
        desc = f"Score {d['score']} - {d['area_ha']} ha - {STATUS_LABEL.get(d['status'], d['status'])}"
        parts.append(
            f'<wpt lat="{d["lat"]:.6f}" lon="{d["lng"]:.6f}"><name>{escape(d["code"])}</name>'
            f"<desc>{escape(desc)}</desc></wpt>"
        )
    parts.append("</gpx>")
    return "".join(parts)
