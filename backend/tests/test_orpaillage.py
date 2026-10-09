"""Tests du module Orpaillage.

- Tests unitaires de orpaillage_core (aucun serveur requis).
- Tests d'API : lancés seulement si ORPAILLAGE_API_URL pointe vers un backend démarré,
  par exemple ORPAILLAGE_API_URL=http://localhost:8001
"""
import os
import sys
import time
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orpaillage_core as core  # noqa: E402


# -------------------- Unitaires --------------------
def test_area_of_one_hectare_square():
    # carré d'environ 100 m x 100 m près de Gagnoa
    lat, lng = 6.13, -5.95
    dlat = 100 / 111_320
    import math
    dlng = 100 / (111_320 * math.cos(math.radians(lat)))
    geom = core.bbox_polygon(lat, lng, lat + dlat, lng + dlng)
    assert core.area_ha(geom) == pytest.approx(1.0, rel=0.01)


def test_centroid_and_point_in_polygon():
    geom = core.bbox_polygon(6.0, -6.0, 6.2, -5.8)
    lat, lng = core.centroid(geom)
    assert lat == pytest.approx(6.1)
    assert lng == pytest.approx(-5.9)
    assert core.point_in_geometry(6.1, -5.9, geom)
    assert not core.point_in_geometry(6.3, -5.9, geom)


def test_bbox_polygon_rejects_inverted_extent():
    with pytest.raises(ValueError):
        core.bbox_polygon(6.2, -6.0, 6.0, -5.8)


def test_normalize_feature_collection():
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": core.bbox_polygon(6.0, -6.0, 6.1, -5.9), "properties": {}},
        {"type": "Feature", "geometry": core.bbox_polygon(6.2, -6.0, 6.3, -5.9), "properties": {}},
    ]}
    g = core.normalize_zone_geometry(fc)
    assert g["type"] == "MultiPolygon" and len(g["coordinates"]) == 2


def test_score_orders_obvious_cases():
    strong = core.suspicion_score(dndvi=0.5, bsi=0.3, ndti=0.15, dist_water_m=50, area=4)
    weak = core.suspicion_score(dndvi=0.2, bsi=0.0, ndti=-0.05, dist_water_m=3000, area=0.5)
    assert strong > 0.8 and core.score_level(strong) == "forte"
    assert weak < 0.45 and core.score_level(weak) == "faible"
    assert core.suspicion_score(0.3, 0.1, 0.05, 400, 1, near_known_site=True) > core.suspicion_score(0.3, 0.1, 0.05, 400, 1)


def test_simulation_is_deterministic_and_inside_zone():
    zone = core.bbox_polygon(6.0, -6.1, 6.3, -5.8)
    a = core.simulate_detections(zone, "seed", core.DEFAULT_PARAMS)
    b = core.simulate_detections(zone, "seed", core.DEFAULT_PARAMS)
    assert a == b and len(a) >= 6
    for d in a:
        lat, lng = core.centroid(d["geometry"])
        assert core.point_in_geometry(lat, lng, zone)
        assert d["area_ha"] >= core.DEFAULT_PARAMS["min_area_ha"]


def test_parse_known_sites_csv_semicolon_and_comma_decimals():
    csv_text = "Nom;Latitude;Longitude;Village\nSite A;6,1234;-5,9876;Seriyo\nSite B;;-5.9;X\n".encode()
    sites, errors = core.parse_known_sites("sites.csv", csv_text)
    assert len(sites) == 1 and sites[0]["lat"] == pytest.approx(6.1234) and sites[0]["locality"] == "Seriyo"
    assert len(errors) == 1


def test_parse_known_sites_geojson():
    gj = b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[-5.9,6.1]},"properties":{"nom":"S1"}}]}'
    sites, errors = core.parse_known_sites("s.geojson", gj)
    assert sites == [{"name": "S1", "lat": 6.1, "lng": -5.9, "locality": "", "status": "actif"}] and not errors


def _sample_detection():
    geom = core.bbox_polygon(6.10, -5.95, 6.101, -5.949)
    lat, lng = core.centroid(geom)
    return {"id": "x", "code": "SER-0001", "geometry": geom, "lat": lat, "lng": lng, "area_ha": 1.2,
            "score": 0.81, "level": "forte", "status": "presume", "indices": {"dndvi": 0.4},
            "known_site_distance_m": None, "history": []}


