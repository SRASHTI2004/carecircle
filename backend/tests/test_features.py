import smtplib
from datetime import date

import pytest

from app import security
from app.config import get_settings
from app.services import mailer
from app.services.reminders import run_reminders

from .conftest import DEMO, auth
from .test_reminders import add_med, emails, fresh_profile, ist

ROUTINE = {"kind": "routine", "name": "Morning walk", "times": ["07:00"], "start_date": date.today().isoformat()}
MED = {"name": "Aspirin", "dose": "75 mg", "times": ["08:00"], "start_date": date.today().isoformat(), "stock": 10}


# ---------- routines ----------


def test_routine_needs_no_dose_but_medicine_does(client, elder):
    assert client.post("/api/medications", json=ROUTINE, headers=elder).status_code == 201
    assert client.post("/api/medications", json={**MED, "dose": ""}, headers=elder).status_code == 422
    kinds = {m["name"]: m["kind"] for m in client.get("/api/medications", headers=elder).json()}
    assert kinds["Morning walk"] == "routine" and kinds["Metformin"] == "medicine"


def test_routine_doses_are_tracked_without_touching_stock(client, elder):
    client.post("/api/medications", json={**ROUTINE, "times": ["00:01"]}, headers=elder)
    slot = next(d for d in client.get("/api/doses/today", headers=elder).json()["doses"] if d["name"] == "Morning walk")
    assert slot["kind"] == "routine"
    body = {"medication_id": slot["medication_id"], "scheduled_at": slot["scheduled_at"], "action": "taken"}
    assert client.post("/api/doses", json=body, headers=elder).status_code == 200


def test_routine_reminder_uses_routine_wording_and_preferences(conn):
    pid = fresh_profile(conn)
    conn.execute(
        "INSERT INTO medications (profile_id, name, dose, times, start_date, kind) VALUES (?,?,?,?,?,?)",
        (pid, "Evening walk", "", '["17:30"]', "2025-01-01", "routine"),
    )
    conn.execute("UPDATE contacts SET notify = '[\"dose_missed\"]' WHERE email = 'care@x.co'")
    run_reminders(conn, ist(2025, 3, 3, 17, 20))
    sent = emails(conn, pid, "Routine reminder")
    assert [a for a, _ in sent] == ["elder@x.co"]  # caretaker opted out of routine emails
    run_reminders(conn, ist(2025, 3, 3, 18, 10))
    assert emails(conn, pid, "Missed routine") == [] or all(
        a != "care@x.co" for a, _ in emails(conn, pid, "Missed routine")
    )


def test_routines_never_trigger_low_stock(conn):
    pid = fresh_profile(conn)
    conn.execute(
        "INSERT INTO medications (profile_id, name, dose, times, start_date, kind, stock) VALUES (?,?,?,?,?,?,0)",
        (pid, "Walk", "", '["09:00"]', "2025-01-01", "routine"),
    )
    run_reminders(conn, ist(2025, 3, 3, 12, 0))
    assert emails(conn, pid, "Low stock") == []


# ---------- duplicate warning ----------


def test_duplicate_medicine_warns_then_allows_when_confirmed(client, elder):
    r = client.post("/api/medications", json={**MED, "name": "metformin"}, headers=elder)
    assert r.status_code == 409 and "already on the list" in r.json()["detail"]
    ok = client.post("/api/medications?allow_duplicate=true", json={**MED, "name": "metformin"}, headers=elder)
    assert ok.status_code == 201


def test_editing_a_medicine_is_not_flagged_as_its_own_duplicate(client, elder):
    med = client.get("/api/medications", headers=elder).json()[0]
    body = {
        k: med[k]
        for k in (
            "kind",
            "name",
            "dose",
            "times",
            "start_date",
            "end_date",
            "instructions",
            "stock",
            "low_stock_threshold",
        )
    }
    assert client.put(f"/api/medications/{med['id']}", json=body, headers=elder).status_code == 200


# ---------- passcode management ----------


def test_elder_rotates_a_passcode_and_old_one_stops_working(client, elder):
    old = auth(client, "family")
    r = client.post("/api/passcodes/family/rotate", headers=elder)
    new = r.json()["passcode"]
    assert r.status_code == 200 and new != DEMO["family"] and new.startswith("DEMO-")
    assert client.get("/api/me", headers=old).status_code == 401  # signed out
    assert client.post("/api/auth/login", json={"passcode": DEMO["family"]}).status_code == 401
    assert client.post("/api/auth/login", json={"passcode": new}).json()["role"] == "family"


