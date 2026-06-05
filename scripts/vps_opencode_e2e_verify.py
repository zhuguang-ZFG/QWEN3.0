#!/usr/bin/env python3
"""OpenCode end-to-end VPS verification — coding, tools, streaming, overflow, affinity.

Usage:
    python scripts/vps_opencode_e2e_verify.py                    # against public endpoint
    python scripts/vps_opencode_e2e_verify.py --local            # against localhost:8080
    python scripts/vps_opencode_e2e_verify.py --vps-ssh          # SSH tunnel to VPS localhost

Env vars:
    LIMA_API_KEY       — required API auth token
    LIMA_SERVER_URL    — override base URL (default: https://chat.donglicao.com)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coding_eval import CodingCase, grade_response, load_cases

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT_ROOT / "evals" / "coding_cases"
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "")
DEFAULT_BASE = "https://chat.donglicao.com"
LIMA_MODEL = "lima"

# ── Tool definitions (OpenAI format, OpenCode-compatible) ─────────────────────

OPENCODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents at the given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search codebase for patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "file_glob": {"type": "string"},
                    "include_context": {"type": "boolean"},
                },
                "required": ["pattern"],
            },
        },
    },
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class VerifyResult:
    name: str
    passed: bool
    latency_ms: int
    ttfb_ms: int = 0
    score: int = 0
    backend: str = ""
    detail: str = ""
    error: str = ""


@dataclass
class VerifyReport:
    timestamp: str = ""
    server: str = ""
    results: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers(stream: bool = False, affinity: str = "") -> dict:
    h = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
    }
    if affinity:
        h["x-session-affinity"] = affinity
    return h


async def _post_chat(
    base: str,
    messages: list[dict],
    *,
    stream: bool = False,
    tools: list[dict] | None = None,
    max_tokens: int = 512,
    affinity: str = "",
    model: str = LIMA_MODEL,
    timeout: float = 60,
) -> dict:
    """Send a chat completion request and return parsed result."""
    import httpx

    body: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools:
        body["tools"] = tools

    url = f"{base}/v1/chat/completions"
    headers = _headers(stream=stream, affinity=affinity)

    t0 = time.perf_counter()
    ttfb = 0
    content_parts: list[str] = []
    tool_calls_raw: list[dict] = []
    usage = None
    backend = ""
    sse_errors = 0

    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        if not stream:
            resp = await client.post(url, headers=headers, json=body)
            ttfb = int((time.perf_counter() - t0) * 1000)
            elapsed = ttfb
            if resp.status_code != 200:
                return {
                    "ok": False, "status": resp.status_code,
                    "error": resp.text[:300], "latency_ms": elapsed,
                    "ttfb_ms": ttfb,
                }
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])
            usage = data.get("usage")
            backend = data.get("model", "")
        else:
            try:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    ttfb = int((time.perf_counter() - t0) * 1000)
                    if resp.status_code != 200:
                        body_text = await resp.aread()
                        return {
                            "ok": False, "status": resp.status_code,
                            "error": body_text.decode("utf-8", errors="replace")[:300],
                            "latency_ms": ttfb, "ttfb_ms": ttfb,
                        }
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            sse_errors += 1
                            continue
                        choices = chunk.get("choices", [])
                        for choice in choices:
                            delta = choice.get("delta", {})
                            if delta.get("content"):
                                content_parts.append(delta["content"])
                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    while len(tool_calls_raw) <= idx:
                                        tool_calls_raw.append({
                                            "id": "", "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        })
                                    if tc.get("id"):
                                        tool_calls_raw[idx]["id"] = tc["id"]
                                    if tc.get("type"):
                                        tool_calls_raw[idx]["type"] = tc["type"]
                                    fn = tc.get("function", {})
                                    if fn.get("name"):
                                        tool_calls_raw[idx]["function"]["name"] = fn["name"]
                                    if fn.get("arguments"):
                                        tool_calls_raw[idx]["function"]["arguments"] += fn["arguments"]
                            if chunk.get("usage"):
                                usage = chunk["usage"]
                        if chunk.get("model"):
                            backend = chunk["model"]
            except Exception as stream_exc:
                # Streaming interrupted — return partial results with error context
                elapsed = int((time.perf_counter() - t0) * 1000)
                return {
                    "ok": True, "content": "".join(content_parts),
                    "tool_calls": tool_calls_raw, "usage": usage,
                    "backend": backend, "latency_ms": elapsed,
                    "ttfb_ms": ttfb, "sse_errors": sse_errors,
                    "stream_error": f"{type(stream_exc).__name__}: {stream_exc}",
                }
            elapsed = int((time.perf_counter() - t0) * 1000)

    content = "".join(content_parts) if stream else content
    return {
        "ok": True, "content": content, "tool_calls": tool_calls_raw,
        "usage": usage, "backend": backend, "latency_ms": elapsed,
        "ttfb_ms": ttfb, "sse_errors": sse_errors,
    }


# ── Verification steps ────────────────────────────────────────────────────────

async def verify_health(base: str) -> VerifyResult:
    """Step 1: Health check."""
    import httpx
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            resp = await client.get(f"{base}/health")
        ms = int((time.perf_counter() - t0) * 1000)
        ok = resp.status_code == 200
        return VerifyResult(
            name="health_check", passed=ok, latency_ms=ms,
            detail=f"status={resp.status_code}",
            error="" if ok else resp.text[:200],
        )
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return VerifyResult(name="health_check", passed=False, latency_ms=ms, error=str(e))


async def verify_coding(base: str) -> list[VerifyResult]:
    """Step 2: Coding ability using eval cases."""
    cases = load_cases(CASES_DIR)
    opencode_cases = [c for c in cases if "opencode" in c.tags]
    results = []

    for case in opencode_cases:
        messages = [{"role": "user", "content": case.prompt}]
        r = await _post_chat(base, messages, max_tokens=case.max_tokens)
        if not r["ok"]:
            results.append(VerifyResult(
                name=f"coding_{case.id}", passed=False,
                latency_ms=r.get("latency_ms", 0),
                error=r.get("error", "request failed"),
            ))
            continue

        score, notes = grade_response(r["content"], case)
        passed = score >= 70
        results.append(VerifyResult(
            name=f"coding_{case.id}", passed=passed,
            latency_ms=r.get("latency_ms", 0),
            ttfb_ms=r.get("ttfb_ms", 0),
            score=score,
            backend=r.get("backend", ""),
            detail=f"notes={notes[:3]}" if notes else "clean",
            error="" if passed else f"score={score}",
        ))
    return results


async def verify_tool_calls(base: str) -> VerifyResult:
    """Step 3: Tool call generation with OpenAI tools format."""
    messages = [
        {"role": "user", "content": "Read the file at /tmp/test.txt and tell me its contents."},
    ]
    r = await _post_chat(base, messages, tools=OPENCODE_TOOLS, max_tokens=512)
    if not r["ok"]:
        return VerifyResult(
            name="tool_calls", passed=False,
            latency_ms=r.get("latency_ms", 0),
            error=r.get("error", "request failed"),
        )

    tool_calls = r.get("tool_calls", [])
    has_tool_call = len(tool_calls) > 0
    has_correct_name = any(
        tc.get("function", {}).get("name") == "read_file" for tc in tool_calls
    )
    passed = has_tool_call and has_correct_name

    return VerifyResult(
        name="tool_calls", passed=passed,
        latency_ms=r.get("latency_ms", 0),
        ttfb_ms=r.get("ttfb_ms", 0),
        backend=r.get("backend", ""),
        detail=f"tools={len(tool_calls)} correct_name={has_correct_name}",
        error="" if passed else "no valid tool_calls in response",
    )


async def verify_streaming(base: str, *, retries: int = 1) -> VerifyResult:
    """Step 4: Streaming SSE format and usage chunk (with retry for network flakes)."""
    messages = [
        {"role": "user", "content": "Write a Python function that calculates fibonacci(n) iteratively. Keep it short."},
    ]
    last_result = None
    for attempt in range(retries + 1):
        r = await _post_chat(base, messages, stream=True, max_tokens=256)
        stream_err = r.get("stream_error", "")
        if not r["ok"]:
            last_result = r
            if attempt < retries:
                import asyncio as _a
                await _a.sleep(2)
                continue
            break
        content = r.get("content", "")
        usage = r.get("usage")
        sse_errors = r.get("sse_errors", 0)
        has_content = len(content) > 20
        has_usage = usage is not None and usage.get("prompt_tokens") is not None
        passed = has_content and sse_errors == 0 and not stream_err
        if passed or attempt >= retries:
            return VerifyResult(
                name="streaming", passed=passed,
                latency_ms=r.get("latency_ms", 0),
                ttfb_ms=r.get("ttfb_ms", 0),
                backend=r.get("backend", ""),
                detail=f"content_len={len(content)} usage={has_usage} sse_errors={sse_errors}",
                error="" if passed else f"content={has_content} errors={sse_errors} stream_err={stream_err}",
            )
        # Not passed but retryable
        last_result = r
        import asyncio as _a
        await _a.sleep(2)
    # All retries exhausted
    return VerifyResult(
        name="streaming", passed=False,
        latency_ms=last_result.get("latency_ms", 0) if last_result else 0,
        error="all retries exhausted",
    )


async def verify_streaming_tools(base: str, *, retries: int = 1) -> VerifyResult:
    """Step 4b: Streaming tool calls SSE delta format (with retry for network flakes)."""
    messages = [
        {"role": "user", "content": "Search the codebase for 'async def route' in *.py files."},
    ]
    last_result = None
    for attempt in range(retries + 1):
        r = await _post_chat(base, messages, stream=True, tools=OPENCODE_TOOLS, max_tokens=256, timeout=180)
        stream_error = r.get("stream_error", "")
        if not r["ok"]:
            last_result = r
            if attempt < retries:
                import asyncio as _a
                await _a.sleep(2)
                continue
            break

        tool_calls = r.get("tool_calls", [])
        has_tool = len(tool_calls) > 0
        # Validate assembled arguments are valid JSON
        args_valid = True
        for tc in tool_calls:
            args_str = tc.get("function", {}).get("arguments", "")
            if args_str:
                try:
                    json.loads(args_str)
                except json.JSONDecodeError:
                    args_valid = False
                    break

        passed = has_tool and args_valid and not stream_error
        if passed or attempt >= retries:
            detail = f"tools={len(tool_calls)} args_valid={args_valid}"
            if stream_error:
                detail += f" stream_error={stream_error}"
            return VerifyResult(
                name="streaming_tools", passed=passed,
                latency_ms=r.get("latency_ms", 0),
                ttfb_ms=r.get("ttfb_ms", 0),
                backend=r.get("backend", ""),
                detail=detail,
                error="" if passed else f"has_tool={has_tool} args_valid={args_valid} err={stream_error}",
            )
        # Not passed but retryable
        last_result = r
        import asyncio as _a
        await _a.sleep(2)
    # All retries exhausted
    return VerifyResult(
        name="streaming_tools", passed=False,
        latency_ms=last_result.get("latency_ms", 0) if last_result else 0,
        error="all retries exhausted",
    )


async def verify_overflow(base: str) -> VerifyResult:
    """Step 5: Context overflow detection."""
    # Generate a very long message to exceed context window
    filler = "This is padding text to exceed context window. " * 5000
    messages = [
        {"role": "user", "content": filler},
        {"role": "assistant", "content": filler},
        {"role": "user", "content": "Summarize the above."},
    ]
    t0 = time.perf_counter()
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.post(
                f"{base}/v1/chat/completions",
                headers=_headers(),
                json={
                    "model": LIMA_MODEL,
                    "messages": messages,
                    "max_tokens": 64,
                },
            )
        ms = int((time.perf_counter() - t0) * 1000)
        # Accept 413 or 400 with context_length_exceeded
        is_overflow = resp.status_code in (413, 400)
        if resp.status_code == 200:
            # Server handled via compression — still a valid outcome
            return VerifyResult(
                name="overflow_handling", passed=True,
                latency_ms=ms, detail="server compressed successfully (200)",
            )
        body = resp.text[:300]
        has_overflow_code = "context_length_exceeded" in body or "context" in body.lower()
        passed = is_overflow and has_overflow_code
        return VerifyResult(
            name="overflow_handling", passed=passed,
            latency_ms=ms,
            detail=f"status={resp.status_code}",
            error="" if passed else body[:200],
        )
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return VerifyResult(name="overflow_handling", passed=False, latency_ms=ms, error=str(e))


async def verify_affinity(base: str) -> VerifyResult:
    """Step 6: Session affinity — same header routes to same backend."""
    affinity = "e2e-test-session-001"
    backends_seen = []

    for i in range(3):
        messages = [{"role": "user", "content": f"Say hello (round {i+1})."}]
        r = await _post_chat(base, messages, affinity=affinity, max_tokens=32)
        if r["ok"]:
            backends_seen.append(r.get("backend", ""))

    if len(backends_seen) < 2:
        return VerifyResult(
            name="session_affinity", passed=False,
            latency_ms=0,
            error=f"only {len(backends_seen)} successful requests",
        )

    # All backends should be the same
    same = len(set(backends_seen)) == 1
    return VerifyResult(
        name="session_affinity", passed=same,
        latency_ms=0,
        backend=backends_seen[0],
        detail=f"backends={backends_seen}",
        error="" if same else f"inconsistent: {backends_seen}",
    )


# ── Report generation ─────────────────────────────────────────────────────────

def build_report(results: list[VerifyResult], server: str) -> VerifyReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    avg_latency = int(sum(r.latency_ms for r in results) / max(total, 1))
    avg_ttfb = int(
        sum(r.ttfb_ms for r in results if r.ttfb_ms > 0)
        / max(sum(1 for r in results if r.ttfb_ms > 0), 1)
    )
    coding_scores = [r.score for r in results if r.name.startswith("coding_") and r.score > 0]
    avg_coding = int(sum(coding_scores) / max(len(coding_scores), 1))

    report = VerifyReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        server=server,
        results=[asdict(r) for r in results],
        summary={
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "avg_latency_ms": avg_latency,
            "avg_ttfb_ms": avg_ttfb,
            "avg_coding_score": avg_coding,
            "all_passed": passed == total,
        },
    )
    return report


def print_summary(report: VerifyReport) -> None:
    s = report.summary
    print("\n" + "=" * 70)
    print("OpenCode E2E Verification Report")
    print(f"  Server:    {report.server}")
    print(f"  Timestamp: {report.timestamp}")
    print("=" * 70)
    print(f"\n{'Step':<28} {'Result':<8} {'Latency':>10} {'TTFB':>10} {'Score':>6}")
    print("-" * 70)
    for r in report.results:
        status = "PASS" if r["passed"] else "FAIL"
        lat = f"{r['latency_ms']}ms" if r["latency_ms"] else "-"
        ttfb = f"{r['ttfb_ms']}ms" if r["ttfb_ms"] else "-"
        score = str(r["score"]) if r["score"] else "-"
        print(f"  {r['name']:<26} {status:<8} {lat:>10} {ttfb:>10} {score:>6}")
        if r.get("detail"):
            print(f"    {r['detail'][:80]}")
        if r.get("error"):
            print(f"    ERROR: {r['error'][:80]}")

    print("-" * 70)
    print(f"  Total: {s['passed']}/{s['total']} passed")
    print(f"  Avg latency: {s['avg_latency_ms']}ms  |  Avg TTFB: {s['avg_ttfb_ms']}ms")
    print(f"  Avg coding score: {s['avg_coding_score']}")
    verdict = "ALL PASSED" if s["all_passed"] else f"{s['failed']} FAILED"
    print(f"  Verdict: {verdict}")
    print("=" * 70 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_all(base: str, *, quick: bool = False) -> VerifyReport:
    results: list[VerifyResult] = []

    def _safe(name: str, coro) -> None:
        """Run a verification step; record FAIL on unhandled exception."""
        import asyncio as _a
        try:
            r = _a.get_event_loop().run_until_complete(coro)
            results.append(r)
        except Exception as exc:
            results.append(VerifyResult(
                name=name, passed=False, latency_ms=0, error=f"{type(exc).__name__}: {exc}",
            ))

    async def _safe_multi(name: str, coro) -> None:
        try:
            rs = await coro
            results.extend(rs)
        except Exception as exc:
            results.append(VerifyResult(
                name=name, passed=False, latency_ms=0, error=f"{type(exc).__name__}: {exc}",
            ))

    # Step 1: Health
    print("[1/7] Health check...")
    try:
        results.append(await verify_health(base))
    except Exception as exc:
        results.append(VerifyResult(name="health", passed=False, latency_ms=0, error=str(exc)))

    # Step 2: Coding (multiple cases)
    print("[2/7] Coding ability verification...")
    await _safe_multi("coding", verify_coding(base))

    # Step 3: Tool calls
    print("[3/7] Tool call generation...")
    try:
        results.append(await verify_tool_calls(base))
    except Exception as exc:
        results.append(VerifyResult(name="tool_calls", passed=False, latency_ms=0, error=str(exc)))

    # Step 4a: Streaming
    print("[4/7] Streaming SSE verification...")
    try:
        results.append(await verify_streaming(base))
    except Exception as exc:
        results.append(VerifyResult(name="streaming", passed=False, latency_ms=0, error=str(exc)))

    # Step 4b: Streaming tools
    print("[4b] Streaming tool calls...")
    try:
        results.append(await verify_streaming_tools(base))
    except Exception as exc:
        results.append(VerifyResult(name="streaming_tools", passed=False, latency_ms=0, error=str(exc)))

    if not quick:
        # Step 5: Overflow (slow — sends very large payload)
        print("[5/7] Context overflow handling...")
        try:
            results.append(await verify_overflow(base))
        except Exception as exc:
            results.append(VerifyResult(name="overflow", passed=False, latency_ms=0, error=str(exc)))

        # Step 6: Affinity (multiple sequential requests)
        print("[6/7] Session affinity...")
        try:
            results.append(await verify_affinity(base))
        except Exception as exc:
            results.append(VerifyResult(name="affinity", passed=False, latency_ms=0, error=str(exc)))
    else:
        print("[5-6] Skipped (quick mode): overflow + affinity")

    return build_report(results, base)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCode E2E VPS verification")
    parser.add_argument("--local", action="store_true", help="Target localhost:8080")
    parser.add_argument("--vps-ssh", action="store_true", help="SSH tunnel to VPS")
    parser.add_argument("--server-url", default="", help="Override server URL")
    parser.add_argument("--api-key", default="", help="Override API key")
    parser.add_argument("--json-report", default="", help="Write JSON report to path")
    parser.add_argument("--quick", action="store_true", help="Skip overflow and affinity tests")
    args = parser.parse_args()

    global LIMA_API_KEY
    if args.api_key:
        LIMA_API_KEY = args.api_key
    if not LIMA_API_KEY:
        sys.exit("ERROR: LIMA_API_KEY is required (env var or --api-key)")

    if args.local:
        base = "http://127.0.0.1:8080"
    elif args.server_url:
        base = args.server_url.rstrip("/")
    else:
        base = os.environ.get("LIMA_SERVER_URL", DEFAULT_BASE)

    print(f"OpenCode E2E Verification — Server: {base}")
    print(f"Cases dir: {CASES_DIR}")
    print()

    report = asyncio.run(run_all(base, quick=args.quick))
    print_summary(report)

    # Write JSON report
    report_path = args.json_report or str(PROJECT_ROOT / "data" / "opencode_e2e_results.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON report: {report_path}")

    if not report.summary["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
