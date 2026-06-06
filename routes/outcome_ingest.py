"""Internal outcome ingestion endpoint — called by CI, smoke scripts, Telegram.

POST /internal/v1/outcome
  Body: {"source": "ci", "event_type": "workflow_run", "outcome": "success|failure",
         "task_id": "", "summary": "", "tags": []}

Protected by LIMA_API_KEY (same as other internal endpoints).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.post("/outcome", dependencies=[Depends(require_private_api_key)])
async def ingest_outcome(request: Request):
    """Record an outcome event from an external source (CI, smoke, Telegram)."""
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("operation failed: %s", exc)
        return JSONResponse({"error": "JSON body required"}, status_code=400)

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
