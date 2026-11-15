import bcrypt

from app import security

from .conftest import DEMO, auth


def test_passcodes_are_stored_hashed(client, conn):
    hashes = [r["hash"] for r in conn.execute("SELECT hash FROM passcodes")]
    assert hashes and all(h.startswith("$2") for h in hashes)
    assert not any(code in h for h in hashes for code in DEMO.values())
    assert any(bcrypt.checkpw(DEMO["elder"].encode(), h.encode()) for h in hashes)


def test_hash_and_verify():
    h = security.hash_passcode("ABCD-12345678")
    assert h != "ABCD-12345678"
    assert security.verify_passcode("ABCD-12345678", h)
    assert not security.verify_passcode("ABCD-00000000", h)
    assert not security.verify_passcode("x", "not-a-hash")


def test_login_roles(client):
    for role, code in DEMO.items():
        r = client.post("/api/auth/login", json={"passcode": code})
        assert r.status_code == 200 and r.json()["role"] == role


def test_login_is_case_insensitive_and_token_not_stored_plain(client, conn):
    r = client.post("/api/auth/login", json={"passcode": " demo-elder24 "})
    assert r.status_code == 200
    token = r.json()["token"]
    assert conn.execute("SELECT 1 FROM sessions WHERE token_hash = ?", (token,)).fetchone() is None


def test_wrong_passcode_401_then_rate_limited(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"passcode": "DEMO-WRONG123"}).status_code == 401
    r = client.post("/api/auth/login", json={"passcode": "DEMO-WRONG123"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    # Even the right passcode is blocked while locked out.
    assert client.post("/api/auth/login", json={"passcode": DEMO["elder"]}).status_code == 429


def test_rate_limiter_window():
    rl = security.RateLimiter(max_attempts=2, window_seconds=60)
    rl.record_failure("k", now=0)
    rl.record_failure("k", now=1)
    assert rl.retry_after("k", now=2) > 0
    assert rl.retry_after("k", now=61.5) == 0
    rl.record_failure("k", now=62)
    rl.reset("k")
    assert rl.retry_after("k", now=63) == 0


def test_requires_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_logout_invalidates_token(client):
    h = auth(client)
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/me", headers=h).status_code == 401


def test_create_profile_returns_working_passcodes(client):
    r = client.post("/api/profiles", json={"name": "Grandpa Joe", "contacts": [{"name": "A", "email": "a@b.co", "role": "family"}]})
    assert r.status_code == 201
    codes = r.json()["passcodes"]
    assert set(codes) == {"elder", "caretaker", "family"}
    login = client.post("/api/auth/login", json={"passcode": codes["caretaker"]})
    assert login.status_code == 200 and login.json()["role"] == "caretaker"


def test_create_profile_validation(client):
    assert client.post("/api/profiles", json={"name": "", "contacts": []}).status_code == 422
    assert client.post("/api/profiles", json={"name": "X", "timezone": "Mars/Base"}).status_code == 422
    bad = {"name": "X", "contacts": [{"name": "A", "email": "not-an-email", "role": "family"}]}
    assert client.post("/api/profiles", json=bad).status_code == 422