def test_revoke_blocks_login_until_rotated(client, elder):
    assert client.delete("/api/passcodes/caretaker", headers=elder).status_code == 200
    assert client.post("/api/auth/login", json={"passcode": DEMO["caretaker"]}).status_code == 401
    states = {p["role"]: p["active"] for p in client.get("/api/passcodes", headers=elder).json()}
    assert states == {"elder": True, "caretaker": False, "family": True}
    new = client.post("/api/passcodes/caretaker/rotate", headers=elder).json()["passcode"]
    assert client.post("/api/auth/login", json={"passcode": new}).status_code == 200


def test_passcode_management_permissions(client, caretaker, family):
    assert client.get("/api/passcodes", headers=family).status_code == 403
    assert client.post("/api/passcodes/family/rotate", headers=family).status_code == 403
    assert (
        client.post("/api/passcodes/family/rotate", headers=caretaker).status_code == 200
    )  # caretaker may manage family
    assert client.post("/api/passcodes/elder/rotate", headers=caretaker).status_code == 403
    assert client.delete("/api/passcodes/elder", headers=caretaker).status_code == 403
    assert client.post("/api/passcodes/stranger/rotate", headers=caretaker).status_code == 404


def test_elder_cannot_revoke_own_passcode(client, elder):
    assert client.delete("/api/passcodes/elder", headers=elder).status_code == 409


def test_session_ttl_comes_from_environment(client, monkeypatch):
    monkeypatch.setenv("SESSION_TTL", "0")
    token = client.post("/api/auth/login", json={"passcode": DEMO["elder"]}).json()["token"]
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_family_can_never_edit_anything(client, family):
    attempts = [
        ("post", "/api/medications", MED),
        ("put", "/api/medications/1", MED),
        ("delete", "/api/medications/1", None),
        ("post", "/api/appointments", {"doctor": "d", "place": "p", "starts_at": "2099-01-01T10:00"}),
        ("put", "/api/appointments/1", {"doctor": "d", "place": "p", "starts_at": "2099-01-01T10:00"}),
        ("delete", "/api/appointments/1", None),
        ("put", "/api/emergency", {}),
        ("post", "/api/checkins", {"mood": "good"}),
        ("post", "/api/settings/test-email", {"email": "a@b.co"}),
        ("post", "/api/pending/1/approve", None),
        ("post", "/api/passcodes/family/rotate", None),
        ("put", "/api/contacts/1/notify", {"notify": []}),
    ]
    for method, path, body in attempts:
        r = getattr(client, method)(path, headers=family, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (method, path, r.status_code)


# ---------- notification preferences ----------


def test_contact_preferences_update_and_filter_recipients(client, elder, conn):
    contacts = client.get("/api/contacts", headers=elder).json()
    assert all("notify" in c and "dose_missed" in c["notify"] for c in contacts)
    fam = next(c for c in contacts if c["role"] == "family")
    r = client.put(f"/api/contacts/{fam['id']}/notify", json={"notify": ["appointment"]}, headers=elder)
    assert r.json()["notify"] == ["appointment"]
    from app.services.reminders import recipients

    pid = conn.execute("SELECT id FROM profiles WHERE code = 'DEMO'").fetchone()["id"]
    assert fam["email"] not in recipients(conn, pid, ("family",), "dose_missed")
    assert fam["email"] in recipients(conn, pid, ("family",), "appointment")
    assert client.put("/api/contacts/99999/notify", json={"notify": []}, headers=elder).status_code == 404
    assert client.put(f"/api/contacts/{fam['id']}/notify", json={"notify": ["bogus"]}, headers=elder).status_code == 422


# ---------- email content, retries, test button ----------


def test_email_has_html_and_text_with_name_and_link(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    run_reminders(conn, ist(2025, 3, 3, 7, 50))
    row = conn.execute("SELECT * FROM outbox WHERE profile_id = ? AND subject LIKE 'Dose reminder%'", (pid,)).fetchone()
    assert "Test Elder" in row["body"] and get_settings().app_url in row["body"]
    assert row["html"].startswith("<!doctype html>") and "font-size:20px" in row["html"] and 'lang="en"' in row["html"]


def test_html_escapes_untrusted_text():
    _, page = mailer.render_email("<b>Evil</b>", "<script>x</script>", "a & b")
    assert "<script>" not in page and "&lt;script&gt;" in page and "a &amp; b" in page


class FakeSMTP:
    fail = 0
    sent: list = []
    calls: list = []

    def __init__(self, host, port, timeout=0):
        FakeSMTP.calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        FakeSMTP.calls.append(("starttls",))

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user))

    def send_message(self, msg):
        if FakeSMTP.fail > 0:
            FakeSMTP.fail -= 1
            raise smtplib.SMTPServerDisconnected("down")
        FakeSMTP.sent.append(msg)


