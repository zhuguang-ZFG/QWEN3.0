"""Tests for http_async — provider semaphore, usage tracking, error handling."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ── Provider resolution ─────────────────────────────────────────────────────
class TestResolveProvider:
    def test_nvidia_prefix(self):
        from http_async import _resolve_provider

        assert _resolve_provider("nvidia_qwen_coder") == "nvidia"

    def test_unknown_prefix(self):
        from http_async import _resolve_provider

        assert _resolve_provider("unknown_backend") is None

    def test_all_pool_prefixes(self):
        """Every KEY_POOL_PREFIXES entry should resolve."""
        from backends_constants import KEY_POOL_PREFIXES
        from http_async import _resolve_provider

        for prefix, provider in KEY_POOL_PREFIXES.items():
            backend = f"{prefix}test_model"
            result = _resolve_provider(backend)
            assert result == provider, f"{backend} should resolve to {provider}, got {result}"


# ── Provider semaphore ──────────────────────────────────────────────────────
class TestProviderSemaphore:
    def test_semaphore_created_for_rate_limited_provider(self):
        from http_async import _get_provider_semaphore, _provider_semaphores

        _provider_semaphores.clear()
        sem = _get_provider_semaphore("nvidia_qwen_coder")
        assert sem is not None
        assert isinstance(sem, asyncio.Semaphore)

    def test_semaphore_none_for_unlimited_provider(self):
        from http_async import _get_provider_semaphore

        sem = _get_provider_semaphore("openai_gpt4")
        assert sem is None

    def test_semaphore_reused(self):
        from http_async import _get_provider_semaphore, _provider_semaphores

        _provider_semaphores.clear()
        sem1 = _get_provider_semaphore("nvidia_qwen_coder")
        sem2 = _get_provider_semaphore("nvidia_llama")
        assert sem1 is sem2  # Same provider → same semaphore


# ── Usage tracking ──────────────────────────────────────────────────────────
class TestUsageTracking:
    def test_get_last_usage_none(self):
        from http_async import _last_usage, get_last_usage

        _last_usage.clear()
        assert get_last_usage("nonexistent_backend") is None

    def test_get_last_usage_after_set(self):
        from http_async import _last_usage, get_last_usage

        _last_usage["test_backend"] = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        usage = get_last_usage("test_backend")
        assert usage["prompt_tokens"] == 100
        assert usage["total_tokens"] == 150
        _last_usage.clear()


# ── call_api_async — error paths ────────────────────────────────────────────
class TestCallApiAsyncErrors:
    @pytest.mark.asyncio
    async def test_unknown_backend_raises(self):
        """Unknown backend raises BackendError."""
        from http_async import call_api_async
        from http_errors import BackendError

        with patch("http_async.BACKENDS", {}), pytest.raises(BackendError, match="unavailable"):
            await call_api_async(
                "nonexistent_backend",
                [{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_cooled_down_backend_raises(self):
        """Cooled-down backend raises BackendError 503."""
        from http_async import call_api_async
        from http_errors import BackendError

        mock_cfg = {"url": "https://api.test.com", "fmt": "openai", "timeout": 10}
        with patch("http_async.BACKENDS", {"test_backend": mock_cfg}):
            with patch("http_async._caller") as mock_caller:
                mock_hc = MagicMock()
                mock_hc._select_key.return_value = ("fake_key", "test")
                mock_hc.health_tracker.is_cooled_down.return_value = True
                mock_caller.return_value = mock_hc

                with pytest.raises(BackendError, match="cooled down"):
                    await call_api_async(
                        "test_backend",
                        [{"role": "user", "content": "hi"}],
                    )


# ── call_raw_async — error paths ────────────────────────────────────────────
class TestCallRawAsyncErrors:
    @pytest.mark.asyncio
    async def test_unknown_backend_raises(self):
        from http_async import call_raw_async
        from http_errors import BackendError

        with patch("http_async.BACKENDS", {}), pytest.raises(BackendError, match="unavailable"):
            await call_raw_async("nonexistent", b'{"test": true}')

    @pytest.mark.asyncio
    async def test_no_key_raises(self):
        from http_async import call_raw_async
        from http_errors import BackendError

        mock_cfg = {"url": "https://api.test.com", "fmt": "openai"}
        with patch("http_async.BACKENDS", {"test_backend": mock_cfg}):
            with patch("http_async._caller") as mock_caller:
                mock_hc = MagicMock()
                mock_hc._select_key.return_value = (None, None)
                mock_caller.return_value = mock_hc

                with pytest.raises(BackendError, match="unavailable"):
                    await call_raw_async("test_backend", b'{"test": true}')
