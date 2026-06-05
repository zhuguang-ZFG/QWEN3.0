"""Legacy sync HTTP backend calls extracted from smart_router (CQ-014 slice 7).

Submodules (CQ-096): router_http_body, router_http_scnet, router_http_vision.
Prefer http_caller for new production code — see docs/REQUEST_PIPELINE_AUTHORITY.md.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

_log = logging.getLogger(__name__)

from backends import BACKENDS, GFW_BACKENDS
from response_cleaner import clean_response
from router_circuit_breaker import cb_allow, cb_record
from router_http_body import UNAVAILABLE_USER_MESSAGE, build_request_body
from router_http_scnet import call_scnet_chunked as _call_scnet_chunked
from router_http_vision import call_cf_vision, has_vision_content

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"
GFW_PROXY_URL = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")

# Back-compat aliases for smart_router and tests
_build_request_body = build_request_body
_call_cf_vision = call_cf_vision
_has_vision_content = has_vision_content


def _get_opener(name: str):
    if name in GFW_BACKENDS:
        proxy = urllib.request.ProxyHandler(
            {"http": GFW_PROXY_URL, "https": GFW_PROXY_URL}
        )
        return urllib.request.build_opener(proxy)
    return None


def _ide_system_prompt(ide: str) -> str:
    from router_http_body import _ide_system_prompt as _prompt

    return _prompt(ide)


def call_api(name, msgs, mt=1024, ide="unknown"):
    if os.environ.get("LIMA_ROUTER_HTTP_HTTPX", "1").strip().lower() not in ("0", "false", "no"):
        try:
            import http_caller

            started = time.time()
            answer = http_caller.call_api(name, msgs, mt, ide=ide)
            if answer and not (
                isinstance(answer, str)
                and (answer.startswith("[ERR]") or "暂时不可用" in answer)
            ):
                cb_record(name, True, int((time.time() - started) * 1000))
                return answer
            cb_record(name, False)
        except Exception as exc:
            _log.debug("router_http http_caller delegation failed: %s", type(exc).__name__)

    if not cb_allow(name):
        if DEBUG:
            print(f"[CB] {name}: blocked by circuit breaker", file=sys.stderr)
        return None
    started = time.time()
    backend = BACKENDS.get(name)
    if not backend or not backend["key"]:
        cb_record(name, False)
        return f"[ERR] Backend {name} unavailable (no key)"

    if name == "cf_vision" and _has_vision_content(msgs):
        return _call_cf_vision(msgs, mt, started)

    if name.startswith("scnet_"):
        return _call_scnet_chunked(name, msgs, mt, started)

    payload, headers, fmt, timeout = build_request_body(name, msgs, mt, ide, stream=False)
    if payload is None:
        cb_record(name, False)
        return f"[ERR] Backend {name} not found"
    try:
        request = urllib.request.Request(backend["url"], data=payload, headers=headers)
        opener = _get_opener(name)
        if opener:
            with opener.open(request, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
        else:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
        if fmt == "anthropic":
            answer = (
                payload["content"][0].get("text", "")
                or payload["content"][0].get("thinking", "")
                or json.dumps(payload, ensure_ascii=False)
            )
        else:
            message = payload["choices"][0]["message"]
            answer = (
                message.get("content")
                or message.get("reasoning_content")
                or message.get("reasoning")
                or json.dumps(payload, ensure_ascii=False)
            )
        cb_record(name, True, int((time.time() - started) * 1000))
        return clean_response(answer, name)
    except Exception as exc:
        _log.warning("%s call failed: %s", name, type(exc).__name__)
        cb_record(name, False)
        return UNAVAILABLE_USER_MESSAGE


def call_api_stream(name, msgs, mt=1024, ide="unknown"):
    if not cb_allow(name):
        if DEBUG:
            print(f"[CB] {name}: blocked by circuit breaker (stream)", file=sys.stderr)
        yield UNAVAILABLE_USER_MESSAGE
        return
    backend = BACKENDS.get(name)
    if not backend or not backend["key"]:
        yield f"[ERR] Backend {name} unavailable (no key)"
        return

    payload, headers, fmt, timeout = build_request_body(name, msgs, mt, ide, stream=True)
    if payload is None:
        yield f"[ERR] Backend {name} not found"
        return

    started = time.time()
    buffer = b""
    try:
        request = urllib.request.Request(backend["url"], data=payload, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line_end = buffer.index(b"\n")
                    line = buffer[:line_end].decode("utf-8", errors="replace").strip()
                    buffer = buffer[line_end + 1 :]
                    if not line:
                        continue
                    if fmt == "openai":
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                                _log.debug("openai stream chunk skipped: %s", type(exc).__name__)
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError as exc:
                            _log.debug("anthropic stream chunk skipped: %s", type(exc).__name__)
        cb_record(name, True, int((time.time() - started) * 1000))
    except Exception as exc:
        if DEBUG:
            print(f"[STREAM] {name} error: {exc}", file=sys.stderr)
        cb_record(name, False)
        yield UNAVAILABLE_USER_MESSAGE
