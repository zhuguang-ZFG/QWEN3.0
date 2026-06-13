"""Pinned-backend eval calls via routing_executor (health + budget telemetry)."""

from __future__ import annotations

import http_caller
from routing_executor import execute

EVAL_SCENARIO = "eval"
EVAL_REQUEST_TYPE = "eval"


def call_pinned_backend(
    backend: str,
    messages: list[dict],
    max_tokens: int,
) -> tuple[str, str]:
    """Call one named backend through routing_executor (no select/route)."""

    def _call_fn(name: str, msgs: list[dict], mt: int) -> str:
        return http_caller.call_api(name, msgs, mt)

    final_backend, answer, _errors = execute(
        [backend],
        _call_fn,
        messages,
        max_tokens,
        scenario=EVAL_SCENARIO,
        request_type=EVAL_REQUEST_TYPE,
    )
    return final_backend, answer or ""
