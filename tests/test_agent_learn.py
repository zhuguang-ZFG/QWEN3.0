from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.agent_learn import router


def test_agent_learn_records_sanitized_cli_telemetry(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LIMA_SESSION_DB", str(tmp_path / "memory.db"))

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/agent/learn/outcome",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "task_id": "hls-learn",
            "backend": "cli-agent",
            "scenario": "coding",
            "success": True,
            "latency_ms": 2500,
            "quality_score": 0.8,
            "telemetry": {
                "timeoutMs": 90000,
                "maxRetries": 1,
                "retryCount": 0,
                "modelCalls": [{"ok": True, "latencyMs": 1200, "toolCalls": 1}],
                "toolCapability": {
                    "requested": True,
                    "observed": True,
                    "protocol": "openai",
                    "toolCalls": 1,
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["telemetry_recorded"] is True
    telemetry_file = tmp_path / "cli_telemetry.jsonl"
    assert telemetry_file.exists()
    text = telemetry_file.read_text(encoding="utf-8")
    assert "hls-learn" in text
    assert "openai" in text
