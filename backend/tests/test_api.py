from datetime import date, timedelta

import pytest

MED = {"name": "Aspirin", "dose": "75 mg", "times": ["08:00", "20:00"], "start_date": date.today().isoformat(),
       "instructions": "After food", "stock": 20}
APPT = {"doctor": "Dr. Who", "place": "Clinic", "starts_at": "2099-01-01T10:00", "notes": ""}


def names(client, headers):
    return [m["name"] for m in client.get("/api/medications", headers=headers).json()]


def test_permission_matrix_for_edits(client, elder, caretaker, family):
    assert client.post("/api/medications", json=MED, headers=family).status_code == 403
    assert client.post("/api/appointments", json=APPT, headers=family).status_code == 403
    assert client.post("/api/medications", json=MED, headers=caretaker).status_code == 201
    assert client.post("/api/medications", json=MED, headers=elder).status_code == 201
    assert client.post("/api/appointments", json=APPT, headers=caretaker).status_code == 201


def test_family_can_view_and_comment_only(client, family):
    assert client.get("/api/medications", headers=family).status_code == 200
    assert client.get("/api/appointments", headers=family).status_code == 200
    assert client.get("/api/activity", headers=family).status_code == 200
    assert client.post("/api/comments", json={"text": "Love you!"}, headers=family).status_code == 201
    dose = {"medication_id": 1, "scheduled_at": "2025-01-01T08:00", "action": "taken"}
    assert client.post("/api/doses", json=dose, headers=family).status_code == 403
    assert client.put("/api/settings", json={"require_approval": True}, headers=family).status_code == 403
    assert client.get("/api/contacts", headers=family).status_code == 403
    assert client.delete("/api/medications/1", headers=family).status_code == 403


def test_only_elder_manages_settings_and_approvals(client, caretaker):
    assert client.put("/api/settings", json={"require_approval": True}, headers=caretaker).status_code == 403
    assert client.post("/api/pending/1/approve", headers=caretaker).status_code == 403


def test_medication_validation(client, elder):
    bad = [
        {**MED, "times": []},
        {**MED, "times": ["25:00"]},
        {**MED, "name": ""},
        {**MED, "stock": -1},
        {**MED, "end_date": (date.today() - timedelta(days=2)).isoformat()},
        {**MED, "unexpected": "field"},
    ]
    for body in bad:
        assert client.post("/api/medications", json=body, headers=elder).status_code == 422, body


def test_medication_crud_and_activity_log(client, elder):
    med_id = client.post("/api/medications", json=MED, headers=elder).json()["id"]
    assert client.put(f"/api/medications/{med_id}", json={**MED, "dose": "100 mg"}, headers=elder).status_code == 200
    meds = {m["id"]: m for m in client.get("/api/medications", headers=elder).json()}
    assert meds[med_id]["dose"] == "100 mg" and meds[med_id]["times"] == ["08:00", "20:00"]
    assert client.delete(f"/api/medications/{med_id}", headers=elder).status_code == 200
    assert med_id not in {m["id"] for m in client.get("/api/medications", headers=elder).json()}
    assert client.delete(f"/api/medications/{med_id}", headers=elder).status_code == 404
    log = [a["detail"] for a in client.get("/api/activity", headers=elder).json()]
    assert any("Aspirin" in d for d in log)


def test_today_view_and_dose_logging(client, elder, caretaker):
    doses = client.get("/api/doses/today", headers=elder).json()["doses"]
    assert doses, "demo data should have doses today"
    d = doses[0]
    body = {"medication_id": d["medication_id"], "scheduled_at": d["scheduled_at"], "action": "taken"}
    assert client.post("/api/doses", json=body, headers=caretaker).status_code == 200
    after = {(x["medication_id"], x["scheduled_at"]): x for x in client.get("/api/doses/today", headers=elder).json()["doses"]}
    got = after[(d["medication_id"], d["scheduled_at"])]
    assert got["status"].startswith("taken") and got["logged_by"] == "caretaker"


def test_dose_logging_updates_stock_once(client, elder):
    med = client.get("/api/medications", headers=elder).json()[0]
    slot = next(d for d in client.get("/api/doses/today", headers=elder).json()["doses"] if d["medication_id"] == med["id"])
    body = {"medication_id": med["id"], "scheduled_at": slot["scheduled_at"], "action": "taken"}
    already = slot["status"].startswith("taken")
    client.post("/api/doses", json=body, headers=elder)
    client.post("/api/doses", json=body, headers=elder)  # idempotent
    stock = next(m for m in client.get("/api/medications", headers=elder).json() if m["id"] == med["id"])["stock"]
    assert stock == med["stock"] - (0 if already else 1)
    client.post("/api/doses", json={**body, "action": "skipped"}, headers=elder)
    stock = next(m for m in client.get("/api/medications", headers=elder).json() if m["id"] == med["id"])["stock"]
    assert stock == med["stock"] + (1 if already else 0)


