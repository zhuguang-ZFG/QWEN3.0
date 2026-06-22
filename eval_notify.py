"""Local notifications after coding eval runs (periodic or manual hook)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def periodic_notify_enabled() -> bool:
    return os.environ.get("LIMA_PERIODIC_EVAL_NOTIFY", "1").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def periodic_full_eval() -> bool:
    return os.environ.get("LIMA_PERIODIC_CODING_EVAL_FULL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _build_message(*, code: int, quick: bool, source: str) -> str:
    from eval_slice_summary import latest_scores_path, summarize_eval_json

    label = "quick" if quick else "full-11"
    lines = [f"[Eval] {source} {label} exit={code}"]
    if code != 0:
        return "\n".join(lines)

    path = latest_scores_path(ROOT / "data", full=not quick)
    if path:
        try:
            top = 5 if quick else 11
            lines.append(summarize_eval_json(path, top_n=top))
        except Exception:
            logger.warning("eval notify summary failed", exc_info=True)

    try:
        from eval_pool_gate import demoted_backends, load_eval_averages, pool_gate_enabled

        if pool_gate_enabled():
            blocked = sorted(demoted_backends(ROOT / "data"))
            scores = load_eval_averages(ROOT / "data")
            lines.append(f"pool gate demoted={len(blocked)}")
            for name in blocked[:5]:
                lines.append(f"· {name}: avg={scores.get(name, 0):.0f}")
    except Exception:
        logger.warning("pool gate summary skipped", exc_info=True)

    return "\n".join(lines)


def notify_eval_finished(*, code: int, quick: bool, source: str = "periodic") -> None:
    """Record eval completion locally."""
    if source == "periodic" and not periodic_notify_enabled():
        return

    text = _build_message(code=code, quick=quick, source=source)
    logger.info("eval finished source=%s quick=%s code=%s\n%s", source, quick, code, text)


def schedule_status_lines() -> list[str]:
    import periodic_coding_eval

    lines = [
        "Eval 周期任务",
        f"LIMA_PERIODIC_CODING_EVAL={'1' if periodic_coding_eval.enabled() else '0'}",
        f"interval_hours={os.environ.get('LIMA_CODING_EVAL_INTERVAL_HOURS', '168')}",
        f"full={'1' if periodic_full_eval() else '0'} (quick only if 0)",
        f"notify={'1' if periodic_notify_enabled() else '0'}",
    ]
    return lines
