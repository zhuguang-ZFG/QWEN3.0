"""IDE coding pool admission — eval scores + tier evidence + private-code gate."""

from __future__ import annotations

import json
import logging
import os
import statistics
from pathlib import Path
from typing import Any

from eval_pool_gate import (
    demoted_backends,
    filter_coding_pool,
    latest_scores_path,
    load_eval_averages,
    pool_gate_enabled,
)

_log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_TIERS_PATH = _ROOT / "data" / "coding_backend_tiers.json"
_FREE_WEB_PATH = _ROOT / "data" / "free_web_ai_admission.json"

# Plan tiers: fast / primary / strong / fallback → orchestrator pool keys
TIER_TO_POOL = {
    "fast": "fast",
    "primary": "coder",
    "strong": "strong",
    "fallback": "fallback",
}

POOL_TO_TIER = {v: k for k, v in TIER_TO_POOL.items()}

TIER_MIN_SCORE = {
    "fast": 75.0,
    "primary": 70.0,
    "strong": 80.0,
    "fallback": 50.0,
}

_SANDBOX_ADMISSION = {
    "sandbox_only",
    "adapter_draft_pending",
    "rejected",
    "blocked",
}


def evidence_gate_enabled() -> bool:
    return os.environ.get("LIMA_IDE_POOL_EVIDENCE_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def load_tier_assignments(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load backend → tier metadata from coding_backend_tiers.json."""
    target = path or _TIERS_PATH
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("tier assignments unreadable path=%s err=%s", target, type(exc).__name__)
        return {}
    backends = raw.get("backends") if isinstance(raw, dict) else raw
    if not isinstance(backends, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, meta in backends.items():
        if isinstance(meta, dict) and str(key).strip():
            out[str(key)] = meta
    return out


def write_tier_assignments(
    assignments: dict[str, dict[str, Any]],
    path: Path | None = None,
    *,
    source: str = "eval_coding_backends",
) -> Path:
    target = path or _TIERS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source,
        "backends": assignments,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def aggregate_backend_stats(results: list[dict]) -> dict[str, dict[str, Any]]:
    """Aggregate per-backend avg score, pass rate, and latency from eval rows."""
    by_backend: dict[str, list[dict]] = {}
    for row in results:
        if not isinstance(row, dict):
            continue
        backend = str(row.get("backend") or "").strip()
        if backend:
            by_backend.setdefault(backend, []).append(row)

    stats: dict[str, dict[str, Any]] = {}
    for backend, rows in by_backend.items():
        scores = [float(r.get("score") or 0) for r in rows]
        latencies = [int(r.get("latency_ms") or 0) for r in rows]
        passes = sum(1 for r in rows if r.get("ok"))
        total = len(rows)
        avg_score = statistics.mean(scores) if scores else 0.0
        avg_latency = int(statistics.mean(latencies)) if latencies else 0
        pass_rate = passes / total if total else 0.0
        stats[backend] = {
            "avg_score": round(avg_score, 1),
            "avg_latency_ms": avg_latency,
            "passes": passes,
            "cases": total,
            "pass_rate": round(pass_rate, 3),
        }
    return stats


def assign_tiers_from_stats(stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Promote backends into fast/primary/strong/fallback from eval aggregates."""
    ranked = sorted(
        stats.items(),
        key=lambda item: (-item[1]["avg_score"], item[1]["avg_latency_ms"], item[0]),
    )
    assignments: dict[str, dict[str, Any]] = {}
    for backend, meta in ranked:
        score = float(meta["avg_score"])
        latency = int(meta["avg_latency_ms"])
        pass_rate = float(meta.get("pass_rate") or 0)
        tier = "fallback"
        if score >= TIER_MIN_SCORE["strong"] and pass_rate >= 0.8:
            tier = "strong"
        elif score >= TIER_MIN_SCORE["primary"] and pass_rate >= 0.7:
            tier = "primary"
        elif score >= TIER_MIN_SCORE["fast"] and latency <= 8000 and pass_rate >= 0.6:
            tier = "fast"
        elif score >= TIER_MIN_SCORE["fallback"]:
            tier = "fallback"
        else:
            continue
        assignments[backend] = {
            "tier": tier,
            "pool": TIER_TO_POOL[tier],
            "avg_score": meta["avg_score"],
            "avg_latency_ms": latency,
            "pass_rate": meta["pass_rate"],
            "evidence": "coding_backend_scores",
        }
    return assignments


def build_tiers_from_eval_results(results: list[dict]) -> dict[str, dict[str, Any]]:
    return assign_tiers_from_stats(aggregate_backend_stats(results))


def _registry_private_code_allowed(backend: str) -> bool | None:
    try:
        from backends import BACKENDS

        cfg = BACKENDS.get(backend) or {}
        if "private_code_allowed" in cfg:
            return bool(cfg["private_code_allowed"])
    except ImportError:
        _log.debug("coding_pool_admission: optional module not available", exc_info=True)
    return None


def _free_web_private_code(backend: str) -> bool | None:
    """Map web-style backend keys to free_web_ai_admission.json entries."""
    if not _FREE_WEB_PATH.is_file():
        return None
    try:
        rows = json.loads(_FREE_WEB_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(rows, list):
        return None
    # duck_ai → duck_web style: strip suffixes and match id prefix
    candidates = {backend}
    if backend.endswith("_web"):
        candidates.add(backend[:-4] + "_ai")
    base = backend.replace("_web", "").replace("_code", "")
    candidates.add(base)
    candidates.add(f"{base}_ai")
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "")
        if row_id in candidates or row_id.replace("_ai", "") == base:
            return bool(row.get("private_code_allowed", False))
    return None


def _admission_overlay_allows(backend: str) -> bool:
    try:
        from backend_admission_store import get_enabled_overlays

        for overlay in get_enabled_overlays():
            if overlay.backend_key != backend:
                continue
            if overlay.admission_status in _SANDBOX_ADMISSION:
                return False
            if overlay.private_code_allowed:
                return True
            if overlay.admission_status == "admitted_late_fallback":
                return True
    except ImportError:
        _log.debug("coding_pool_admission: optional module not available", exc_info=True)
    return False


def backend_has_evidence(
    backend: str,
    *,
    tier_assignments: dict[str, dict[str, Any]] | None = None,
    eval_averages: dict[str, float] | None = None,
) -> bool:
    tiers = tier_assignments if tier_assignments is not None else load_tier_assignments()
    if backend in tiers:
        return True
    scores = eval_averages if eval_averages is not None else load_eval_averages()
    if backend in scores:
        return True
    if _admission_overlay_allows(backend):
        return True
    if _registry_private_code_allowed(backend) is True:
        reg_admission = None
        try:
            from backends import BACKENDS

            reg_admission = (BACKENDS.get(backend) or {}).get("admission")
        except ImportError:
            reg_admission = None
        if reg_admission and reg_admission not in _SANDBOX_ADMISSION:
            return True
    return False


def private_code_blocked(backend: str) -> bool:
    """True when backend must not receive private IDE code (sandbox web AI)."""
    web_flag = _free_web_private_code(backend)
    if web_flag is not None:
        return not web_flag
    reg = _registry_private_code_allowed(backend)
    if reg is not None:
        return not reg
    if backend.endswith("_web") and not backend.endswith("_web_code"):
        return True
    return False


def blocked_without_evidence(
    backend: str,
    *,
    tier_assignments: dict[str, dict[str, Any]] | None = None,
    eval_averages: dict[str, float] | None = None,
) -> bool:
    if not evidence_gate_enabled():
        return False
    tiers = tier_assignments if tier_assignments is not None else load_tier_assignments()
    scores = eval_averages if eval_averages is not None else load_eval_averages()
    if not tiers and not scores:
        return False
    return not backend_has_evidence(
        backend,
        tier_assignments=tiers,
        eval_averages=scores,
    )


def filter_ide_coding_pool(
    pool: list[str],
    *,
    pool_tier: str = "",
    data_dir: Path | None = None,
) -> list[str]:
    """Apply eval demotion, evidence gate, and private-code sandbox rules."""
    filtered = filter_coding_pool(pool, data_dir)
    tiers = load_tier_assignments()
    scores = load_eval_averages(data_dir)
    out: list[str] = []
    for name in filtered:
        if private_code_blocked(name):
            continue
        if blocked_without_evidence(name, tier_assignments=tiers, eval_averages=scores):
            continue
        if pool_tier and tiers.get(name, {}).get("pool") not in ("", pool_tier, TIER_TO_POOL.get(pool_tier, pool_tier)):
            # Soft preference: keep if no tier file entry; drop if assigned to different pool
            assigned_pool = tiers.get(name, {}).get("pool")
            want = TIER_TO_POOL.get(pool_tier, pool_tier)
            if assigned_pool and assigned_pool != want and pool_tier in POOL_TO_TIER:
                continue
        out.append(name)
    return out


def tier_pool_from_evidence(tier: str, static_pool: list[str]) -> list[str]:
    """Merge eval-promoted backends for a tier ahead of static POOLS list."""
    want_pool = TIER_TO_POOL.get(tier, tier)
    assignments = load_tier_assignments()
    promoted = [
        name
        for name, meta in assignments.items()
        if meta.get("pool") == want_pool
    ]
    promoted.sort(key=lambda n: (-float(assignments[n].get("avg_score") or 0), n))
    merged: list[str] = []
    for name in promoted + static_pool:
        if name not in merged:
            merged.append(name)
    return filter_ide_coding_pool(merged, pool_tier=tier)


def summarize_admission(data_dir: Path | None = None) -> dict[str, Any]:
    base = data_dir or (_ROOT / "data")
    scores_path = latest_scores_path(base, full=True) or latest_scores_path(base, full=False)
    tiers = load_tier_assignments()
    averages = load_eval_averages(base)
    return {
        "evidence_gate": evidence_gate_enabled(),
        "eval_gate": pool_gate_enabled(),
        "scores_path": scores_path.name if scores_path else None,
        "tier_backends": len(tiers),
        "eval_backends": len(averages),
        "demoted": sorted(demoted_backends(base)),
    }
