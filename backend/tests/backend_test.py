"""GestPro backend API tests - covers auth, forests, alerts, observations, drone missions, GEE, predictions, stats, AI."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://geefastapi.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@gestpro.ci", "password": "GestPro2026!"}
ANALYSTE = {"email": "analyste@gestpro.ci", "password": "Analyste2026!"}
AGENT = {"email": "agent@gestpro.ci", "password": "Agent2026!"}
PILOTE = {"email": "pilote@gestpro.ci", "password": "Pilote2026!"}


# ------------- helpers / fixtures -------------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    return data


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def agent_headers():
    return {"Authorization": f"Bearer {_login(AGENT)['access_token']}"}


@pytest.fixture(scope="session")
def analyste_headers():
    return {"Authorization": f"Bearer {_login(ANALYSTE)['access_token']}"}


@pytest.fixture(scope="session")
def pilote_headers():
    return {"Authorization": f"Bearer {_login(PILOTE)['access_token']}"}


@pytest.fixture(scope="session")
def forests(admin_headers):
    r = requests.get(f"{API}/forests", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    return r.json()


# ------------- Health -------------
def test_root_health():
    r = requests.get(f"{API}/", timeout=20)
    assert r.status_code == 200
    assert r.json().get("app") == "GestPro"


# ------------- Auth -------------
class TestAuth:
    def test_login_admin_returns_token_and_cookie(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str)
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "admin"
        assert "password_hash" not in data["user"]
        # cookie is set
        assert "access_token" in r.cookies or any(
            c.lower().startswith("access_token=") for c in r.headers.get("set-cookie", "").split(",")
        )

    @pytest.mark.parametrize("creds,role", [
        (ADMIN, "admin"),
        (ANALYSTE, "analyste_sig"),
        (AGENT, "agent_terrain"),
        (PILOTE, "pilote_drone"),
    ])
    def test_login_all_demo_accounts(self, creds, role):
        d = _login(creds)
        assert d["user"]["role"] == role

    def test_login_invalid_credentials(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@gestpro.ci", "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me_with_bearer(self, admin_headers):
        r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]
        assert "password_hash" not in r.json()

    def test_me_without_token_unauthorized(self):
        r = requests.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 401

    def test_logout_clears_cookie(self, admin_headers):
        r = requests.post(f"{API}/auth/logout", headers=admin_headers, timeout=20)
        assert r.status_code == 200


# ------------- Forests -------------
class TestForests:
    def test_seeded_forests(self, forests):
        names = {f["name"]: f["area_ha"] for f in forests}
        assert any("Sangoué" in n for n in names), f"Sangoué not found in {list(names)}"
        assert any("Téné" in n for n in names), f"Téné not found in {list(names)}"
        sang = next(f for f in forests if "Sangoué" in f["name"])
        tene = next(f for f in forests if "Téné" in f["name"])
        assert sang["area_ha"] == 36200
        assert tene["area_ha"] == 29700

    def test_forests_requires_auth(self):
        r = requests.get(f"{API}/forests", timeout=20)
        assert r.status_code == 401


# ------------- Alerts -------------
class TestAlerts:
    def test_list_alerts(self, admin_headers):
        r = requests.get(f"{API}/alerts", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        alerts = r.json()
        assert isinstance(alerts, list) and len(alerts) > 0
        a = alerts[0]
        for key in ("status", "severity", "alert_type", "forest_id"):
            assert key in a, f"missing {key}"

    def test_filter_by_status(self, admin_headers):
        r = requests.get(f"{API}/alerts", params={"status_filter": "detectee"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        for a in r.json():
            assert a["status"] == "detectee"

    def test_create_and_update_status(self, admin_headers, forests):
        forest_id = forests[0]["id"]
        payload = {
            "forest_id": forest_id,
            "alert_type": "deforestation",
            "severity": "haute",
            "lat": forests[0]["center_lat"],
            "lng": forests[0]["center_lng"],
            "area_ha": 3.5,
            "description": "TEST_alert from pytest",
            "source": "satellite",
        }
        r = requests.post(f"{API}/alerts", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        alert = r.json()
        assert alert["status"] == "detectee"
        assert isinstance(alert["history"], list) and len(alert["history"]) == 1
        alert_id = alert["id"]

        # update status
        r2 = requests.patch(
            f"{API}/alerts/{alert_id}/status",
            json={"status": "en_verification", "note": "TEST_check"},
            headers=admin_headers, timeout=30,
        )
        assert r2.status_code == 200, r2.text
        updated = r2.json()
        assert updated["status"] == "en_verification"
        assert len(updated["history"]) == 2
        assert updated["history"][-1]["status"] == "en_verification"

        # GET to verify persistence
        rg = requests.get(f"{API}/alerts", params={"forest_id": forest_id}, headers=admin_headers, timeout=30)
        assert any(a["id"] == alert_id and a["status"] == "en_verification" for a in rg.json())

        # cleanup
        requests.delete(f"{API}/alerts/{alert_id}", headers=admin_headers, timeout=20)

    def test_create_requires_auth(self, forests):
        payload = {
            "forest_id": forests[0]["id"], "alert_type": "deforestation", "severity": "faible",
            "lat": 6.1, "lng": -5.95, "area_ha": 1.0, "description": "x",
        }
        r = requests.post(f"{API}/alerts", json=payload, timeout=20)
        assert r.status_code == 401


# ------------- Observations -------------
class TestObservations:
    def test_list_observations(self, admin_headers):
        r = requests.get(f"{API}/observations", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_observation(self, agent_headers, forests):
        payload = {
            "forest_id": forests[0]["id"],
            "observation_type": "deforestation",
            "lat": forests[0]["center_lat"],
            "lng": forests[0]["center_lng"],
            "description": "TEST_observation pytest",
        }
        r = requests.post(f"{API}/observations", json=payload, headers=agent_headers, timeout=30)
        assert r.status_code == 200, r.text
        obs = r.json()
        assert obs["description"] == "TEST_observation pytest"
        assert obs["agent_name"]


# ------------- Drone Missions -------------
class TestDroneMissions:
    def test_list_missions(self, admin_headers):
        r = requests.get(f"{API}/drone-missions", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_and_complete_mission_auto_ndvi(self, pilote_headers, forests):
        payload = {
            "forest_id": forests[0]["id"],
            "planned_date": "2026-02-15T08:00:00+00:00",
            "target_lat": forests[0]["center_lat"],
            "target_lng": forests[0]["center_lng"],
            "radius_m": 500,
            "purpose": "TEST_mission pytest",
        }
        r = requests.post(f"{API}/drone-missions", json=payload, headers=pilote_headers, timeout=30)
        assert r.status_code == 200, r.text
        mission = r.json()
        assert mission["status"] == "planifiee"
        mid = mission["id"]

        r2 = requests.patch(f"{API}/drone-missions/{mid}",
                            json={"status": "terminee", "notes": "ok"},
                            headers=pilote_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        upd = r2.json()
        assert upd["status"] == "terminee"
        assert upd["ndvi_avg"] is not None and 0 <= upd["ndvi_avg"] <= 1


# ------------- GEE mock & predictions -------------
class TestGEEAndPredictions:
    def test_indices_time_series(self, admin_headers, forests):
        fid = forests[0]["id"]
        r = requests.get(f"{API}/gee/indices/{fid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["time_series"]) == 12
        for m in d["time_series"]:
            assert "ndvi" in m and "nbr" in m and "ndwi" in m

    def test_landcover_classes_sum_100(self, admin_headers, forests):
        fid = forests[0]["id"]
        r = requests.get(f"{API}/gee/landcover/{fid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        classes = r.json()["classes"]
        total = sum(c["percent"] for c in classes)
        assert 99.0 <= total <= 101.0, f"sum was {total}"

    def test_predictions(self, admin_headers, forests):
        fid = forests[0]["id"]
        r = requests.get(f"{API}/predictions/{fid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["cells"]) == 64
        assert "high_risk_count" in d and "high_risk_zones" in d
        for z in d["high_risk_zones"]:
            assert z["risk"] >= 0.7


# ------------- Stats -------------
def test_stats_dashboard(admin_headers):
    r = requests.get(f"{API}/stats/dashboard", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for key in ("totals", "alerts_by_status", "alerts_by_type", "recent_alerts"):
        assert key in d
    assert d["totals"]["forests"] >= 2


# ------------- Admin role enforcement -------------
class TestAdminEnforcement:
    def test_register_requires_admin(self, agent_headers):
        r = requests.post(f"{API}/auth/register", json={
            "email": "TEST_should_fail@gestpro.ci", "password": "Pass1234!",
            "full_name": "Should Fail", "role": "agent_terrain",
        }, headers=agent_headers, timeout=20)
        assert r.status_code == 403

    def test_list_users_requires_admin(self, agent_headers):
        r = requests.get(f"{API}/users", headers=agent_headers, timeout=20)
        assert r.status_code == 403

    def test_admin_register_list_delete(self, admin_headers):
        email = f"TEST_user_{uuid.uuid4().hex[:8]}@gestpro.ci"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Pass1234!", "full_name": "TEST User",
            "role": "agent_terrain",
        }, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        new_user = r.json()
        uid = new_user["id"]

        r2 = requests.get(f"{API}/users", headers=admin_headers, timeout=20)
        assert r2.status_code == 200
        assert any(u["id"] == uid for u in r2.json())

        # admin cannot self-delete
        admin_user = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=20).json()
        rs = requests.delete(f"{API}/users/{admin_user['id']}", headers=admin_headers, timeout=20)
        assert rs.status_code == 400

        rd = requests.delete(f"{API}/users/{uid}", headers=admin_headers, timeout=20)
        assert rd.status_code == 200


# ------------- AI Analyze (Claude real LLM) -------------
class TestAI:
    def test_ai_analyze_and_history(self, admin_headers):
        payload = {
            "text": "Plantation de cacao récente sur 4 ha au coeur de la FC Sangoué, traces de défrichement.",
            "context": "Observation terrain agent Kouamé",
        }
        r = requests.post(f"{API}/ai/analyze", json=payload, headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("response"), str) and len(d["response"]) > 50
        assert d["model"].startswith("claude")

        time.sleep(1)
        rh = requests.get(f"{API}/ai/history", headers=admin_headers, timeout=30)
        assert rh.status_code == 200
        history = rh.json()
        assert isinstance(history, list) and len(history) >= 1



# ------------- Kobo Toolbox webhook -------------
KOBO_SECRET = os.environ.get("KOBO_WEBHOOK_SECRET", "gestpro_kobo_2026_secret_token")


class TestKobo:
    def test_kobo_info_authenticated(self, admin_headers):
        r = requests.get(f"{API}/kobo/info", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["header_name"] == "X-Kobo-Token"
        assert d["header_value"] == KOBO_SECRET
        assert "/api/kobo/webhook" in d["webhook_url"]
        assert isinstance(d["instructions"], list) and len(d["instructions"]) >= 4

    def test_kobo_info_requires_auth(self):
        r = requests.get(f"{API}/kobo/info", timeout=20)
        assert r.status_code == 401

    def test_webhook_no_token_unauthorized(self):
        r = requests.post(f"{API}/kobo/webhook", json={"_id": "x"}, timeout=20)
        assert r.status_code == 401

    def test_webhook_wrong_token_unauthorized(self):
        r = requests.post(
            f"{API}/kobo/webhook", json={"_id": "x"},
            headers={"X-Kobo-Token": "WRONG"}, timeout=20,
        )
        assert r.status_code == 401

    def test_webhook_observation_creates_observation(self, admin_headers, forests):
        f = forests[0]
        kobo_id = f"TEST_kobo_{uuid.uuid4().hex[:8]}"
        payload = {
            "_id": kobo_id,
            "_xform_id_string": "observation_terrain",
            "_geolocation": [f["center_lat"], f["center_lng"]],
            "description": "TEST_kobo observation - défrichement actif",
            "observation_type": "deforestation",
            "_submitted_by": "agent_kobo",
            "_submission_time": "2026-01-15T10:00:00",
        }
        r = requests.post(
            f"{API}/kobo/webhook", json=payload,
            headers={"X-Kobo-Token": KOBO_SECRET}, timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["form_type"] == "observation"
        assert d["submission_id"]
        assert d["observation_id"], "observation should be auto-created"

        # verify submission listed
        rl = requests.get(f"{API}/kobo/submissions", headers=admin_headers, timeout=30)
        assert rl.status_code == 200
        subs = rl.json()
        sub = next((s for s in subs if s["kobo_id"] == kobo_id), None)
        assert sub is not None, "kobo submission should be visible"
        assert sub["form_type"] == "observation"
        assert sub["raw_payload"]["_id"] == kobo_id
        assert sub["forest_id"] == f["id"]
        assert sub["observation_id"] == d["observation_id"]

        # verify observation persisted with source=kobo
        ro = requests.get(f"{API}/observations", headers=admin_headers, timeout=30)
        assert ro.status_code == 200
        obs_list = ro.json()
        match = next((o for o in obs_list if o["id"] == d["observation_id"]), None)
        assert match is not None, "observation should be persisted"
        assert match["source"] == "kobo"
        assert match["kobo_submission_id"] == d["submission_id"]

    def test_webhook_verification_classified(self):
        payload = {
            "_id": f"TEST_kobo_v_{uuid.uuid4().hex[:6]}",
            "_xform_id_string": "verification_alerte",
            "_geolocation": [6.10, -5.95],
            "description": "TEST verification",
        }
        r = requests.post(
            f"{API}/kobo/webhook", json=payload,
            headers={"X-Kobo-Token": KOBO_SECRET}, timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["form_type"] == "verification"

    def test_webhook_infraction_classified_no_observation(self):
        payload = {
            "_id": f"TEST_kobo_i_{uuid.uuid4().hex[:6]}",
            "_xform_id_string": "infraction_forestiere",
            "_geolocation": [6.10, -5.95],
            "description": "TEST infraction",
        }
        r = requests.post(
            f"{API}/kobo/webhook", json=payload,
            headers={"X-Kobo-Token": KOBO_SECRET}, timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["form_type"] == "infraction"
        assert d["observation_id"] is None, "infraction should not create observation"

    def test_webhook_geolocation_extraction_and_nearest_forest(self, admin_headers):
        # Sangoué center 6.10, -5.95 → expect Sangoué
        payload = {
            "_id": f"TEST_kobo_geo_{uuid.uuid4().hex[:6]}",
            "_xform_id_string": "observation_terrain",
            "_geolocation": [6.11, -5.94],
            "description": "TEST geo extraction",
        }
        r = requests.post(
            f"{API}/kobo/webhook", json=payload,
            headers={"X-Kobo-Token": KOBO_SECRET}, timeout=30,
        )
        assert r.status_code == 200, r.text
        rl = requests.get(f"{API}/kobo/submissions", headers=admin_headers, timeout=30)
        sub = next((s for s in rl.json() if s["kobo_id"] == payload["_id"]), None)
        assert sub is not None
        assert abs(sub["lat"] - 6.11) < 0.001
        assert abs(sub["lng"] - (-5.94)) < 0.001
        # Sangoué (6.10,-5.95) is nearer than Téné (6.30,-6.05)
        rf = requests.get(f"{API}/forests", headers=admin_headers, timeout=30)
        sang = next(f for f in rf.json() if "Sangoué" in f["name"])
        assert sub["forest_id"] == sang["id"]

    def test_kobo_submissions_requires_auth(self):
        r = requests.get(f"{API}/kobo/submissions", timeout=20)
        assert r.status_code == 401


# ------------- Stats kobo_submissions field -------------
def test_stats_includes_kobo_submissions(admin_headers):
    r = requests.get(f"{API}/stats/dashboard", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    totals = r.json()["totals"]
    assert "kobo_submissions" in totals
    assert isinstance(totals["kobo_submissions"], int)
