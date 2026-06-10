# Device Model Routing Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit cloud-side routing roles for AI drawing/writing device tasks so LiMa can later admit and switch models by task family instead of relying on generic chat/code route pools.

**Architecture:** Keep this phase cloud-only and firmware-safe. Add a small `device_gateway.model_routing` module that classifies parsed device tasks into route roles and emits serializable route policy metadata; attach that metadata to `motion_task` payloads created by `device_gateway.tasks.project_to_motion_task()`. Do not call real image providers in this phase.

**Tech Stack:** Python 3.10, pytest, existing `device_gateway` modules, existing task store/workflow/ledger behavior.

---

## File Structure

| File | Responsibility |
|---|---|
| `device_gateway/model_routing.py` | Device task family to model-routing role classification. |
| `device_gateway/tasks.py` | Attach route metadata to created motion tasks. |
| `tests/test_device_gateway_model_routing.py` | Public behavior tests for role classification and task metadata. |
| `docs/superpowers/plans/2026-06-10-device-model-routing-phase1.md` | This implementation plan and evidence checklist. |

## Task 1: Device Route Roles

**Files:**
- Create: `device_gateway/model_routing.py`
- Create: `tests/test_device_gateway_model_routing.py`
- Modify: `device_gateway/tasks.py`

- [ ] **Step 1: Write failing tests for route role behavior**

Add tests that call public device gateway functions:

```python
from device_gateway.model_routing import resolve_device_route_policy
from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests


def setup_function():
    reset_tasks_for_tests()


def test_control_command_uses_no_model_route():
    task = create_task_from_transcript("dev-1", "home")
    assert task["route_policy"]["route_role"] == "device_control"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["primary_strategy"] == "deterministic"


def test_write_text_uses_device_write_route():
    task = create_task_from_transcript("dev-1", "write LiMa")
    assert task["route_policy"]["route_role"] == "device_write"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["artifact_required"] == "preview_svg"


def test_generated_drawing_uses_device_draw_route():
    task = create_task_from_transcript("dev-1", "draw cat")
    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["route_policy"]["model_required"] is True
    assert task["route_policy"]["artifact_required"] == "vector_path"


def test_svg_like_generated_drawing_uses_vector_route_without_model():
    policy = resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}}
    )
    assert policy["route_role"] == "device_vector"
    assert policy["model_required"] is False
```

Run: `python -m pytest tests/test_device_gateway_model_routing.py -q`
Expected: FAIL because `device_gateway.model_routing` does not exist.

- [ ] **Step 2: Implement minimal route policy module**

Create `device_gateway/model_routing.py`:

```python
from __future__ import annotations

from typing import Any

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "get_device_info"})


def looks_like_svg_path(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped) and stripped[0] in "MmLCcQqHhVvZz"


def resolve_device_route_policy(voice_task: dict[str, Any]) -> dict[str, Any]:
    capability = str(voice_task.get("capability", ""))
    params = voice_task.get("params", {})
    if not isinstance(params, dict):
        params = {}

    if capability in CONTROL_CAPABILITIES:
        return _policy("device_control", False, "deterministic", "none")
    if capability == "write_text":
        return _policy("device_write", False, "deterministic", "preview_svg")
    if capability == "draw_generated":
        prompt = str(params.get("prompt", ""))
        if looks_like_svg_path(prompt):
            return _policy("device_vector", False, "svg_vector", "preview_svg")
        return _policy("device_draw", True, "image_then_vector", "vector_path")
    if capability == "run_path":
        return _policy("device_vector", False, "provided_path", "preview_svg")
    return _policy("device_unknown", True, "planner_required", "none")


def _policy(route_role: str, model_required: bool, primary_strategy: str, artifact_required: str) -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
    }
```

- [ ] **Step 3: Attach policy in task projection**

In `device_gateway/tasks.py`, import `resolve_device_route_policy` and set:

```python
route_policy = resolve_device_route_policy(voice_task)
...
task["route_policy"] = route_policy
```

Apply this to successful tasks and failed/blocked task objects so diagnostics can
see the route role even when validation or policy blocks dispatch.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py tests/test_p1_4_device_stability_gate.py -q
```

Expected: PASS.

- [ ] **Step 5: Run local lint/whitespace gate**

Run:

```powershell
python scripts/run_ruff_check.py
git diff --check
```

Expected: PASS.

## Task 2: Role-Aware Route Evidence

**Files:**
- Modify: `device_gateway/tasks.py`
- Modify or create: focused tests under `tests/`

- [ ] **Step 1: Add tests proving route policy is recorded into task ledger/artifacts**
- [ ] **Step 2: Add route role to task-created ledger payload**
- [ ] **Step 3: Verify focused ledger tests pass**

This task starts only after Task 1 is green and committed.

## Task 3: Drawing Model Admission Fixtures

**Files:**
- Create: `scripts/eval_device_drawing_backends.py`
- Create: `tests/test_device_drawing_backend_eval.py`
- Update: `docs/FREE_MODEL_ROUTING_STATUS.md`

- [ ] **Step 1: Define no-network fixture scoring for line-art/vector suitability**
- [ ] **Step 2: Add CLI shell that can run against a named backend when keys exist**
- [ ] **Step 3: Record dated evidence without changing route pools**

This task must not promote a backend automatically.

## Task 4: Real Image-To-Vector Route Integration

**Files:**
- Modify or create: `device_gateway/drawing_pipeline.py`
- Modify: `device_gateway/tasks.py`
- Add focused tests under `tests/`

- [ ] **Step 1: Extract deterministic vector pipeline boundary**
- [ ] **Step 2: Add provider-gated image generation adapter**
- [ ] **Step 3: Validate preview/path/simulation before dispatch**

This task starts only after Task 3 has admission evidence.
