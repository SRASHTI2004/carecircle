import os
import tempfile

import pytest

# Configure the environment before the app is imported.
_dir = tempfile.mkdtemp()
os.environ.update(
    DATABASE_PATH=os.path.join(_dir, "test.db"),
    BCRYPT_ROUNDS="4",
    DISABLE_SCHEDULER="1",
    REMINDER_TOKEN="test-reminder-token",
    SMTP_HOST="",
    GEMINI_API_KEY="",
)

from fastapi.testclient import TestClient  # noqa: E402

from app import db, security  # noqa: E402
from app.main import create_app  # noqa: E402

DEMO = {"elder": "DEMO-ELDER24", "caretaker": "DEMO-CARER24", "family": "DEMO-FAMILY24"}


@pytest.fixture()
def client():
    path = os.environ["DATABASE_PATH"]
    for suffix in ("", "-journal"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    for limiter in (
        security.client_limiter,
        security.profile_limiter,
        security.create_limiter,
        security.ai_limiter,
        security.email_limiter,
    ):
        limiter._hits.clear()
    with TestClient(create_app()) as c:  # lifespan creates schema + seeds the DEMO profile
        yield c


@pytest.fixture()
def conn(client):
    c = db.connect()
    yield c
    c.close()


def auth(client, role="elder"):
    r = client.post("/api/auth/login", json={"passcode": DEMO[role]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def elder(client):
    return auth(client, "elder")


@pytest.fixture()
def caretaker(client):
    return auth(client, "caretaker")


@pytest.fixture()
def family(client):
    return auth(client, "family")
