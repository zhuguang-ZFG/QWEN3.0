"""GI-G-3: Gitee 模力方舟 budget configs and digest lines."""

from __future__ import annotations

GITEE_BACKEND_PREFIX = "gitee_"
GITEE_ACCOUNT_DAILY_LIMIT = 100
GITEE_ACCOUNT_WARN_AT = 0.8

GITEE_DEFAULT_BACKEND_BUDGETS = {
    "daily_limit": 100,
    "warn_at": 0.8,
}


def register_gitee_budgets(registry: dict, budget_config_cls) -> None:
    """Register per-backend budgets for any existing gitee_* keys."""
    try:
        from backends_registry import BACKENDS
    except ImportError:
        BACKENDS = {}
    for name in sorted(BACKENDS):
        if name.startswith(GITEE_BACKEND_PREFIX):
            registry[name] = budget_config_cls(**GITEE_DEFAULT_BACKEND_BUDGETS)


def _bm():
    import budget_manager as bm

    return bm


def _gitee_backends() -> list[str]:
    bm = _bm()
    return sorted(b for b in bm.BACKEND_BUDGETS if b.startswith(GITEE_BACKEND_PREFIX))


def get_gitee_pool_usage() -> tuple[int, int]:
    bm = _bm()
    with bm._lock:
        bm._check_reset()
        used = sum(bm._usage.get(b, 0) for b in _gitee_backends())
    return used, GITEE_ACCOUNT_DAILY_LIMIT


def get_gitee_pool_status() -> str:
    used, limit = get_gitee_pool_usage()
    if limit <= 0:
        return "normal"
    ratio = used / limit
    if ratio >= 1.0:
        return "exhausted"
    if ratio >= GITEE_ACCOUNT_WARN_AT:
        return "warning"
    return "normal"


def get_gitee_summary_lines(usage_snapshot: dict[str, int]) -> list[str]:
    used, limit = get_gitee_pool_usage()
    lines = [f"pool: {used}/{limit} ({get_gitee_pool_status()})"]
    bm = _bm()
    for backend in _gitee_backends():
        cfg = bm.BACKEND_BUDGETS[backend]
        u = usage_snapshot.get(backend, 0)
        status = bm.get_budget_status(backend)
        lines.append(f"{backend}: {u}/{cfg.daily_limit} ({status})")
    return lines
