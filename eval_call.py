"""Eval call_fn factory — direct http_caller or FRP/Windows router for local proxies."""

from __future__ import annotations

from typing import Callable


def make_eval_call_fn() -> Callable[[str, list[dict], int], str]:
    from eval_pinned_call import call_pinned_backend
    from eval_topology import call_via_router, needs_via_router

    def call_fn(backend: str, messages: list[dict], max_tokens: int) -> str:
        if needs_via_router(backend):
            return call_via_router(backend, messages, max_tokens)
        final_backend, answer = call_pinned_backend(backend, messages, max_tokens)
        if final_backend == "exhausted" or not answer.strip():
            raise RuntimeError(f"eval pinned call failed: {backend}")
        return answer

    return call_fn
