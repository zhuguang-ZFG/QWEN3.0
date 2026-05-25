#!/usr/bin/env python3
"""Smoke prod retrieval injection + admin retrieval trace on LiMa VPS or local."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _request(method: str, url: str, *, headers: dict | None = None, body: dict | None = None, timeout: int = 60):
    data = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        elapsed_ms = int((time.time() - start) * 1000)
        return resp.status, raw, elapsed_ms


def _chat(base: str, api_key: str, query: str) -> tuple[bool, str]:
    url = base.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 64,
        "temperature": 0,
        "stream": False,
    }
    try:
        status, raw, elapsed_ms = _request(
            "POST",
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            body=body,
        )
        ok = status == 200
        print(f"{'OK' if ok else 'FAIL'} chat: HTTP {status} {elapsed_ms}ms")
        if not ok:
            return False, raw[:300]
        data = json.loads(raw)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"  answer_chars={len(content)}")
        return True, content
    except Exception as exc:
        print(f"FAIL chat: {type(exc).__name__}: {str(exc)[:200]}")
        return False, ""


def _admin_traces(base: str, admin_token: str) -> tuple[bool, list[dict]]:
    url = base.rstrip("/") + "/admin/api/retrieval-traces"
    try:
        status, raw, elapsed_ms = _request(
            "GET",
            url,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ok = status == 200
        print(f"{'OK' if ok else 'FAIL'} admin retrieval-traces: HTTP {status} {elapsed_ms}ms")
        if not ok:
            return False, []
        traces = json.loads(raw)
        if not isinstance(traces, list):
            print("FAIL admin retrieval-traces: response is not a list")
            return False, []
        print(f"  trace_count={len(traces)}")
        return True, traces
    except Exception as exc:
        print(f"FAIL admin retrieval-traces: {type(exc).__name__}: {str(exc)[:200]}")
        return False, []


def _ops_traces(base: str, api_key: str) -> tuple[bool, list[dict]]:
    url = base.rstrip("/") + "/v1/ops/metrics"
    try:
        status, raw, elapsed_ms = _request(
            "GET",
            url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        ok = status == 200
        print(f"{'OK' if ok else 'FAIL'} ops metrics: HTTP {status} {elapsed_ms}ms")
        if not ok:
            return False, []
        data = json.loads(raw)
        traces = data.get("retrieval_traces", [])
        if not isinstance(traces, list):
            print("FAIL ops metrics: retrieval_traces missing")
            return False, []
        print(f"  ops_trace_count={len(traces)}")
        return True, traces
    except Exception as exc:
        print(f"FAIL ops metrics: {type(exc).__name__}: {str(exc)[:200]}")
        return False, []


def _trace_hits_prod_module(traces: list[dict]) -> tuple[bool, dict | None]:
    prod_names = {
        "routing_engine.py",
        "routing_classifier.py",
        "routing_selector.py",
        "routing_executor.py",
        "http_caller.py",
        "health_tracker.py",
        "retrieval_injection.py",
    }
    for trace in traces:
        injected = trace.get("injected_text", "") or ""
        entities = trace.get("query_entities", []) or []
        reranked = trace.get("reranked_results", []) or []
        paths = {item.get("path", "") for item in reranked if isinstance(item, dict)}
        blob = injected + " " + " ".join(str(x) for x in entities) + " " + " ".join(paths)
        if any(name in blob for name in prod_names):
            chars = int(trace.get("injected_chars", 0) or 0)
            if chars <= 0 and injected:
                chars = len(injected)
            return True, {
                "injected_chars": chars,
                "entities": entities[:5],
                "paths": sorted(paths)[:5],
            }
    return False, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--api-key", default=os.environ.get("LIMA_API_KEY", "lima-local"))
    parser.add_argument("--admin-token", default=os.environ.get("LIMA_ADMIN_TOKEN", ""))
    parser.add_argument(
        "--query",
        default="Explain how routing_engine.py selects backends using health_tracker.py",
    )
    args = parser.parse_args()

    checks: list[bool] = []

    checks.append(_chat(args.base_url, args.api_key, args.query)[0])

    traces: list[dict] = []
    if args.admin_token:
        ok, traces = _admin_traces(args.base_url, args.admin_token)
        checks.append(ok)
    else:
        ok, traces = _ops_traces(args.base_url, args.api_key)
        checks.append(ok)

    hit, detail = _trace_hits_prod_module(traces)
    if hit and detail:
        print(
            "OK retrieval trace hit prod module: "
            f"chars={detail['injected_chars']} entities={detail['entities']} paths={detail['paths']}"
        )
        checks.append(True)
    else:
        print("FAIL retrieval trace: no prod routing module in recent traces")
        if traces:
            sample = traces[0]
            print(
                "  latest_trace_entities=",
                sample.get("query_entities"),
                "injected_chars=",
                sample.get("injected_chars"),
            )
        checks.append(False)

    passed = sum(1 for item in checks if item)
    print(f"Result: {passed}/{len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
