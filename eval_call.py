"""Eval call_fn factory (M6: FRP path retired — all backends cloud-native)."""

from __future__ import annotations

from collections.abc import Callable


def make_eval_call_fn() -> Callable[[str, list[dict], int], str]:
    import http_caller

    def call_fn(backend: str, messages: list[dict], max_tokens: int) -> str:
        return http_caller.call_api(backend, messages, max_tokens)

    return call_fn