def test_dose_logging_rejects_invalid_slots(client, elder):
    med = client.get("/api/medications", headers=elder).json()[0]
    today = date.today().isoformat()
    for slot in ["garbage", f"{today}T03:17", "2000-01-01T08:00"]:
        body = {"medication_id": med["id"], "scheduled_at": slot, "action": "taken"}
        assert client.post("/api/doses", json=body, headers=elder).status_code == 422, slot
    missing = {"medication_id": 9999, "scheduled_at": f"{today}T08:00", "action": "taken"}
    assert client.post("/api/doses", json=missing, headers=elder).status_code == 404


def test_weekly_adherence_endpoint(client, elder):
    w = client.get("/api/adherence/weekly", headers=elder).json()
    assert w["days"] == 7 and w["total"] > 0
    assert 0 <= w["percent"] <= 100
    assert set(w["counts"]) == {"taken_on_time", "taken_late", "skipped", "missed"}


def test_appointments_upcoming_and_validation(client, elder):
    appts = client.get("/api/appointments", headers=elder).json()
    assert appts and appts == sorted(appts, key=lambda a: a["starts_at"])
    assert client.post("/api/appointments", json={**APPT, "doctor": ""}, headers=elder).status_code == 422
    assert client.post("/api/appointments", json={**APPT, "starts_at": "nope"}, headers=elder).status_code == 422
    new = client.post("/api/appointments", json=APPT, headers=elder).json()["id"]
    assert client.put(f"/api/appointments/{new}", json={**APPT, "place": "New place"}, headers=elder).status_code == 200
    assert client.delete(f"/api/appointments/{new}", headers=elder).status_code == 200
    assert client.delete(f"/api/appointments/{new}", headers=elder).status_code == 404


def test_profiles_are_isolated(client, elder):
    created = client.post("/api/profiles", json={"name": "Other"}).json()
    other = client.post("/api/auth/login", json={"passcode": created["passcodes"]["elder"]}).json()
    oh = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/api/medications", headers=oh).json() == []
    demo_med = client.get("/api/medications", headers=elder).json()[0]["id"]
    assert client.put(f"/api/medications/{demo_med}", json=MED, headers=oh).status_code == 404
    assert client.delete(f"/api/medications/{demo_med}", headers=oh).status_code == 404


def test_approval_workflow(client, elder, caretaker):
    assert client.put("/api/settings", json={"require_approval": True}, headers=elder).status_code == 200
    r = client.post("/api/medications", json=MED, headers=caretaker)
    assert r.status_code == 202 and r.json()["status"] == "pending"
    assert "Aspirin" not in names(client, elder)
    pending = client.get("/api/pending", headers=elder).json()
    assert len(pending) == 1 and pending[0]["requested_by"] == "caretaker"
    assert client.get("/api/me", headers=elder).json()["pending_count"] == 1
    # The elder's own changes are never held back.
    assert client.post("/api/appointments", json=APPT, headers=elder).status_code == 201
    assert client.post(f"/api/pending/{pending[0]['id']}/approve", headers=elder).status_code == 200
    assert "Aspirin" in names(client, elder)
    assert client.get("/api/pending", headers=elder).json() == []


def test_approval_reject(client, elder, caretaker):
    client.put("/api/settings", json={"require_approval": True}, headers=elder)
    client.post("/api/medications", json=MED, headers=caretaker)
    pid = client.get("/api/pending", headers=elder).json()[0]["id"]
    assert client.post(f"/api/pending/{pid}/reject", headers=elder).status_code == 200
    assert "Aspirin" not in names(client, elder)
    assert client.post(f"/api/pending/{pid}/approve", headers=elder).status_code == 404


@pytest.mark.parametrize("path", ["/api/me", "/api/medications", "/api/appointments", "/api/doses/today",
                                  "/api/activity", "/api/outbox", "/api/pending", "/api/contacts"])
def test_every_endpoint_requires_auth(client, path):
    assert client.get(path).status_code == 401


def test_security_headers_and_cors(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    pre = client.options("/api/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in pre.headers


def test_contacts_manage_and_comments(client, elder, caretaker):
    c = {"name": "Sam", "email": "sam@example.com", "role": "family"}
    assert client.post("/api/contacts", json=c, headers=caretaker).status_code == 201
    sam = next(x for x in client.get("/api/contacts", headers=elder).json() if x["name"] == "Sam")
    assert client.delete(f"/api/contacts/{sam['id']}", headers=elder).status_code == 204
    assert client.post("/api/comments", json={"text": ""}, headers=elder).status_code == 422