@pytest.fixture()
def smtp(monkeypatch):
    FakeSMTP.fail, FakeSMTP.sent, FakeSMTP.calls = 0, [], []
    for k, v in {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "u@gmail.com",
        "SMTP_PASSWORD": "app-pass",
        "FROM_EMAIL": "u@gmail.com",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer, "_sleep", lambda s: None)
    return FakeSMTP


def test_gmail_style_starttls_login_and_multipart(conn, smtp):
    pid = fresh_profile(conn)
    assert mailer.send_email(conn, pid, "x@y.co", "Hi", "plain", "<p>html</p>") is True
    assert ("starttls",) in smtp.calls and ("login", "u@gmail.com") in smtp.calls
    msg = smtp.sent[0]
    assert msg.is_multipart() and {p.get_content_type() for p in msg.iter_parts()} == {"text/plain", "text/html"}
    row = conn.execute("SELECT delivered, attempts FROM outbox").fetchone()
    assert row["delivered"] == 1 and row["attempts"] == 1


def test_inline_retry_with_backoff_then_success(conn, smtp):
    pid = fresh_profile(conn)
    smtp.fail = 1
    sleeps: list[float] = []
    mailer._sleep = sleeps.append
    assert mailer.send_email(conn, pid, "x@y.co", "Hi", "plain") is True
    assert sleeps == [mailer.INLINE_BACKOFF_SECONDS]
    assert conn.execute("SELECT attempts FROM outbox").fetchone()["attempts"] == 2


def test_failure_never_raises_and_is_retried_later(conn, smtp):
    from datetime import datetime, timedelta

    pid = fresh_profile(conn)
    smtp.fail = 99
    assert mailer.send_email(conn, pid, "x@y.co", "Hi", "plain") is False
    row = conn.execute("SELECT * FROM outbox").fetchone()
    assert row["delivered"] == 0 and row["error"] == "SMTPServerDisconnected" and row["attempts"] == 2
    assert mailer.retry_failed(conn) == 0  # too soon: backing off
    smtp.fail = 0
    later = datetime.fromisoformat(row["last_attempt_at"]) + timedelta(minutes=11)
    assert mailer.retry_failed(conn, later) == 1
    assert conn.execute("SELECT delivered FROM outbox").fetchone()["delivered"] == 1


def test_retry_gives_up_after_max_attempts(conn, smtp):
    from datetime import datetime, timedelta

    pid = fresh_profile(conn)
    smtp.fail = 99
    mailer.send_email(conn, pid, "x@y.co", "Hi", "plain")
    t = datetime.fromisoformat(conn.execute("SELECT last_attempt_at FROM outbox").fetchone()[0])
    for i in range(1, 8):
        mailer.retry_failed(conn, t + timedelta(minutes=30 * i))
    assert conn.execute("SELECT attempts FROM outbox").fetchone()["attempts"] <= mailer.MAX_ATTEMPTS


def test_test_email_endpoint_demo_mode(client, elder):
    r = client.post("/api/settings/test-email", json={"email": "judge@gmail.com"}, headers=elder).json()
    assert r["delivered"] is False and r["smtp_configured"] is False and "demo outbox" in r["message"]
    box = client.get("/api/outbox", headers=elder).json()["emails"]
    assert box[0]["subject"] == "CareCircle test email" and box[0]["to_email"] == "judge@gmail.com"


