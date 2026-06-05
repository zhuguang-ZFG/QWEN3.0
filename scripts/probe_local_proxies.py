#!/usr/bin/env python3
"""Probe local proxy backends for reachability and coding quality.

Usage:
    python scripts/probe_local_proxies.py
    python scripts/probe_local_proxies.py --ports 4502 4504 4505
    python scripts/probe_local_proxies.py --timeout 10
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

PROXY_CONFIGS = [
    {"name": "theoldllm", "port": 4502, "models_endpoint": "/v1/models"},
    {"name": "kimi", "port": 4504, "models_endpoint": "/v1/models"},
    {"name": "scnet_large", "port": 4505, "models_endpoint": "/v1/models"},
]

CODING_FIXTURES = [
    {
        "name": "fix_function",
        "prompt": "Write a Python function that returns the factorial of n.",
        "must_contain": ["def", "return"],
    },
    {
        "name": "explain_code",
        "prompt": "Explain what this code does: def fib(n): return n if n<2 else fib(n-1)+fib(n-2)",
        "must_contain": [],
    },
    {
        "name": "json_output",
        "prompt": 'Return a JSON object with keys "name" and "version" for Python.',
        "must_contain": ["{"],
    },
]

DATA_DIR = Path(os.environ.get("LIMA_DATA_DIR", "data"))


# ── Probe Logic ───────────────────────────────────────────────────────────────


def probe_models(base_url: str, timeout: int = 5) -> dict:
    """GET /v1/models → list available models."""
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{base_url}/v1/models",
            headers={"Accept": "application/json"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            latency_ms = int((time.time() - t0) * 1000)
            models = [m.get("id", "") for m in data.get("data", [])]
            return {"ok": True, "models": models, "count": len(models), "latency_ms": latency_ms}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def probe_chat(base_url: str, model: str, prompt: str, timeout: int = 15) -> dict:
    """POST /v1/chat/completions with a coding fixture."""
    import urllib.request

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0,
            "stream": False,
        }
    ).encode()

    try:
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            latency_ms = int((time.time() - t0) * 1000)
            answer = ""
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                answer = msg.get("content", "")
            return {"ok": bool(answer), "answer": answer[:500], "latency_ms": latency_ms}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def probe_proxy(config: dict, timeout: int = 15) -> dict:
    """Full probe: models + coding fixtures for a single proxy."""
    base_url = f"http://127.0.0.1:{config['port']}"
    result = {
        "name": config["name"],
        "port": config["port"],
        "base_url": base_url,
        "models": probe_models(base_url, timeout=min(timeout, 5)),
        "fixtures": [],
        "score": 0,
        "status": "unreachable",
    }

    if not result["models"]["ok"]:
        result["status"] = "unreachable"
        return result

    models = result["models"]["models"]
    model = models[0] if models else "default"

    passed = 0
    for fixture in CODING_FIXTURES:
        chat_result = probe_chat(base_url, model, fixture["prompt"], timeout=timeout)
        answer = chat_result.get("answer", "")
        checks = all(kw in answer for kw in fixture["must_contain"]) if fixture["must_contain"] else bool(answer)
        fixture_result = {
            "name": fixture["name"],
            "passed": chat_result["ok"] and checks,
            "latency_ms": chat_result.get("latency_ms", 0),
            "answer_preview": answer[:200],
        }
        if not chat_result["ok"]:
            fixture_result["error"] = chat_result.get("error", "")
        result["fixtures"].append(fixture_result)
        if fixture_result["passed"]:
            passed += 1

    result["score"] = passed / len(CODING_FIXTURES)
    result["status"] = "healthy" if result["score"] >= 0.66 else "degraded"
    return result


def load_previous_results() -> dict:
    """Load previous probe results for comparison."""
    pattern = DATA_DIR / "local_proxy_probe_*.json"
    files = sorted(pattern.glob("*.json"), reverse=True)
    if not files:
        return {}
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        return {r["name"]: r for r in data.get("results", [])}
    except Exception as exc:
        print(f"[warn] failed to load previous probe data: {exc}")
        return {}


def compare_with_previous(current: dict, previous: dict) -> str:
    """Compare current result with previous, return status delta."""
    name = current["name"]
    if name not in previous:
        return "new"
    prev = previous[name]
    if current["score"] > prev.get("score", 0):
        return "improved"
    if current["score"] < prev.get("score", 0):
        return "degraded"
    return "stable"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Probe local proxy backends")
    parser.add_argument("--ports", type=int, nargs="+", help="Ports to probe (default: 4502 4504 4505)")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    configs = PROXY_CONFIGS
    if args.ports:
        configs = [c for c in PROXY_CONFIGS if c["port"] in args.ports]

    previous = load_previous_results()
    results = []

    for config in configs:
        if not args.json:
            print(f"\n--- Probing {config['name']} (port {config['port']}) ---")

        result = probe_proxy(config, timeout=args.timeout)
        delta = compare_with_previous(result, previous)
        result["delta"] = delta
        results.append(result)

        if not args.json:
            print(
                f"  Models: {result['models'].get('count', 0)} available"
                + (f" ({result['models']['latency_ms']}ms)" if result["models"].get("ok") else "")
            )
            print(f"  Status: {result['status']} (score: {result['score']:.0%})")
            for fx in result["fixtures"]:
                mark = "PASS" if fx["passed"] else "FAIL"
                print(f"    [{mark}] {fx['name']} ({fx['latency_ms']}ms)")
            print(f"  Delta: {delta}")

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    output = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    out_path = DATA_DIR / f"local_proxy_probe_{date_str}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"\nResults saved to {out_path}")

    # Summary
    healthy = sum(1 for r in results if r["status"] == "healthy")
    total = len(results)
    if not args.json:
        print(f"\nSummary: {healthy}/{total} proxies healthy")

    return 0 if healthy == total else 1


if __name__ == "__main__":
    sys.exit(main())
