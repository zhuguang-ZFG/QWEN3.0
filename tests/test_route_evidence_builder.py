"""Direct unit tests for device_gateway.route_evidence_builder.

These complement the higher-level test_device_gateway_route_evidence.py (which
exercises the functions via tasks.py / task_events.py) by covering the pure
content-builder branches directly: optional policy/sim/error/workflow dict
fields, the no-route-policy early return, and device_consumed/recovery shapes.
"""

from __future__ import annotations

from unittest.mock import patch

import device_gateway.route_evidence_builder as reb
from device_gateway.route_evidence_builder import (
    _build_route_evidence_content,
    record_device_consumed_route_evidence,
    record_recovery_route_evidence,
    record_route_evidence_artifact,
)


def _task(**overrides) -> dict:
    base = {
        "task_id": "t-1",
        "device_id": "dev-1",
        "capability": "draw_generated",
        "source": "voice",
        "request_id": "req-1",
        "route_policy": {
            "route_role": "device_draw",
            "primary_strategy": "image_then_vector",
            "model_required": True,
            "artifact_required": "preview_svg",
            "backend": "dashscope_wanx",
        },
    }
    base.update(overrides)
    return base


def test_build_content_returns_none_without_route_policy() -> None:
    assert _build_route_evidence_content({"route_policy": None}, "task_created") is None
    assert _build_route_evidence_content({}, "task_created") is None


def test_build_content_includes_core_route_fields() -> None:
    content = _build_route_evidence_content(_task(), "task_created")
    assert content is not None
    assert content["scenario"] == "task_created"
    assert content["route_role"] == "device_draw"
    assert content["backend"] == "dashscope_wanx"
    assert content["capability"] == "draw_generated"
    assert content["request_id"] == "req-1"


def test_build_content_picks_up_optional_dicts() -> None:
    content = _build_route_evidence_content(
        _task(
            device_capabilities=["draw_generated", "run_path"],
            policy={"decision": "admit", "reason": "ok"},
            simulation={"risk_score": 0.3, "estimated_runtime_sec": 12.0},
            workflow_state="running",
            error={"code": "E_X", "reason": "boom"},
            status="failed",
        ),
        "task_terminal",
    )
    assert content is not None
    assert content["device_capabilities"] == ["draw_generated", "run_path"]
    assert content["policy_decision"] == "admit"
    assert content["policy_reason"] == "ok"
    assert content["sim_risk_score"] == 0.3
    assert content["sim_runtime_sec"] == 12.0
    assert content["workflow_state"] == "running"
    assert content["error_code"] == "E_X"
    assert content["task_status"] == "failed"


def test_build_content_entrypoint_falls_back_to_source() -> None:
    content = _build_route_evidence_content(_task(), "task_created")
    assert content is not None
    assert content["entrypoint"] == "voice"  # no explicit entrypoint -> source


def test_record_artifact_no_op_without_route_policy() -> None:
    """A task missing route_policy must not touch the artifact store."""
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_route_evidence_artifact({"task_id": "t", "route_policy": None})
        persist.assert_not_called()


def test_record_artifact_persists_with_built_content() -> None:
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_route_evidence_artifact(_task(), scenario="task_created")
        persist.assert_called_once()
        _, kwargs = persist.call_args
        assert kwargs["task_id"] == "t-1"
        assert kwargs["device_id"] == "dev-1"
        assert kwargs["route_policy"]["route_role"] == "device_draw"
        assert kwargs["content"]["scenario"] == "task_created"


def test_record_device_consumed_requires_evidence_dict() -> None:
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_device_consumed_route_evidence("t-1", {"phase": "done"})  # no evidence
        persist.assert_not_called()


def test_record_device_consumed_merges_device_evidence() -> None:
    event = {
        "phase": "done",
        "request_id": "req-1",
        "device_id": "dev-1",
        "route_policy_evidence": {
            "route_role": "device_draw",
            "backend": "dashscope_wanx",
            "model_required": True,
            "primary_strategy": "image_then_vector",
            "artifact_required": "preview_svg",
        },
    }
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_device_consumed_route_evidence("t-1", event)
        persist.assert_called_once()
        _, kwargs = persist.call_args
        assert kwargs["content"]["scenario"] == "device_consumed"
        assert kwargs["content"]["phase"] == "done"
        assert kwargs["route_policy"]["backend"] == "dashscope_wanx"


def test_record_recovery_without_task_uses_empty_route_context() -> None:
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_recovery_route_evidence("t-1", "dev-1", {"action": "retry", "attempt": 2}, task=None)
        persist.assert_called_once()
        _, kwargs = persist.call_args
        assert kwargs["content"]["recovery_action"] == "retry"
        assert kwargs["content"]["recovery_attempt"] == 2
        assert kwargs["route_policy"]["route_role"] == ""


def test_record_recovery_with_task_propagates_route_role() -> None:
    with patch.object(reb, "_persist_route_evidence") as persist:
        record_recovery_route_evidence("t-1", "dev-1", {"action": "rollback"}, task=_task(capability="run_path"))
        persist.assert_called_once()
        _, kwargs = persist.call_args
        assert kwargs["content"]["route_role"] == "device_draw"
        assert kwargs["content"]["capability"] == "run_path"
