from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import DEMO


def test_all_security_headers_are_present(client):
    h = client.get("/api/health").headers
    assert h["strict-transport-security"].startswith("max-age=")
    assert h["cross-origin-opener-policy"] == "same-origin"
    assert h["cross-origin-resource-policy"] == "same-origin"
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert h["cache-control"] == "no-store"


def test_oversized_json_body_is_rejected_before_parsing(client):
    big = {"passcode": "x" * 70_000}
    r = client.post("/api/auth/login", json=big)
    assert r.status_code == 413 and r.json() == {"detail": "That request is too large."}


def test_oversized_upload_is_rejected_but_normal_json_still_works(client, elder):
    r = client.post(
        "/api/ai/prescription", files={"file": ("a.png", b"0" * (7 * 1024 * 1024), "image/png")}, headers=elder
    )
    assert r.status_code == 413
    assert client.post("/api/auth/login", json={"passcode": DEMO["family"]}).status_code == 200


def test_field_length_limits_are_enforced(client, elder):
    too_long = {"name": "x" * 101, "dose": "1", "times": ["08:00"], "start_date": "2026-01-01"}
    assert client.post("/api/medications", json=too_long, headers=elder).status_code == 422
    assert client.post("/api/comments", json={"text": "x" * 501}, headers=elder).status_code == 422
    assert client.post("/api/checkins", json={"mood": "good", "note": "x" * 301}, headers=elder).status_code == 422
    assert client.post("/api/profiles", json={"name": "x" * 81}).status_code == 422


def test_unexpected_errors_never_leak_a_stack_trace(client, monkeypatch):
    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("secret database path /srv/data.db")

    monkeypatch.setattr("app.services.adherence.weekly_stats", explode)
    token = client.post("/api/auth/login", json={"passcode": DEMO["elder"]}).json()["token"]
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        r = c.get("/api/adherence/weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert "secret" not in r.text and "Traceback" not in r.text


def test_unknown_api_path_is_a_clean_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "Traceback" not in r.text
