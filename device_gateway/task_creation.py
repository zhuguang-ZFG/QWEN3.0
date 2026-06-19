"""Device task creation and motion_task projection."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .device_route_memory import record_route_decision
from .intent import resolve_voice_task
from . import task_deps as deps
from .task_creation_builders import (
    _resolve_route_context,
    _handle_policy_error,
    _handle_dispatch_blocked,
    _build_error_task,
    _run_task_simulation,
    _build_run_params_or_error,
    _validate_params_or_error,
    _apply_route_policy_or_blocked,
    _assemble_motion_task,
    _create_task_from_voice_task,
    _next_task_id,
)


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # ponytail: thread offload when called under pytest-asyncio / FastAPI loop
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def project_to_motion_task_async(
    device_id: str, voice_task: dict[str, Any], request_id: str | None = None
) -> dict[str, Any]:
    capability = voice_task["capability"]
    resolved, route_policy = _resolve_route_context(device_id, voice_task)

    validated_policy, policy_error = deps.validate_route_policy(route_policy, capability)
    if policy_error:
        return _handle_policy_error(device_id, voice_task, request_id, route_policy, capability, policy_error)

    if resolved.routing_hints.get("block_dispatch") or route_policy.get("dispatch_blocked"):
        return _handle_dispatch_blocked(device_id, voice_task, request_id, route_policy, capability, resolved)

    task = await _create_task_from_voice_task(
        device_id, voice_task, request_id, route_policy, voice_task.get("params", {}), capability
    )
    task = deps.apply_profile_constraints(task, resolved)

    approval_required = task.get("route_policy", {}).get("approval_required", False)
    if resolved.complete and resolved.fw_compatible and not approval_required:
        backend = route_policy.get("backend", "unknown")
        record_route_decision(device_id, backend, True)

    return task


def project_to_motion_task(device_id: str, voice_task: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return _run_sync(project_to_motion_task_async(device_id, voice_task, request_id))


async def create_task_from_transcript_async(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return await project_to_motion_task_async(device_id, resolve_voice_task(text), request_id)


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return _run_sync(create_task_from_transcript_async(device_id, text, request_id))
