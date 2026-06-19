"""Ops backend lifecycle endpoints."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter()
logger = logging.getLogger(__name__)
_BACKEND_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


def valid_backend_name(value: Any) -> str:
    backend = value.strip() if isinstance(value, str) else ""
    if not backend or not _BACKEND_NAME_RE.match(backend):
        return ""
    return backend


@router.post("/backends/reactivate", dependencies=[Depends(require_private_api_key)])
async def ops_backend_reactivate(request: Request) -> JSONResponse:
    """Manually reactivate a backend after fresh operator evidence."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = valid_backend_name(body.get("backend"))
    evidence = str(body.get("evidence", "")).strip()
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    if not evidence:
        return JSONResponse({"error": "evidence required"}, status_code=400)
    try:
        from backend_retirement import reactivate

        reactivate(backend)
    except ImportError:
        return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend reactivation failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend reactivation failed"}, status_code=500)
    logger.warning("manual backend reactivation backend=%s evidence=%s", backend, evidence[:120])
    return JSONResponse({"ok": True, "backend": backend, "status": "healthy"})


@router.post("/backends/probe", dependencies=[Depends(require_private_api_key)])
async def ops_backend_probe(request: Request) -> JSONResponse:
    """Probe one backend and record the evidence before any recovery action."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = valid_backend_name(body.get("backend"))
    reactivate_on_success = bool(body.get("reactivate_on_success", False))
    timeout_raw = body.get("timeout_sec", 25)
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    try:
        timeout_sec = float(timeout_raw)
    except (TypeError, ValueError):
        return JSONResponse({"error": "valid timeout_sec required"}, status_code=400)
    if timeout_sec <= 0 or timeout_sec > 120:
        return JSONResponse({"error": "timeout_sec must be between 0 and 120"}, status_code=400)
    try:
        from backend_probe_loop import probe_and_record_backend

        result = probe_and_record_backend(
            backend,
            ignore_cooldown=True,
            timeout_sec=timeout_sec,
        )
    except ImportError:
        return JSONResponse({"error": "backend_probe_loop module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend probe failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend probe failed"}, status_code=500)

    status = str(result.get("status", "unknown"))
    healthy = status == "healthy"
    reactivated = False
    if healthy and reactivate_on_success:
        try:
            from backend_retirement import reactivate

            reactivate(backend)
            reactivated = True
        except ImportError:
            return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
        except Exception as exc:
            logger.warning("probe-based backend reactivation failed backend=%s: %s", backend, type(exc).__name__)
            return JSONResponse({"error": "backend reactivation failed"}, status_code=500)

    if healthy:
        recommended = "reactivated" if reactivated else "reactivate_with_evidence"
    elif status == "unknown":
        recommended = "check_backend_name"
    else:
        recommended = "keep_retired"

    return JSONResponse(
        {
            "ok": healthy,
            "backend": backend,
            "probe": result,
            "reactivated": reactivated,
            "recommended_action": recommended,
        }
    )


@router.post("/backends/retire", dependencies=[Depends(require_private_api_key)])
async def ops_backend_retire(request: Request) -> JSONResponse:
    """Manually remove a backend from routing until an operator reactivates it."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = valid_backend_name(body.get("backend"))
    reason = str(body.get("reason", "")).strip()
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    if not reason:
        return JSONResponse({"error": "reason required"}, status_code=400)
    try:
        from backend_retirement import STATUS_RETIRED, apply_retirement

        apply_retirement(
            {
                "action": "retire",
                "backend": backend,
                "reason": f"manual operator override: {reason[:200]}",
                "status": STATUS_RETIRED,
            }
        )
    except ImportError:
        return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend retirement failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend retirement failed"}, status_code=500)
    return JSONResponse({"ok": True, "backend": backend, "status": "retired"})