def test_test_email_endpoint_real_and_validated_and_limited(client, elder, caretaker, smtp):
    r = client.post("/api/settings/test-email", json={"email": "judge@gmail.com"}, headers=caretaker).json()
    assert r["delivered"] is True and "judge@gmail.com" in r["message"]
    assert client.post("/api/settings/test-email", json={"email": "nope"}, headers=elder).status_code == 422
    for _ in range(4):
        client.post("/api/settings/test-email", json={"email": "judge@gmail.com"}, headers=elder)
    assert client.post("/api/settings/test-email", json={"email": "judge@gmail.com"}, headers=elder).status_code == 429


def test_failed_delivery_does_not_crash_reminder_run(conn, smtp):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    smtp.fail = 99
    totals = run_reminders(conn, ist(2025, 3, 3, 7, 55))
    assert totals["doses"] == 2
    assert emails(conn, pid, "Dose reminder")  # recorded in the outbox despite SMTP being down


# ---------- emergency card ----------


def test_emergency_card_autofills_medicines_and_is_elder_edited(client, elder, caretaker, family):
    card = client.get("/api/emergency", headers=family).json()
    assert card["blood_group"] == "B+" and card["can_edit"] is False
    assert {"Metformin", "Amlodipine"} <= {m["name"] for m in card["medicines"]}
    assert "Blood pressure check" not in [m["name"] for m in card["medicines"]]  # routines are not medicines
    assert any(c["role"] == "caretaker" for c in card["contacts"])
    body = {
        "blood_group": "O-",
        "allergies": "Nuts",
        "conditions": "Asthma",
        "doctor_name": "Dr. X",
        "doctor_phone": "123",
        "emergency_contacts": "Son 999",
        "notes": "n",
    }
    assert client.put("/api/emergency", json=body, headers=caretaker).status_code == 403
    assert client.put("/api/emergency", json=body, headers=family).status_code == 403
    assert client.put("/api/emergency", json=body, headers=elder).status_code == 200
    got = client.get("/api/emergency", headers=caretaker).json()
    assert got["blood_group"] == "O-" and got["allergies"] == "Nuts" and got["can_edit"] is False
    assert client.get("/api/emergency", headers=elder).json()["can_edit"] is True
    assert client.put("/api/emergency", json={**body, "notes": "x" * 501}, headers=elder).status_code == 422
    assert any("emergency" in a["detail"] for a in client.get("/api/activity", headers=elder).json())


def test_emergency_card_for_new_profile_is_empty(client):
    created = client.post("/api/profiles", json={"name": "New Elder"}).json()
    h = {
        "Authorization": "Bearer "
        + client.post("/api/auth/login", json={"passcode": created["passcodes"]["family"]}).json()["token"]
    }
    card = client.get("/api/emergency", headers=h).json()
    assert card["blood_group"] == "" and card["medicines"] == [] and card["name"] == "New Elder"


# ---------- wellbeing check-ins ----------


def test_checkin_roles_and_listing(client, elder, caretaker, family):
    assert client.post("/api/checkins", json={"mood": "good", "note": "Slept well"}, headers=elder).status_code == 201
    assert client.post("/api/checkins", json={"mood": "okay"}, headers=caretaker).status_code == 201
    assert client.post("/api/checkins", json={"mood": "great"}, headers=elder).status_code == 422
    listing = client.get("/api/checkins", headers=family).json()
    assert (
        listing[0]["mood"] == "okay" and listing[0]["logged_by"] == "caretaker" and listing[1]["note"] == "Slept well"
    )


def test_repeated_unwell_alerts_caretakers_only_once_per_checkin(client, elder, conn):
    first = client.post("/api/checkins", json={"mood": "unwell"}, headers=elder).json()
    assert first["alerted"] == 0
    second = client.post("/api/checkins", json={"mood": "unwell", "note": "dizzy"}, headers=elder).json()
    assert second["alerted"] == 1
    rows = conn.execute("SELECT to_email, body FROM outbox WHERE subject LIKE 'Please check in%'").fetchall()
    assert [r["to_email"] for r in rows] == ["caretaker@example.com"] and "dizzy" in rows[0]["body"]


def test_good_checkin_after_unwell_does_not_alert(client, elder):
    client.post("/api/checkins", json={"mood": "unwell"}, headers=elder)
    assert client.post("/api/checkins", json={"mood": "good"}, headers=elder).json()["alerted"] == 0
    assert client.post("/api/checkins", json={"mood": "unwell"}, headers=elder).json()["alerted"] == 0


