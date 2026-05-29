"""Agent task evolution routes — skill candidate promotion (off chat hot path)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException

from agent_evolution.candidates import get_candidate_store
from agent_evolution.promote import promote_candidate
from routes.agent_task_schemas import PromoteBody
from routes.agent_task_service import require_admin

router = APIRouter()


async def _require_admin(authorization: str = Header(default="")) -> None:
    await require_admin(authorization)


@router.get("/skills/candidates", dependencies=[Depends(_require_admin)])
async def list_skill_candidates():
    store = get_candidate_store()
    return {"candidates": [asdict(c) for c in store.list_pending()]}


@router.post("/skills/{skill_id}/promote", dependencies=[Depends(_require_admin)])
async def promote_skill(skill_id: str, body: PromoteBody):
    store = get_candidate_store()
    success = promote_candidate(
        store,
        skill_id,
        body.eval_passed,
        body.manual_flag,
        body.mastery_evidence_refs,
    )
    if not success:
        raise HTTPException(
            400,
            "Promotion failed: eval, manual flag, and mastery evidence are required",
        )
    return {"promoted": True, "skill_id": skill_id}
