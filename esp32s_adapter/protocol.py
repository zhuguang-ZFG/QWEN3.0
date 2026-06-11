"""Protocol conversion between lima-device-v1 and esp32S_XYZ Edge-C."""

from __future__ import annotations

from typing import Any

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "estop", "get_device_info"})


def generate_route_policy(capability: str) -> dict[str, Any]:
    """Generate route_policy for Edge-C motion_task from capability."""
    if capability in CONTROL_CAPABILITIES:
        return {
            "route_role": "device_control",
            "model_required": False,
            "primary_strategy": "deterministic",
            "artifact_required": "none",
        }
    elif capability == "run_path":
        return {
            "route_role": "device_write",
            "model_required": False,
            "primary_strategy": "provided_path",
            "artifact_required": "none",
        }
    else:
        return {
            "route_role": "device_unknown",
            "model_required": False,
            "primary_strategy": "planner_required",
            "artifact_required": "none",
        }


def lima_to_edge_c_task(lima_task: dict[str, Any]) -> dict[str, Any]:
    """Convert LiMa task_dispatch to Edge-C motion_task.

    Args:
        lima_task: LiMa task_dispatch frame with type/device_id/task_id/capability/params

    Returns:
        Edge-C motion_task frame with route_policy and source fields added
    """
    capability = lima_task.get("capability", "")
    edge_c_task: dict[str, Any] = {
        "type": "motion_task",
        "task_id": lima_task["task_id"],
        "device_id": lima_task["device_id"],
        "capability": capability,
        "source": "client",
        "params": lima_task.get("params", {}),
        "route_policy": generate_route_policy(capability),
    }
    if "request_id" in lima_task:
        edge_c_task["request_id"] = lima_task["request_id"]
    if "trace_id" in lima_task:
        edge_c_task["trace_id"] = lima_task["trace_id"]
    return edge_c_task


def edge_c_to_lima_event(edge_c_event: dict[str, Any]) -> dict[str, Any]:
    """Convert Edge-C motion_event to LiMa motion_event.

    Args:
        edge_c_event: Edge-C motion_event with session_id/type/task_id/phase

    Returns:
        LiMa motion_event frame with session_id removed
    """
    lima_event: dict[str, Any] = {
        "type": "motion_event",
        "device_id": edge_c_event.get("device_id", ""),
        "task_id": edge_c_event["task_id"],
        "phase": edge_c_event["phase"],
    }
    if "progress" in edge_c_event and isinstance(edge_c_event["progress"], dict):
        lima_event["progress"] = edge_c_event["progress"]
    if "request_id" in edge_c_event:
        lima_event["request_id"] = edge_c_event["request_id"]
    if "error_code" in edge_c_event or "error_message" in edge_c_event:
        lima_event["error"] = {
            "code": edge_c_event.get("error_code", "unknown"),
            "reason": edge_c_event.get("error_message", ""),
        }
    return lima_event
