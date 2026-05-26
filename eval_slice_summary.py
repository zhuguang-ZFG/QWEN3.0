"""Summarize latest coding-backend eval JSON for operators."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"


def latest_scores_path(data_dir: Path | None = None, *, full: bool = False) -> Path | None:
    """Return newest eval JSON (quick vs full-11)."""
    base = data_dir or DEFAULT_DATA_DIR
    if not base.is_dir():
        return None

    candidates: list[Path] = []
    for path in base.glob("coding_backend_scores*.json"):
        name = path.name
        is_full = "_full_" in name or name == "coding_backend_scores_full.json"
        if full and not is_full:
            continue
        if not full and is_full:
            continue
        candidates.append(path)

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def summarize_eval_json(path: Path, *, top_n: int = 5) -> str:
    """Build a compact ranking summary from eval JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        return f"{path.name}: empty"

    by_backend: dict[str, list[dict]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        backend = str(row.get("backend") or "?")
        by_backend.setdefault(backend, []).append(row)

    ranked: list[tuple[str, float, int, int, int]] = []
    for backend, rows in by_backend.items():
        scores = [float(r.get("score") or 0) for r in rows]
        passes = sum(1 for r in rows if r.get("ok"))
        latencies = [int(r.get("latency_ms") or 0) for r in rows]
        avg_score = statistics.mean(scores) if scores else 0.0
        avg_latency = int(statistics.mean(latencies)) if latencies else 0
        ranked.append((backend, avg_score, passes, len(rows), avg_latency))

    ranked.sort(key=lambda item: (-item[1], item[4]))
    lines = [f"Eval 摘要 ({path.name})", f"backends={len(ranked)} runs={len(raw)}"]
    for backend, avg_score, passes, total, avg_ms in ranked[:top_n]:
        lines.append(
            f"· {backend}: avg={avg_score:.0f} pass={passes}/{total} {avg_ms}ms"
        )
    if len(ranked) > top_n:
        lines.append(f"… +{len(ranked) - top_n} more")
    return "\n".join(lines)
