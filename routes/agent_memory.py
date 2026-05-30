"""Session memory REST API — CLI stores/retrieves conversation memories.

POST /agent/memory/store    — Store a memory (code_fact, routing_lesson, etc.)
GET  /agent/memory/query    — Query memories by type
GET  /agent/memory/context  — Get context for routing (preferred backends, etc.)
"""

from __future__ import annotations

import logging
import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agent/memory", tags=["agent-memory"])
_log = logging.getLogger(__name__)


class StoreMemoryRequest(BaseModel):
    memory_type: str = Field(..., description="Type: code_fact, routing_lesson, test_result, skill")
    summary: str = Field(..., min_length=1, max_length=2000)
    backend: str = Field(default="")
    scenario: str = Field(default="")
    metadata: dict = Field(default_factory=dict)


class QueryMemoryRequest(BaseModel):
    memory_type: str = Field(default="")
    query: str = Field(default="", max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


@router.post("/store")
async def store_memory(req: StoreMemoryRequest) -> dict:
    """Store a memory from CLI into the session memory system."""
    try:
        from session_memory.store import save_typed_memory

        detail = json.dumps(
            {
                "backend": req.backend,
                "scenario": req.scenario,
                "metadata": req.metadata,
            },
            ensure_ascii=False,
        )
        memory_id = save_typed_memory(
            memory_type=req.memory_type,
            summary=req.summary,
            detail=detail,
        )
        return {"ok": True, "memory_id": memory_id}
    except Exception as exc:
        _log.warning("memory store failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/query")
async def query_memory(req: QueryMemoryRequest) -> dict:
    """Query memories by type and optional text search."""
    try:
        from session_memory.store import query_by_type
        memories = query_by_type(memory_type=req.memory_type, limit=req.limit)
        if req.query:
            needle = req.query.lower()
            memories = [
                memory for memory in memories
                if needle in memory.summary.lower() or needle in memory.detail.lower()
            ]
        return {"ok": True, "memories": memories, "count": len(memories)}
    except Exception as exc:
        _log.warning("memory query failed: %s", exc)
        return {"ok": False, "error": str(exc), "memories": []}


@router.get("/context")
async def get_routing_context(backend: str = "", scenario: str = "") -> dict:
    """Get memory context for routing decisions."""
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        ctx = hmem.get_context_for_routing(backend or "unknown", scenario)
        return {"ok": True, "context": ctx}
    except Exception as exc:
        _log.debug("memory context failed: %s", exc)
        return {"ok": False, "context": {}}
