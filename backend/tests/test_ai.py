import json

import httpx
import pytest

from app.services import ai

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise httpx.HTTPStatusError(
                "boom", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status)
            )

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self.payload}]}}]}


@pytest.fixture()
def with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")


def upload(client, headers, data=PNG, mime="image/png"):
    return client.post("/api/ai/prescription", files={"file": ("rx.png", data, mime)}, headers=headers)


def test_prescription_requires_ai_permission(client, family):
    assert upload(client, family).status_code == 403


def test_prescription_without_key_gives_clear_message(client, elder):
    body = upload(client, elder).json()
    assert body["ok"] is False and "by hand" in body["message"] and body["drafts"] == []
    assert "doctor" in body["disclaimer"]


def test_prescription_valid_ai_output_becomes_drafts(client, elder, with_key, monkeypatch):
    payload = json.dumps(
        {"medicines": [{"name": "Metformin", "dose": "500 mg", "times_per_day": 2, "instructions": "after food"}]}
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(payload))
    body = upload(client, elder).json()
    assert body["ok"] and body["drafts"][0]["times"] == ["08:00", "20:00"]


def test_prescription_does_not_save_anything(client, elder, with_key, monkeypatch):
    before = len(client.get("/api/medications", headers=elder).json())
    payload = json.dumps({"medicines": [{"name": "Zed", "dose": "1", "times_per_day": 1}]})
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(payload))
    upload(client, elder)
    assert len(client.get("/api/medications", headers=elder).json()) == before


@pytest.mark.parametrize(
    "payload", ["not json", json.dumps({"medicines": [{"name": "", "times_per_day": 99}]}), json.dumps({"wrong": 1})]
)
def test_prescription_schema_violations_are_rejected(client, elder, with_key, monkeypatch, payload):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(payload))
    body = upload(client, elder).json()
    assert body["ok"] is False and body["drafts"] == []


def test_prescription_http_failure(client, elder, with_key, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp("", status=503))
    assert upload(client, elder).json()["ok"] is False


def test_prescription_rejects_bad_files(client, elder):
    assert upload(client, elder, data=b"not an image", mime="image/png").status_code == 415
    assert upload(client, elder, data=PNG, mime="application/pdf").status_code == 415
    assert upload(client, elder, data=PNG + b"0" * (5 * 1024 * 1024)).status_code == 413


def test_weekly_summary_falls_back_without_ai(client, family):
    body = client.get("/api/ai/weekly-summary", headers=family).json()
    assert body["source"] == "facts" and "Margaret" in body["summary"] and "%" in body["summary"]
    assert "Showing a simple summary" in body["message"]


def test_weekly_summary_uses_ai_when_valid(client, family, with_key, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(json.dumps({"summary": "Mom had a good week."})))
    body = client.get("/api/ai/weekly-summary", headers=family).json()
    assert body["source"] == "ai" and body["summary"] == "Mom had a good week."


def test_plain_summary_text():
    stats = {"days": 7, "percent": 92, "counts": {"taken_late": 1}, "missed_by_medicine": {"Metformin": 2}}
    text = ai.plain_summary("Mom", stats)
    assert "92%" in text and "Metformin missed 2 times" in text and "1 of them late" in text
    assert "not enough data" in ai.plain_summary("Mom", {"percent": None})
