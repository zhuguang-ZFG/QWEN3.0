"""CF-G-1: Cloudflare pool, grouped summary, and Telegram budget alerts."""

from __future__ import annotations

CF_ACCOUNT_DAILY_LIMIT = 12000
CF_ACCOUNT_WARN_AT = 0.7
CF_BACKEND_PREFIX = "cf_"

CF_BACKEND_BUDGETS = {
    "cf_qwen_coder": {"daily_limit": 1200, "warn_at": 0.8},
    "cf_llama70b": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_llama4": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_mistral": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_gptoss_120b": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_qwen3_30b": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_glm47": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_gemma4": {"daily_limit": 1000, "warn_at": 0.8},
    "cf_vision": {"daily_limit": 800, "warn_at": 0.7},
    "cf_kimi_k26": {"daily_limit": 800, "warn_at": 0.7},
    "cf_deepseek_r1": {"daily_limit": 800, "warn_at": 0.7},
    "cf_qwq": {"daily_limit": 800, "warn_at": 0.7},
    "cf_nemotron": {"daily_limit": 800, "warn_at": 0.7},
}


def register_cf_google_budgets(registry: dict, budget_config_cls) -> None:
    registry["google_flash"] = budget_config_cls(daily_limit=1000, warn_at=0.8)
    for name, cfg in CF_BACKEND_BUDGETS.items():
        registry[name] = budget_config_cls(**cfg)


def _bm():
    import budget_manager as bm

    return bm


def _cf_backends() -> list[str]:
    bm = _bm()
    return sorted(b for b in bm.BACKEND_BUDGETS if b.startswith(CF_BACKEND_PREFIX))


def _google_backends() -> list[str]:
    bm = _bm()
    return sorted(b for b in bm.BACKEND_BUDGETS if b.startswith("google_"))


def get_cf_pool_usage() -> tuple[int, int]:
    bm = _bm()
    with bm._lock:
        bm._check_reset()
        used = sum(bm._usage.get(b, 0) for b in _cf_backends())
    return used, CF_ACCOUNT_DAILY_LIMIT


def get_cf_pool_status() -> str:
    used, limit = get_cf_pool_usage()
    if limit <= 0:
        return "normal"
    ratio = used / limit
    if ratio >= 1.0:
        return "exhausted"
    if ratio >= CF_ACCOUNT_WARN_AT:
        return "warning"
    return "normal"


def _format_backend_line(backend: str, used: int) -> str:
    bm = _bm()
    cfg = bm.BACKEND_BUDGETS[backend]
    limit = cfg.daily_limit or 0
    status = bm.get_budget_status(backend)
    return f"{backend}: {used}/{limit} ({status})"


def get_usage_summary() -> dict[str, str]:
    bm = _bm()
    with bm._lock:
        bm._check_reset()
        usage_snapshot = dict(bm._usage)

    cf_used, cf_limit = get_cf_pool_usage()
    cf_lines = [f"pool: {cf_used}/{cf_limit} ({get_cf_pool_status()})"]
    for backend in _cf_backends():
        cf_lines.append(_format_backend_line(backend, usage_snapshot.get(backend, 0)))

    google_lines = [
        _format_backend_line(backend, usage_snapshot.get(backend, 0))
        for backend in _google_backends()
    ]
    return {
        "Cloudflare": "\n".join(cf_lines),
        "Google": "\n".join(google_lines) if google_lines else "(none configured)",
    }


def get_total_requests_today() -> int:
    bm = _bm()
    with bm._lock:
        bm._check_reset()
        return sum(bm._usage.values())


def emit_budget_alerts(backend: str, old_used: int, new_used: int) -> None:
    bm = _bm()
    cfg = bm.BACKEND_BUDGETS.get(backend)
    if not cfg or not cfg.daily_limit:
        return
    limit = cfg.daily_limit
    old_ratio = old_used / limit
    new_ratio = new_used / limit
    try:
        import telegram_notify
    except ImportError:
        return
    if old_ratio < 1.0 <= new_ratio:
        telegram_notify.notify_budget_threshold(
            backend=backend, level="exhausted", used=new_used, limit=limit,
        )
    elif old_ratio < cfg.warn_at <= new_ratio:
        telegram_notify.notify_budget_threshold(
            backend=backend, level="warning", used=new_used, limit=limit,
        )


def emit_cf_pool_alerts() -> None:
    used, limit = get_cf_pool_usage()
    if limit <= 0:
        return
    ratio = used / limit
    prev_ratio = (used - 1) / limit if used > 0 else 0.0
    try:
        import telegram_notify
    except ImportError:
        return
    if prev_ratio < CF_ACCOUNT_WARN_AT <= ratio:
        telegram_notify.notify_budget_threshold(
            backend="cf_pool",
            level="pool_warning",
            used=used,
            limit=limit,
            pool_label="cf_*",
        )
    elif prev_ratio < 1.0 <= ratio:
        telegram_notify.notify_budget_threshold(
            backend="cf_pool",
            level="exhausted",
            used=used,
            limit=limit,
            pool_label="cf_*",
        )
