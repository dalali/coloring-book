"""Endpoint integration tests (architecture §4).

The text flow is exercised by monkeypatching the provider factory so no network
call is made.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import service
from app.main import app

client = TestClient(app)


def test_health_alias():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_health_shape():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "text_flow_enabled" in body


def test_from_image_success(multicolor_png):
    r = client.post(
        "/api/coloring/from-image",
        files={"file": ("q.png", multicolor_png, "image/png")},
        data={"complexity": "simple"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_image"].startswith("data:image/png;base64,")
    assert body["source_preview"].startswith("data:image/png;base64,")
    assert body["region_count"] >= 1
    assert len(body["legend"]) >= 1
    assert body["legend"][0]["hex"].startswith("#")


def test_from_image_rejects_bad_type():
    r = client.post(
        "/api/coloring/from-image",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_TYPE"


def test_from_image_rejects_unreadable(monkeypatch):
    # A PNG content-type but garbage bytes -> 422 UNREADABLE_IMAGE.
    r = client.post(
        "/api/coloring/from-image",
        files={"file": ("x.png", b"not-an-image", "image/png")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNREADABLE_IMAGE"


def test_from_text_disabled_without_provider(monkeypatch):
    monkeypatch.setattr(service, "get_provider", lambda s: None)
    r = client.post("/api/coloring/from-text", json={"prompt": "a cat"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "TEXT_FLOW_DISABLED"


def test_from_text_empty_prompt():
    r = client.post("/api/coloring/from-text", json={"prompt": "   "})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "EMPTY_PROMPT"


def test_from_text_success_with_fake_provider(monkeypatch, multicolor_png):
    class FakeProvider:
        name = "fake"

        def generate(self, prompt, size=1024):
            return multicolor_png

    monkeypatch.setattr(service, "get_provider", lambda s: FakeProvider())
    r = client.post(
        "/api/coloring/from-text",
        json={"prompt": "four colored squares", "complexity": "simple"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_image"].startswith("data:image/png;base64,")
    assert body["region_count"] >= 1
