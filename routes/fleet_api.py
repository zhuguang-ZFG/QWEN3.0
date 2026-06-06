"""Fleet management REST API — mounted on the VPS main server.

Endpoints:
  POST /fleet/register   — node registers itself
  POST /fleet/heartbeat  — node sends heartbeat
  GET  /fleet/nodes      — list all nodes
  POST /fleet/submit     — submit a task
  GET  /fleet/poll/{node_id} — node polls for tasks
  POST /fleet/complete   — node reports task completion
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/fleet", tags=["fleet"])
_log = logging.getLogger(__name__)

_admin_token: str = ""


def inject_state(admin_token: str = "") -> None:
    global _admin_token
    _admin_token = admin_token


class RegisterRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=64)
    host: str = Field(default="")
    port: int = Field(default=0)
    role: str = Field(default="worker")
    gpu: bool = Field(default=False)
    gpu_model: str = Field(default="")
    gpu_vram_gb: float = Field(default=0.0)
    cpu_cores: int = Field(default=0)
    ram_gb: float = Field(default=0.0)
    shell: bool = Field(default=True)
    workspace: bool = Field(default=True)
    models: list[str] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    node_id: str
    load_avg: float = Field(default=0.0)
    status: str = Field(default="online")


class SubmitRequest(BaseModel):
    task_type: str = Field(default="shell")
    command: str = Field(default="")
    required_gpu: bool = Field(default=False)
    required_model: str = Field(default="")
    payload: dict = Field(default_factory=dict)


class CompleteRequest(BaseModel):
    task_id: str
    result: str = Field(default="")
    error: str = Field(default="")


@router.post("/register")
async def register_node(req: RegisterRequest) -> dict:
    from fleet.node_registry import NodeCapabilities, get_registry
    caps = NodeCapabilities(
        gpu=req.gpu, gpu_model=req.gpu_model, gpu_vram_gb=req.gpu_vram_gb,
        cpu_cores=req.cpu_cores, ram_gb=req.ram_gb,
        shell=req.shell, workspace=req.workspace, models=req.models,
    )
    node = get_registry().register(
        req.node_id, host=req.host, port=req.port, role=req.role,
        capabilities=caps,
    )
    return {"ok": True, "node": node.to_dict()}


@router.post("/heartbeat")
async def heartbeat(req: HeartbeatRequest) -> dict:
    from fleet.node_registry import get_registry
    node = get_registry().heartbeat(req.node_id, load_avg=req.load_avg, status=req.status)
    if node is None:
        return {"ok": False, "error": "node not registered"}
    return {"ok": True, "online_nodes": len(get_registry().get_online_nodes())}


@router.get("/nodes")
async def list_nodes() -> dict:
    from fleet.node_registry import get_registry
    nodes = get_registry().get_all_nodes()
    return {
        "total": len(nodes),
        "online": len([n for n in nodes if n.is_online]),
        "nodes": [n.to_dict() for n in nodes],
    }


@router.post("/submit")
async def submit_task(req: SubmitRequest) -> dict:
    from fleet.task_dispatcher import get_dispatcher
    task = get_dispatcher().submit(
        task_type=req.task_type, command=req.command,
        required_gpu=req.required_gpu, required_model=req.required_model,
        payload=req.payload,
    )
    return {"ok": True, "task_id": task.task_id, "status": task.status}


@router.get("/poll/{node_id}")
async def poll_tasks(node_id: str) -> dict:
    from fleet.node_registry import get_registry
    from fleet.task_dispatcher import get_dispatcher

    node = get_registry().get_node(node_id)
    if node is None:
        return {"ok": False, "error": "node not registered"}

    # Update heartbeat
    get_registry().heartbeat(node_id)

    # Find pending task
    result = get_dispatcher().dispatch(get_registry())
    if result is None:
        return {"ok": True, "task": None}

    task, assigned_node = result
    return {
        "ok": True,
        "task": {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "command": task.command,
            "payload": task.payload,
        },
    }


@router.post("/complete")
async def complete_task(req: CompleteRequest) -> dict:
    from fleet.node_registry import get_registry
    from fleet.task_dispatcher import get_dispatcher

    dispatcher = get_dispatcher()
    task = dispatcher.get_task(req.task_id)
    if task is None:
        return {"ok": False, "error": "task not found"}

    dispatcher.complete_task(req.task_id, result=req.result, error=req.error)

    if req.error:
        get_registry().mark_failed(task.assigned_to)
    else:
        get_registry().mark_completed(task.assigned_to)

    return {"ok": True}
