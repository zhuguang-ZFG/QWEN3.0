from fastapi.testclient import TestClient

import routes.public_demo as public_demo
import server


def _post_malformed(path: str, *, headers: dict[str, str] | None = None):
    merged = {"Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    return TestClient(server.app).post(path, headers=merged, content='{"bad":')


def test_embeddings_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/v1/embeddings",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_images_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/v1/images/generations",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_public_demo_rejects_malformed_json(monkeypatch):
    monkeypatch.setenv("LIMA_PUBLIC_DEMO_ENABLED", "1")
    public_demo._public_demo_hits.clear()

    response = _post_malformed("/public/demo/chat")

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_device_gateway_tasks_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_device_gateway_events_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_device_gateway_events_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_outcome_ingest_rejects_malformed_json_after_auth(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")

    response = _post_malformed(
        "/internal/v1/outcome",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"