# ---------- adherence detail, pagination, errors, headers ----------


def test_weekly_trend_and_per_medicine(client, elder):
    w = client.get("/api/adherence/weekly", headers=elder).json()
    assert len(w["daily"]) == 7 and w["daily"][-1]["date"] == date.today().isoformat()
    assert all(d["percent"] is None or 0 <= d["percent"] <= 100 for d in w["daily"])
    names = {m["name"] for m in w["by_medicine"]}
    assert {"Metformin", "Evening walk"} <= names
    assert all({"name", "percent", "total", "missed"} <= set(m) for m in w["by_medicine"])


def test_pagination(client, elder):
    full = client.get("/api/activity?limit=100", headers=elder).json()
    page = client.get("/api/activity?limit=2&offset=1", headers=elder).json()
    assert page == full[1:3]
    assert client.get("/api/activity?limit=0", headers=elder).status_code == 422
    assert client.get("/api/activity?limit=1000", headers=elder).status_code == 422
    assert len(client.get("/api/outbox?limit=1", headers=elder).json()["emails"]) <= 1


def test_validation_errors_are_one_readable_string(client, elder):
    r = client.post("/api/medications", json={"name": "", "times": ["99:99"], "start_date": "x"}, headers=elder)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and "name" in r.json()["detail"]


def test_extra_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_ai_endpoint_is_rate_limited(client, elder):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    codes = [
        client.post("/api/ai/prescription", files={"file": ("a.png", png, "image/png")}, headers=elder).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [200] * 10 and codes[10] == 429
    security.ai_limiter.reset(str(1))


def test_weekly_summary_is_cached(client, family, monkeypatch):
    import httpx

    calls = []

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"summary": "Great week."}'}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or R())
    for _ in range(3):
        assert client.get("/api/ai/weekly-summary", headers=family).json()["summary"] == "Great week."
    assert len(calls) == 1


def test_demo_addresses_are_never_sent_to_a_real_server(conn, smtp):
    pid = fresh_profile(conn)
    assert mailer.is_demo_address("a@example.com") and mailer.is_demo_address("a@x.invalid")
    assert not mailer.is_demo_address("someone@gmail.com")
    assert mailer.send_email(conn, pid, "caretaker@example.com", "Hi", "plain") is False
    assert smtp.calls == [] and conn.execute("SELECT delivered, error FROM outbox").fetchone()["error"] == ""
    assert mailer.send_email(conn, pid, "real@gmail.com", "Hi", "plain") is True


def test_undo_clears_a_dose_and_restores_stock(client, elder):
    med = next(m for m in client.get("/api/medications", headers=elder).json() if m["kind"] == "medicine")
    slot = next(
        d for d in client.get("/api/doses/today", headers=elder).json()["doses"] if d["medication_id"] == med["id"]
    )
    body = {"medication_id": med["id"], "scheduled_at": slot["scheduled_at"]}
    client.post("/api/doses", json={**body, "action": "taken"}, headers=elder)
    taken = next(
        d
        for d in client.get("/api/doses/today", headers=elder).json()["doses"]
        if d["scheduled_at"] == slot["scheduled_at"] and d["medication_id"] == med["id"]
    )
    assert taken["status"].startswith("taken") and taken["logged_at"] and taken["logged_by"] == "elder"
    stock_taken = next(m for m in client.get("/api/medications", headers=elder).json() if m["id"] == med["id"])["stock"]
    assert client.post("/api/doses", json={**body, "action": "undo"}, headers=elder).status_code == 200
    after = next(
        d
        for d in client.get("/api/doses/today", headers=elder).json()["doses"]
        if d["scheduled_at"] == slot["scheduled_at"] and d["medication_id"] == med["id"]
    )
    assert after["status"] in ("upcoming", "due", "missed") and after["logged_at"] is None
    assert (
        next(m for m in client.get("/api/medications", headers=elder).json() if m["id"] == med["id"])["stock"]
        == stock_taken + 1
    )
    assert client.post("/api/doses", json={**body, "action": "undo"}, headers=elder).status_code == 409


def test_family_cannot_undo(client, family):
    body = {"medication_id": 1, "scheduled_at": "2025-01-01T08:00", "action": "undo"}
    assert client.post("/api/doses", json=body, headers=family).status_code == 403
