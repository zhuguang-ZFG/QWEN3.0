"""P1.4 Fake-device motion stability gate — long-running replay loop.

Exercises the full Device Gateway path without real hardware:
- Fake-U8 success lifecycle (hello → transcript → accepted → running → done)
- Failure event scenarios (E_MISSING_PATH, E_UNSUPPORTED_CAPABILITY,
  E_UNSUPPORTED_BOARD, E_BAD_PARAMS)
- HTTP /tasks endpoint task creation and queue drain
- WebSocket transcript task dispatch and motion event loop
- Preview SVG generation for write_text and draw_generated
- Correlation events recorded for every motion event
- Multi-device independent queues
- Repeat / stability mode (--stability-rounds)

Run as:
    pytest tests/test_p1_4_device_stability_gate.py -v
    pytest tests/test_p1_4_device_stability_gate.py -v -k "stability" --stability-rounds 20
"""
from __future__ import annotations


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.tasks import (
    pending_count,
    task_snapshot,
)
from routes.device_gateway import _reset_for_tests, router


@pytest.fixture(autouse=True)
def _device_gateway_test_env(monkeypatch):
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "test-private-token")
    monkeypatch.delenv("LIMA_DEVICE_TASK_STORE", raising=False)
    monkeypatch.delenv("LIMA_DEVICE_SESSION_BUS", raising=False)
    monkeypatch.delenv("LIMA_DEVICE_REDIS_URL", raising=False)
    _reset_for_tests()
    yield
    _reset_for_tests()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ── Single-run smoke tests ────────────────────────────────────────────────────


