"""Tests for AI provider auto-fallback routing (try_backends)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from device_gateway.model_routing import (
    DEVICE_ROLE_PREFERENCES,
    try_backends,
    _auto_fallback_enabled,
)


# ── helpers ─────────────────────────────────────────────────────────────────

ROUTE_ROLE = "device_draw"  # has 2 alternatives: dashscope_wanx, dashscope_flux
_ALTS = DEVICE_ROLE_PREFERENCES[ROUTE_ROLE]
assert len(_ALTS) == 2, "test assumes device_draw has exactly 2 alternatives"


def _make_execute(script: dict[str, bool], attempts: list[dict[str, Any]]):
    """Return an async execute_fn that succeeds/fails per *script*.

    *script* maps backend name → True (succeed) or False (fail).
    *attempts* is mutated in-place recording each call.
    """

    async def execute_fn(backend: dict[str, Any]) -> str:
        backend_name = backend.get("backend", "")
        attempts.append(backend)
        if script.get(backend_name, False):
            return f"ok-{backend_name}"
        raise RuntimeError(f"boom-{backend_name}")

    return execute_fn


def _make_timeout_execute(script: dict[str, str], attempts: list[dict[str, Any]]):
    """Return an execute_fn that may sleep (timeout) or fail or succeed.

    *script* maps backend name → "ok" | "fail" | "timeout".
    """
    timeout_value = 0.1  # very short so sleep(1) triggers TimeoutError

    async def execute_fn(backend: dict[str, Any]) -> str:
        backend_name = backend.get("backend", "")
        attempts.append(backend)
        mode = script.get(backend_name, "fail")
        if mode == "ok":
            return f"ok-{backend_name}"
        if mode == "timeout":
            await asyncio.sleep(10)  # will be cancelled by wait_for
        raise RuntimeError(f"boom-{backend_name}")

    return execute_fn


# ── tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_backend_success(monkeypatch):
    """Fallback ON + first backend succeeds → return first result, attempts=1."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")
    assert _auto_fallback_enabled()

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: True, _ALTS[1]["backend"]: False}
    result = await try_backends(ROUTE_ROLE, _make_execute(script, attempts))

    assert result == f"ok-{_ALTS[0]['backend']}"
    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_first_fails_idempotent_fallback(monkeypatch, caplog):
    """Fallback ON + first fails + idempotent → return second result, attempts=2."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: False, _ALTS[1]["backend"]: True}

    with caplog.at_level(logging.WARNING):
        result = await try_backends(ROUTE_ROLE, _make_execute(script, attempts), idempotent=True)

    assert result == f"ok-{_ALTS[1]['backend']}"
    assert len(attempts) == 2
    assert any("fallback continue" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_first_fails_non_idempotent_raises(monkeypatch, caplog):
    """Fallback ON + first fails + non-idempotent → raise immediately, attempts=1."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: False, _ALTS[1]["backend"]: True}

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError, match=f"boom-{_ALTS[0]['backend']}"):
            await try_backends(ROUTE_ROLE, _make_execute(script, attempts), idempotent=False)

    assert len(attempts) == 1
    assert any("fallback stop" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_all_fail_raises_last_exception(monkeypatch, caplog):
    """Fallback ON + idempotent + all fail → raise last exception, attempts=2."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: False, _ALTS[1]["backend"]: False}

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError, match=f"boom-{_ALTS[1]['backend']}"):
            await try_backends(ROUTE_ROLE, _make_execute(script, attempts), idempotent=True)

    assert len(attempts) == len(_ALTS)


@pytest.mark.asyncio
async def test_fallback_disabled_raises_immediately(monkeypatch):
    """Fallback OFF + first fails → raise immediately, no fallback."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "0")
    assert not _auto_fallback_enabled()

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: False, _ALTS[1]["backend"]: True}

    with pytest.raises(RuntimeError, match=f"boom-{_ALTS[0]['backend']}"):
        await try_backends(ROUTE_ROLE, _make_execute(script, attempts), idempotent=True)

    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_timeout_treated_as_failure(monkeypatch, caplog):
    """Timeout on first backend + idempotent → fallback to second."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: "timeout", _ALTS[1]["backend"]: "ok"}

    with caplog.at_level(logging.WARNING):
        result = await try_backends(
            ROUTE_ROLE,
            _make_timeout_execute(script, attempts),
            idempotent=True,
            timeout=0.1,
        )

    assert result == f"ok-{_ALTS[1]['backend']}"
    assert len(attempts) == 2
    assert any("fallback continue" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_timeout_non_idempotent_raises(monkeypatch, caplog):
    """Timeout on first backend + non-idempotent → raise immediately."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    attempts: list[dict[str, Any]] = []
    script = {_ALTS[0]["backend"]: "timeout", _ALTS[1]["backend"]: "ok"}

    with caplog.at_level(logging.WARNING):
        with pytest.raises(asyncio.TimeoutError):
            await try_backends(
                ROUTE_ROLE,
                _make_timeout_execute(script, attempts),
                idempotent=False,
                timeout=0.1,
            )

    assert len(attempts) == 1
    assert any("fallback stop" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_empty_role_raises_value_error(monkeypatch):
    """Non-existent route_role → ValueError."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    with pytest.raises(ValueError, match="no backends"):
        await try_backends("nonexistent_role", _make_execute({}, []))
