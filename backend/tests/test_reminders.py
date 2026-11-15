from datetime import UTC, datetime, timedelta

from app.schemas import ContactIn
from app.services.profiles import create_profile
from app.services.reminders import run_reminders


def ist(y, mo, d, h, mi):
    """UTC instant for a wall-clock time in Asia/Kolkata (UTC+5:30)."""
    return (datetime(y, mo, d, h, mi) - timedelta(hours=5, minutes=30)).replace(tzinfo=UTC)


def fresh_profile(conn, tz="Asia/Kolkata"):
    contacts = [ContactIn(name="E", email="elder@x.co", role="elder"), ContactIn(name="C", email="care@x.co", role="caretaker"),
                ContactIn(name="F", email="fam@x.co", role="family")]
    pid, _ = create_profile(conn, "Test Elder", tz, contacts)
    return pid


def add_med(conn, pid, name="Pill", times='["08:00"]', stock=50):
    return conn.execute(
        "INSERT INTO medications (profile_id, name, dose, times, start_date, stock, low_stock_threshold) VALUES (?,?,?,?,?,?,5)",
        (pid, name, "1 tab", times, "2025-01-01", stock),
    ).lastrowid


def emails(conn, pid, prefix=""):
    rows = conn.execute("SELECT to_email, subject FROM outbox WHERE profile_id = ? ORDER BY id", (pid,))
    return [(r["to_email"], r["subject"]) for r in rows if r["subject"].startswith(prefix)]


def test_upcoming_dose_goes_to_elder_and_caretaker_once(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    now = ist(2025, 3, 3, 7, 50)
    run_reminders(conn, now)
    run_reminders(conn, now + timedelta(minutes=1))  # idempotent
    assert sorted(a for a, _ in emails(conn, pid, "Dose reminder")) == ["care@x.co", "elder@x.co"]


def test_no_upcoming_reminder_too_early(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    run_reminders(conn, ist(2025, 3, 3, 7, 0))
    assert emails(conn, pid, "Dose reminder") == []


def test_missed_dose_after_30_minutes_notifies_caretaker_and_family(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    run_reminders(conn, ist(2025, 3, 3, 8, 30))  # exactly 30 min: still within grace
    assert emails(conn, pid, "Missed") == []
    run_reminders(conn, ist(2025, 3, 3, 8, 31))
    run_reminders(conn, ist(2025, 3, 3, 9, 15))  # no duplicate
    assert sorted(a for a, _ in emails(conn, pid, "Missed")) == ["care@x.co", "fam@x.co"]


def test_taken_dose_is_not_reported_missed(conn):
    pid = fresh_profile(conn)
    mid = add_med(conn, pid)
    conn.execute("INSERT INTO dose_logs (medication_id, scheduled_at, status, logged_at, logged_by) VALUES (?,?,?,?,?)",
                 (mid, "2025-03-03T08:00", "taken", "2025-03-03T08:05", "elder"))
    run_reminders(conn, ist(2025, 3, 3, 9, 0))
    assert emails(conn, pid, "Missed") == []


def test_stale_missed_doses_are_not_sent_after_long_downtime(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid)
    run_reminders(conn, ist(2025, 3, 3, 20, 0))  # 12 hours late
    assert emails(conn, pid, "Missed") == []


def test_appointment_windows(conn):
    pid = fresh_profile(conn)
    conn.execute("INSERT INTO appointments (profile_id, doctor, place, starts_at) VALUES (?,?,?,?)",
                 (pid, "Dr. A", "Clinic", "2025-03-05T15:00"))
    run_reminders(conn, ist(2025, 3, 4, 10, 0))  # more than a day before
    assert emails(conn, pid, "Appointment") == []
    run_reminders(conn, ist(2025, 3, 4, 15, 0))  # one day before
    got = emails(conn, pid, "Appointment")
    assert len(got) == 3 and all("tomorrow" in s for _, s in got)
    run_reminders(conn, ist(2025, 3, 5, 12, 0))  # not yet 2h
    assert len(emails(conn, pid, "Appointment")) == 3
    run_reminders(conn, ist(2025, 3, 5, 13, 0))  # two hours before
    got = emails(conn, pid, "Appointment")
    assert len(got) == 6 and sum("2 hours" in s for _, s in got) == 3
    run_reminders(conn, ist(2025, 3, 5, 15, 30))  # after start: nothing more
    assert len(emails(conn, pid, "Appointment")) == 6


def test_low_stock_once_per_day(conn):
    pid = fresh_profile(conn)
    add_med(conn, pid, name="Low", stock=3)
    add_med(conn, pid, name="Plenty", stock=60)
    run_reminders(conn, ist(2025, 3, 3, 12, 0))
    run_reminders(conn, ist(2025, 3, 3, 18, 0))
    low = emails(conn, pid, "Low stock")
    assert len(low) == 2 and all("Low" in s for _, s in low)
    run_reminders(conn, ist(2025, 3, 4, 12, 0))
    assert len(emails(conn, pid, "Low stock")) == 4


def test_no_contacts_means_no_emails(conn):
    pid, _ = create_profile(conn, "Lonely", "Asia/Kolkata", [])
    add_med(conn, pid)
    run_reminders(conn, ist(2025, 3, 3, 9, 0))
    assert emails(conn, pid) == []


def test_timezone_is_respected(conn):
    pid = fresh_profile(conn, tz="America/New_York")
    add_med(conn, pid)
    run_reminders(conn, datetime(2025, 3, 3, 12, 55, tzinfo=UTC))  # 07:55 EST
    assert emails(conn, pid, "Dose reminder")


def test_run_endpoint_requires_secret_token(client):
    assert client.post("/api/reminders/run").status_code == 401
    assert client.post("/api/reminders/run", headers={"X-Reminder-Token": "wrong"}).status_code == 401
    r = client.post("/api/reminders/run", headers={"X-Reminder-Token": "test-reminder-token"})
    assert r.status_code == 200 and set(r.json()["sent"]) == {"doses", "appointments", "low_stock"}


def test_run_endpoint_disabled_without_configured_token(client, monkeypatch):
    monkeypatch.setenv("REMINDER_TOKEN", "")
    assert client.post("/api/reminders/run", headers={"X-Reminder-Token": ""}).status_code == 503


def test_outbox_endpoint_shows_demo_emails(client, elder):
    client.post("/api/reminders/run", headers={"X-Reminder-Token": "test-reminder-token"})
    box = client.get("/api/outbox", headers=elder).json()
    assert box["smtp_configured"] is False
    assert box["emails"], "demo data has a low-stock medicine, so an email is expected"
    assert all(e["delivered"] == 0 for e in box["emails"])
