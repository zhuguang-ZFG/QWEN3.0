"""Quota and stability aware backend scoring for LiMa routing."""

from __future__ import annotations

import budget_manager

TERMINAL_STATES = {
    "auth_expired",
    "manual_refresh_required",
    "quota_exhausted",
}

# M6: DDG backends deleted — no unproven web adapters remain
UNPROVEN_WEB_ADAPTERS: set[str] = set()

CODING_BACKENDS = {
    "scnet_ds_flash",
    "scnet_qwen235b",
    "scnet_qwen30b",
    "scnet_ds_pro",
    "github_gpt4o",
    "github_gpt4o_mini",
    "github_codestral",
    "cf_qwen_coder",
    "cfai_qwen_coder",
    "or_gptoss_120b",
    "mistral_large",
    "mistral_devstral",
    "cerebras_gptoss",
    "groq_gptoss",
}

FAST_CHAT_BACKENDS = {
    "longcat_lite",
    "groq_gptoss_20b",
    "groq_gptoss",
    "cerebras_gptoss",
    "cf_llama70b",
    "cfai_llama70b",
    "google_flash",
    "google_flash_lite",
}


def is_terminal_state(state: dict | None) -> bool:
    return bool(state and state.get("state") in TERMINAL_STATES)


def is_unproven_web_adapter(backend: str) -> bool:
    return backend in UNPROVEN_WEB_ADAPTERS


def is_selectable(backend: str, request_type: str,
                  state: dict | None = None) -> bool:
    if is_terminal_state(state):
        return False
    if request_type == "ide" and is_unproven_web_adapter(backend):
        return False
    return True


def _norm_score(score: float) -> float:
    return max(0.0, min(float(score), 100.0)) / 100.0


def latency_score(latency_ms: float) -> float:
    if latency_ms <= 500:
        return 1.0
    if latency_ms >= 5000:
        return 0.0
    return 1.0 - ((latency_ms - 500.0) / 4500.0)


def stability_score(state: dict | None) -> float:
    if not state or state.get("state") in (None, "ok"):
        return 1.0
    current = state.get("state")
    if current == "rate_limited":
        return 0.25
    if current == "timeout":
        return 0.35
    if current == "provider_error":
        return 0.45
    return 0.0 if current in TERMINAL_STATES else 0.6


def task_fit_score(backend: str, request_type: str, scenario: str = "") -> float:
    if request_type == "ide":
        if backend in UNPROVEN_WEB_ADAPTERS:
            return 0.0
        return 1.0 if backend in CODING_BACKENDS else 0.7
    if scenario == "coding" or request_type == "code":
        return 1.0 if backend in CODING_BACKENDS else 0.45
    if request_type in ("chat", "chat_fast"):
        return 1.0 if backend in FAST_CHAT_BACKENDS else 0.7
    return 0.6


def effective_score(backend: str, request_type: str, scenario: str = "",
                    *, health_score: float = 50.0,
                    state: dict | None = None,
                    avg_latency_ms: float = 1000.0,
                    remaining_quota_score: float | None = None,
                    quality_trend_score: float = 1.0) -> float:
    quota_score = (
        budget_manager.get_remaining_quota_score(backend)
        if remaining_quota_score is None else remaining_quota_score
    )
    score = (
        _norm_score(health_score) * 0.35
        + stability_score(state) * 0.25
        + latency_score(avg_latency_ms) * 0.15
        + max(0.0, min(quota_score, 1.0)) * 0.10
        + task_fit_score(backend, request_type, scenario) * 0.05
        + max(0.0, min(quality_trend_score, 2.0)) * 0.10
    )
    return round(score, 6)


def rank_backends(backends: list[str], request_type: str, scenario: str = "",
                  *, health_scores: dict[str, float] | None = None,
                  states: dict[str, dict] | None = None,
                  latency_map: dict[str, float] | None = None,
                  quality_trends: dict[str, float] | None = None) -> list[str]:
    health_scores = health_scores or {}
    states = states or {}
    latency_map = latency_map or {}
    quality_trends = quality_trends or {}

    def key(item: tuple[int, str]) -> tuple[float, int]:
        idx, backend = item
        return (
            -effective_score(
                backend,
                request_type,
                scenario,
                health_score=health_scores.get(backend, 50.0),
                state=states.get(backend),
                avg_latency_ms=latency_map.get(backend, 1000.0),
                quality_trend_score=quality_trends.get(backend, 1.0),
            ),
            idx,
        )

    return [backend for _, backend in sorted(enumerate(backends), key=key)]