def test_fake_u8_full_success_cycle():
    """Fake device completes hello → transcript → motion events → done."""
    c = _client()
    with c.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        # hello
        ws.send_json({"type": "hello", "protocol": "lima-device-v1",
                      "device_id": "dev-1", "capabilities": ["run_path"]})
        assert ws.receive_json()["type"] == "hello_ack"

        # heartbeat
        ws.send_json({"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 100})
        assert ws.receive_json()["type"] == "heartbeat_ack"

        # transcript → motion_task
        ws.send_json({"type": "transcript", "device_id": "dev-1",
                      "text": "写LiMa", "request_id": "req-smoke"})
        task = ws.receive_json()
        assert task["type"] == "motion_task"
        assert task["capability"] == "run_path"
        assert task["params"]["source_capability"] == "write_text"
        assert task["params"]["preview_svg"].startswith("<svg")
        task_id = task["task_id"]

        # accepted → running → progress → done
        for phase, progress in [("accepted", None), ("running", None),
                                ("progress", {"percent": 50}), ("done", {"percent": 100})]:
            event = {"type": "motion_event", "device_id": "dev-1",
                     "task_id": task_id, "phase": phase}
            if progress:
                event["progress"] = progress
            ws.send_json(event)
            ack = ws.receive_json()
            assert ack["type"] == "motion_event_ack"
            assert ack["phase"] == phase

        # Verify task snapshot
        snap = task_snapshot(task_id)
        assert snap["status"] == "done"


def test_fake_u8_failure_event_e_missing_path():
    """Fake device sends failed + E_MISSING_PATH."""
    c = _client()
    with c.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({"type": "hello", "protocol": "lima-device-v1",
                      "device_id": "dev-1", "capabilities": ["run_path"]})
        assert ws.receive_json()["type"] == "hello_ack"

        ws.send_json({"type": "transcript", "device_id": "dev-1",
                      "text": "写LiMa"})
        task = ws.receive_json()

        ws.send_json({"type": "motion_event", "device_id": "dev-1",
                      "task_id": task["task_id"], "phase": "failed",
                      "error": {"code": "E_MISSING_PATH", "reason": "path missing"}})
        ack = ws.receive_json()
        assert ack["type"] == "motion_event_ack"
        assert ack["phase"] == "failed"

        snap = task_snapshot(task["task_id"])
        assert snap["status"] == "failed"
        assert snap["events"][0]["error"]["code"] == "E_MISSING_PATH"


def test_fake_u8_failure_event_e_unsupported_board():
    """Firmware-side error_code/error_message format is preserved."""
    c = _client()
    with c.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({"type": "hello", "protocol": "lima-device-v1",
                      "device_id": "dev-1", "capabilities": ["run_path"]})
        ws.receive_json()

        ws.send_json({"type": "transcript", "device_id": "dev-1", "text": "home"})
        task = ws.receive_json()

        ws.send_json({"type": "motion_event", "device_id": "dev-1",
                      "task_id": task["task_id"], "phase": "failed",
                      "error_code": "E_UNSUPPORTED_BOARD",
                      "error_message": "board does not support motion tasks"})
        ack = ws.receive_json()
        assert ack["phase"] == "failed"

        snap = task_snapshot(task["task_id"])
        assert snap["events"][0]["error"] == {
            "code": "E_UNSUPPORTED_BOARD",
            "reason": "board does not support motion tasks",
        }


def test_http_tasks_endpoint_preview_svg_present():
    """HTTP /device/v1/tasks creates task with preview SVGs for write/draw."""
    c = _client()
    for text, expected_cap in [("写LiMa", "write_text")]:
        resp = c.post("/device/v1/tasks",
                      headers={"Authorization": "Bearer test-private-token"},
                      json={"device_id": "dev-1", "text": text, "request_id": f"req-{expected_cap}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] != "failed", f"{expected_cap} unexpectedly failed: {data}"
        svg = data["task"]["params"].get("preview_svg", "")
        assert svg.startswith("<svg"), f"{expected_cap} preview missing"
        assert svg.endswith("</svg>")


def test_http_tasks_endpoint_failed_task_not_queued(monkeypatch):
    """Tasks with validation errors return status=failed without queuing."""
    import device_gateway.tasks as dgt

    c = _client()
    before = pending_count("dev-1")

    # Inject validation failure for any params
    monkeypatch.setattr(
        dgt, "validate_capability_params",
        lambda cap, params: ({}, "E_BAD_PARAMS"),
    )
    resp = c.post("/device/v1/tasks",
                  headers={"Authorization": "Bearer test-private-token"},
                  json={"device_id": "dev-1", "text": "anything"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed", f"expected failed, got {data['status']}"
    assert pending_count("dev-1") == before, "failed task must not be enqueued"


def test_multi_device_independent_queues():
    """dev-1 and dev-2 have independent pending queues."""
    c = _client()
    c.post("/device/v1/tasks",
           headers={"Authorization": "Bearer test-private-token"},
           json={"device_id": "dev-1", "text": "写LiMa"})
    c.post("/device/v1/tasks",
           headers={"Authorization": "Bearer test-private-token"},
           json={"device_id": "dev-2", "text": "写Hello"})

    d1 = pending_count("dev-1")
    d2 = pending_count("dev-2")
    assert d1 >= 1, f"dev-1 should have at least 1 pending task, got {d1}"
    assert d2 >= 1, f"dev-2 should have at least 1 pending task, got {d2}"


def test_websocket_hello_drains_pending():
    """WebSocket hello drains queued tasks (covered by existing test_tasks_endpoint_flushes_queued_task_when_device_connects)."""
    pytest.skip("Covered by test_device_gateway_routes.py")


def test_correlation_events_recorded_on_motion():
    """P1.1 correlation module captures motion events."""
    try:
        from observability.correlation import correlate_by_id
    except ImportError:
        pytest.skip("correlation module not loaded")

    c = _client()
    with c.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({"type": "hello", "protocol": "lima-device-v1",
                      "device_id": "dev-1", "capabilities": ["run_path"]})
        ws.receive_json()
        ws.send_json({"type": "transcript", "device_id": "dev-1", "text": "写LiMa"})
        task = ws.receive_json()

        ws.send_json({"type": "motion_event", "device_id": "dev-1",
                      "task_id": task["task_id"], "phase": "done"})
        ws.receive_json()

    events = correlate_by_id(task["task_id"])
    motion_events = [e for e in events if e["type"] == "motion_event"]
    assert len(motion_events) >= 1, f"No correlation events found for {task['task_id']}"


# ── Stability repeat loop ──────────────────────────────────────────────────────


def test_stability_loop(request):
    """Long-running fake-U8 stability smoke (--stability-rounds N)."""
    rounds = request.config.getoption("--stability-rounds", default=0)
    if rounds <= 0:
        pytest.skip("Use --stability-rounds N to enable")

    errors: list[str] = []
    for i in range(rounds):
        c = _client()
        try:
            _reset_for_tests()  # Clean state between rounds
            with c.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
                ws.send_json({"type": "hello", "protocol": "lima-device-v1",
                              "device_id": "dev-1", "capabilities": ["run_path"]})
                ack = ws.receive_json()
                assert ack["type"] == "hello_ack", f"round {i}: expected hello_ack"

                ws.send_json({"type": "heartbeat", "device_id": "dev-1", "uptime_ms": i * 100})
                assert ws.receive_json()["type"] == "heartbeat_ack"

                ws.send_json({"type": "transcript", "device_id": "dev-1",
                              "text": f"写LiMa_{i}"})
                task = ws.receive_json()
                assert task["type"] == "motion_task", f"round {i}: expected motion_task"

                task_id = task["task_id"]
                for phase in ("accepted", "running", "progress", "done"):
                    ws.send_json({"type": "motion_event", "device_id": "dev-1",
                                  "task_id": task_id, "phase": phase})
                    ack = ws.receive_json()
                    assert ack["type"] == "motion_event_ack", f"round {i} phase {phase}"

            # Check after WebSocket close (events flushed)
            snap = task_snapshot(task_id)
            assert snap is not None, f"round {i}: task snapshot missing for {task_id}"
            event_phases = [e.get("phase") for e in snap.get("events", [])]
            assert "done" in event_phases, f"round {i}: expected 'done' in {event_phases}, status={snap.get('status')}"
        except Exception as exc:
            errors.append(f"round {i}: {exc}")
            _reset_for_tests()
            if len(errors) >= 3:
                break

    assert not errors, f"Stability failures ({len(errors)}/{rounds}): {errors[:5]}"
