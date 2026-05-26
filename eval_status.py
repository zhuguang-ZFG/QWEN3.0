"""Operator eval dashboard for Telegram /evalstatus."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from eval_slice_summary import latest_scores_path

ROOT = Path(__file__).resolve().parent

# Often score 0 on VPS localhost when large pool is on Windows FRP.
_LARGE_ZERO_HINT = frozenset(
    {"scnet_large_ds_pro", "scnet_large_ds_flash", "stock_kimi_k2"}
)


def _age_label(path: Path) -> str:
    age_s = max(0, time.time() - path.stat().st_mtime)
    if age_s < 3600:
        return f"{int(age_s // 60)}m ago"
    if age_s < 86400:
        return f"{int(age_s // 3600)}h ago"
    return f"{int(age_s // 86400)}d ago"


def _mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def eval_file_lines(data_dir: Path | None = None) -> list[str]:
    base = data_dir or (ROOT / "data")
    lines = ["Eval 数据文件"]
    for label, full in (("quick", False), ("full-11", True)):
        path = latest_scores_path(base, full=full)
        if path:
            lines.append(
                f"· {label}: {path.name} ({_age_label(path)}, {_mtime_iso(path)})"
            )
        else:
            lines.append(f"· {label}: （无）")
    return lines


def large_eval_hint_lines(data_dir: Path | None = None) -> list[str]:
    from eval_pool_gate import average_scores_from_path

    base = data_dir or (ROOT / "data")
    path = latest_scores_path(base, full=True)
    if not path:
        return []
    try:
        scores = average_scores_from_path(path)
    except (OSError, ValueError):
        return []
    zeros = sorted(b for b in _LARGE_ZERO_HINT if scores.get(b, -1) == 0)
    if not zeros:
        return []
    from eval_preflight import eval_base_url

    return [
        "Large/Stock 0 分提示",
        f"· {', '.join(zeros)} avg=0（VPS localhost 可能不可达）",
        "· full eval 可设 LIMA_EVAL_BASE_URL=FRP/8088 路径",
        f"· 当前 base={eval_base_url()}",
    ]


def build_eval_status(
    data_dir: Path | None = None,
    *,
    eval_busy: bool = False,
) -> str:
    from eval_notify import schedule_status_lines
    from eval_pool_gate import demoted_backends, load_eval_averages, pool_gate_enabled
    from eval_preflight import check_eval_health, eval_base_url
    from eval_quiet import eval_quiet_active

    base = data_dir or (ROOT / "data")
    lines = ["Eval 运维总览"]
    lines.extend(schedule_status_lines())
    if eval_busy:
        lines.append("manual_eval=运行中")
    if eval_quiet_active():
        lines.append("eval_quiet=1（告警静默）")

    ok, detail = check_eval_health()
    lines.append(
        f"preflight={'ok' if ok else 'FAIL'} ({detail}) base={eval_base_url()}"
    )
    lines.extend(eval_file_lines(base))

    hint = large_eval_hint_lines(base)
    if hint:
        lines.extend(hint)

    if pool_gate_enabled():
        scores = load_eval_averages(base)
        blocked = sorted(demoted_backends(base))
        from eval_pool_gate import min_avg_score

        lines.append(f"pool gate demoted={len(blocked)} min={min_avg_score():g}")
        for name in blocked[:4]:
            lines.append(f"· {name}: avg={scores.get(name, 0):.0f}")
        if len(blocked) > 4:
            lines.append(f"… +{len(blocked) - 4} more（/poolgate 查看全部）")
    else:
        lines.append("pool gate=关闭")

    return "\n".join(lines)
