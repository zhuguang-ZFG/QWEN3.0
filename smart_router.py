#!/usr/bin/env python3
"""DEPRECATED — legacy compatibility facade only.

All production callers migrated to routing_engine / routing_facade as of 2026-06-07.
Remaining production imports: 0 (verified by CI gate test_no_smart_router_imports_in_production).

Do **not** add new ``import smart_router`` in production code.
Use instead:

- ``routing_engine.route`` — authoritative routing
- ``http_caller`` — sync/async HTTP
- ``routing_facade`` — classify/intent/status helpers
- ``router_classifier`` / ``router_image`` / ``router_intent`` — direct APIs
- ``local_router`` — ``call_local`` / ``warmup_router_model``
- ``routing_constants`` — ``ROUTE`` / ``PUBLIC_MODEL_NAME``
- ``distill_queue`` — distill logging

Enforced by ``tests/test_ci_gates.py::test_no_smart_router_imports_in_production``.
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[reportAttributeAccessIssue]

from dotenv import load_dotenv

load_dotenv()

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"

# ── Slice 4/5: local router + constants ─────────────────────────────────────
# ── Backends registry ─────────────────────────────────────────────────────────
from backends import BACKENDS, GFW_BACKENDS, THINKING_BACKENDS, VISION_BACKENDS

# ── Slice 3: distill queue (no duplicate implementation here) ───────────────
from distill_queue import DISTILL_QUEUE_DIR, log_to_distill_queue
from local_router import call_local, warmup_router_model
from response_cleaner import clean_response

# ── Extracted router_* modules (re-export for scripts/tests) ──────────────────
from router_circuit_breaker import cb_allow, cb_record, cb_status
from router_classifier import RULES, analyze, rule_classify, signal_classify
from router_http import (
    GFW_PROXY_URL,
    _build_request_body,
    _call_cf_vision,
    _get_opener,
    call_api,
    call_api_stream,
)
from router_image import detect_image_intent
from router_intent import detect_thinking_intent, get_thinking_backend
from router_prompt import FRAGMENT_DIR, SYS, assemble_prompt
from routing_constants import PUBLIC_MODEL_NAME, ROUTE
from vision_handler import (
    VISION_SYSTEM_PROMPT,
    convert_openai_vision_to_anthropic,
    detect_vision_request,
)

_log_to_distill_queue = log_to_distill_queue  # back-compat alias
_has_vision_content = detect_vision_request  # back-compat alias

__all__ = [
    "DEBUG",
    "PUBLIC_MODEL_NAME",
    "ROUTE",
    "BACKENDS",
    "GFW_BACKENDS",
    "THINKING_BACKENDS",
    "VISION_BACKENDS",
    "analyze",
    "rule_classify",
    "signal_classify",
    "RULES",
    "detect_thinking_intent",
    "get_thinking_backend",
    "detect_image_intent",
    "call_api",
    "call_api_stream",
    "call_local",
    "warmup_router_model",
    "cb_allow",
    "cb_record",
    "cb_status",
    "clean_response",
    "DISTILL_QUEUE_DIR",
    "log_to_distill_queue",
    "_log_to_distill_queue",
    "_has_vision_content",
    "detect_vision_request",
]
