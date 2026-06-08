"""Internal outcome ingestion endpoint — called by CI, smoke scripts, and agents.

POST /internal/v1/outcome
  Body: {"source": "ci", "event_type": "workflow_run", "outcome": "success|failure",
         "task_id": "", "summary": "", "tags": []}

Protected by LIMA_API_KEY (same as other internal endpoints).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.post("/outcome", dependencies=[Depends(require_private_api_key)])
async def ingest_outcome(request: Request):
    """Record an outcome event from an external source."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body

    source = str(body.get("source", ""))
    event_type = str(body.get("event_type", ""))
    outcome = str(body.get("outcome", "success"))
    if not source or not event_type:
        return JSONResponse({"error": "source and event_type required"}, status_code=400)

    try:
        from session_memory.outcome_ledger import record

        event_id = record(
            source=source,
            event_type=event_type,
            outcome=outcome,
            task_id=str(body.get("task_id", "")),
            backend=str(body.get("backend", "")),
            scenario=str(body.get("scenario", "")),
            summary=str(body.get("summary", ""))[:500],
            tags=body.get("tags") if isinstance(body.get("tags"), list) else None,
        )
        return JSONResponse({"ok": True, "event_id": event_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
