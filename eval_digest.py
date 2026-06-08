"""Merged quick + full eval digest for local operator reports."""

from __future__ import annotations

from pathlib import Path

from eval_slice_summary import latest_scores_path, summarize_eval_json
from eval_status import large_eval_hint_lines

ROOT = Path(__file__).resolve().parent


def build_eval_digest(
    data_dir: Path | None = None,
    *,
    top_quick: int = 3,
    top_full: int = 5,
) -> str:
    from eval_pool_gate import demoted_backends, load_eval_averages, pool_gate_enabled

    base = data_dir or (ROOT / "data")
    quick_path = latest_scores_path(base, full=False)
    full_path = latest_scores_path(base, full=True)

    if not quick_path and not full_path:
        return "尚无 eval JSON（先跑 /evalslice 或 /evalslice full）"

    lines = ["Eval 合并摘要"]
    if quick_path:
        lines.append("— quick —")
        lines.append(summarize_eval_json(quick_path, top_n=top_quick))
    if full_path:
        lines.append("— full-11 —")
        lines.append(summarize_eval_json(full_path, top_n=top_full))

    hint = large_eval_hint_lines(base)
    if hint:
        lines.extend(hint)

    if pool_gate_enabled():
        scores = load_eval_averages(base)
        blocked = sorted(demoted_backends(base))
        lines.append(f"pool gate demoted={len(blocked)}")
        for name in blocked[:5]:
            lines.append(f"· {name}: avg={scores.get(name, 0):.0f}")

    return "\n".join(lines)