def test_exports_are_well_formed():
    d = [_sample_detection()]
    ET.fromstring(core.to_kml(d, "Test & co"))
    ET.fromstring(core.to_gpx(d, "Test"))
    gj = core.to_geojson(d)
    assert gj["features"][0]["properties"]["code"] == "SER-0001" and "history" not in gj["features"][0]["properties"]
    csv_text = core.to_csv(d)
    assert csv_text.splitlines()[1].startswith("SER-0001;")


# -------------------- API --------------------
API_URL = os.environ.get("ORPAILLAGE_API_URL")
api = pytest.mark.skipif(not API_URL, reason="ORPAILLAGE_API_URL non défini (backend non démarré)")


@pytest.fixture(scope="module")
def http():
    import requests
    s = requests.Session()
    r = s.post(f"{API_URL}/api/auth/login", json={"email": "admin@gestpro.ci", "password": "GestPro2026!"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@api
def test_full_workflow(http):
    base = f"{API_URL}/api/orpaillage"
    zones = http.get(f"{base}/zones").json()
    assert any(z["name"] == "Région du Gôh" and z["approximate"] for z in zones)

    z = http.post(f"{base}/zones", json={"name": "Zone test Seriyo", "min_lat": 6.0, "min_lng": -6.1,
                                         "max_lat": 6.15, "max_lng": -5.95}).json()
    assert z["area_ha"] > 10000

    imp = http.post(f"{base}/known-sites/import", files={
        "file": ("sites.csv", "nom;lat;lng\nSite connu;6.07;-6.02\n".encode(), "text/csv")}).json()
    assert imp["imported"] == 1

    bad = http.post(f"{base}/runs", json={"zone_id": z["id"], "ref_start": "2026-01-01", "ref_end": "2026-03-31",
                                          "recent_start": "2026-02-01", "recent_end": "2026-09-30"})
    assert bad.status_code == 422

    run = http.post(f"{base}/runs", json={"zone_id": z["id"], "ref_start": "2025-11-01", "ref_end": "2026-02-28",
                                          "recent_start": "2026-06-01", "recent_end": "2026-09-30",
                                          "mode": "simulation"}).json()
    assert run["mode"] == "simulation"
    for _ in range(30):
        run = http.get(f"{base}/runs/{run['id']}").json()
        if run["status"] != "en_cours":
            break
        time.sleep(0.5)
    assert run["status"] == "terminee", run
    assert run["detections_count"] > 0

    dets = http.get(f"{base}/detections", params={"zone_id": z["id"]}).json()
    assert len(dets) == run["detections_count"]
    assert dets == sorted(dets, key=lambda d: -d["score"])
    assert all(d["code"].startswith("SER-") for d in dets)

    # relancer la même analyse ne doit pas dupliquer les zones déjà détectées
    run2 = http.post(f"{base}/runs", json={"zone_id": z["id"], "ref_start": "2025-11-01", "ref_end": "2026-02-28",
                                           "recent_start": "2026-06-01", "recent_end": "2026-09-30",
                                           "mode": "simulation"}).json()
    for _ in range(30):
        run2 = http.get(f"{base}/runs/{run2['id']}").json()
        if run2["status"] != "en_cours":
            break
        time.sleep(0.5)
    assert run2["detections_count"] == 0

    d = dets[0]
    upd = http.patch(f"{base}/detections/{d['id']}/status", json={"status": "precise", "note": "Survol drone"}).json()
    assert upd["status"] == "precise" and upd["history"][-1]["note"] == "Survol drone"

    al = http.post(f"{base}/detections/{d['id']}/alert").json()
    alert = [a for a in http.get(f"{API_URL}/api/alerts").json() if a["id"] == al["alert_id"]][0]
    assert alert["alert_type"] == "orpaillage"
    assert http.post(f"{base}/detections/{d['id']}/alert").status_code == 409

    mi = http.post(f"{base}/detections/{d['id']}/drone-mission", json={"planned_date": "2026-10-20"}).json()
    assert mi["detection"]["mission_id"] == mi["mission_id"]

    for fmt in ("geojson", "kml", "csv", "gpx"):
        r = http.get(f"{base}/export", params={"format": fmt, "zone_id": z["id"]})
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        if fmt in ("kml", "gpx"):
            ET.fromstring(r.content)

    st = http.get(f"{base}/stats", params={"zone_id": z["id"]}).json()
    assert st["total"] == len(dets) and st["by_status"]["precise"] == 1

    assert http.delete(f"{base}/zones/{z['id']}").json()["ok"]
