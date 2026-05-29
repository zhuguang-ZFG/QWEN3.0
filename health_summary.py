"""Backend health summary for operator surfaces (Telegram / CLI)."""

from __future__ import annotations

from health_state import get_health_map


def summarize_backend_health() -> dict[str, int | str]:
    """Merge configured backends with health map (default healthy)."""
    try:
        from backends_registry import BACKENDS

        names = sorted(BACKENDS.keys())
    except ImportError:
        hmap = get_health_map()
        counts = _count_states(hmap.values())
        return {
            "total": len(hmap),
            "tracked": len(hmap),
            "warmup": len(hmap) == 0,
            **counts,
        }

    hmap = get_health_map()
    states = [hmap.get(name, "healthy") for name in names]
    counts = _count_states(states)
    return {
        "total": len(names),
        "tracked": len(hmap),
        "warmup": len(hmap) == 0,
        **counts,
    }


def format_backend_health_line(summary: dict[str, int | str]) -> str:
    healthy = summary.get("healthy", 0)
    degraded = summary.get("degraded", 0)
    dead = summary.get("dead", 0)
    suspicious = summary.get("suspicious", 0)
    total = summary.get("total", 0)
    tracked = summary.get("tracked", 0)
    parts = [f"{healthy} healthy", f"{degraded} degraded", f"{dead} dead"]
    if suspicious:
        parts.append(f"{suspicious} suspicious")
    line = f"Backends: {total} total — {', '.join(parts)}"
    if summary.get("warmup") and total:
        line += f"\n(warmup: {tracked} tracked since restart; others assumed healthy)"
    return line


def _count_states(states) -> dict[str, int]:
    counts = {"healthy": 0, "degraded": 0, "dead": 0, "suspicious": 0}
    for state in states:
        key = state if state in counts else "healthy"
        counts[key] = counts.get(key, 0) + 1
    return counts
