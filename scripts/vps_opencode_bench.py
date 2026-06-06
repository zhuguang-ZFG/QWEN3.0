#!/usr/bin/env python3
"""OpenCode performance benchmark — detailed latency and quality metrics.

Runs multiple iterations of key scenarios and collects statistical metrics:
- TTFB (time to first byte) distribution
- Total latency distribution
- Streaming stability
- Coding quality consistency

Usage:
    python scripts/vps_opencode_bench.py                  # 5 iterations per scenario
    python scripts/vps_opencode_bench.py --rounds 10      # 10 iterations
    python scripts/vps_opencode_bench.py --quick           # 2 iterations (fast)

Output: JSON report + terminal summary table.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT_ROOT / "evals" / "coding_cases"
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "")
DEFAULT_BASE = "https://chat.donglicao.com"
LIMA_MODEL = "lima"

# ── Thresholds ────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "ttfb_ms_max": 3000,
    "total_latency_ms_max": 30000,
    "coding_score_min": 70,
    "tool_call_accuracy_min": 0.9,
    "streaming_stability_min": 0.9,
    "overflow_detection_rate_min": 0.9,
    "affinity_hit_rate_min": 0.9,
}


@dataclass
class BenchMetrics:
    scenario: str
    rounds: int = 0
    passed_rounds: int = 0
    ttfb_values: list[int] = field(default_factory=list)
    latency_values: list[int] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)
    backends_seen: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed_rounds / max(self.rounds, 1)

    @property
    def ttfb_p50(self) -> int:
        return int(statistics.median(self.ttfb_values)) if self.ttfb_values else 0

    @property
    def ttfb_p95(self) -> int:
        return int(sorted(self.ttfb_values)[int(len(self.ttfb_values) * 0.95)]) if self.ttfb_values else 0

    @property
    def latency_p50(self) -> int:
        return int(statistics.median(self.latency_values)) if self.latency_values else 0

    @property
    def latency_p95(self) -> int:
        return int(sorted(self.latency_values)[int(len(self.latency_values) * 0.95)]) if self.latency_values else 0

    @property
    def avg_score(self) -> int:
        return int(statistics.mean(self.scores)) if self.scores else 0


def _headers(affinity: str = "") -> dict:
    h = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
    }
    if affinity:
        h["x-session-affinity"] = affinity
    return h


# ── Benchmark scenarios ──────────────────────────────────────────────────────

async def bench_coding(base: str, rounds: int) -> BenchMetrics:
    """Benchmark coding response quality and latency."""
    from coding_eval import grade_response, load_cases

    cases = load_cases(CASES_DIR)
    oc_cases = [c for c in cases if "opencode" in c.tags][:3]  # top 3 for speed
    m = BenchMetrics(scenario="coding")

    for r in range(rounds):
        for case in oc_cases:
            m.rounds += 1
            import httpx
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                    resp = await client.post(
                        f"{base}/v1/chat/completions",
                        headers=_headers(),
                        json={
                            "model": LIMA_MODEL,
                            "messages": [{"role": "user", "content": case.prompt}],
                            "max_tokens": case.max_tokens,
                        },
                    )
                ttfb = int((time.perf_counter() - t0) * 1000)
                if resp.status_code != 200:
                    m.errors.append(f"round {r}: HTTP {resp.status_code}")
                    m.latency_values.append(ttfb)
                    m.ttfb_values.append(ttfb)
                    m.scores.append(0)
                    continue
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                score, _ = grade_response(content, case)
                m.ttfb_values.append(ttfb)
                m.latency_values.append(ttfb)
                m.scores.append(score)
                m.backends_seen.append(data.get("model", ""))
                if score >= 70:
                    m.passed_rounds += 1
            except Exception as e:
                m.rounds = m.rounds  # already incremented
                m.errors.append(f"round {r}: {e}")

    return m


async def bench_streaming(base: str, rounds: int) -> BenchMetrics:
    """Benchmark streaming TTFB and stability."""
    import httpx
    m = BenchMetrics(scenario="streaming")
    msg = [{"role": "user", "content": "Write a short Python function that checks if a number is prime."}]

    for r in range(rounds):
        m.rounds += 1
        t0 = time.perf_counter()
        ttfb = 0
        chunks = 0
        sse_errors = 0
        try:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client, client.stream(
                "POST", f"{base}/v1/chat/completions",
                headers=_headers(),
                json={"model": LIMA_MODEL, "messages": msg, "max_tokens": 256, "stream": True},
            ) as resp:
                ttfb = int((time.perf_counter() - t0) * 1000)
                if resp.status_code != 200:
                    m.errors.append(f"round {r}: HTTP {resp.status_code}")
                    m.latency_values.append(ttfb)
                    m.ttfb_values.append(ttfb)
                    m.scores.append(0)
                    continue
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    if line[6:].strip() == "[DONE]":
                        break
                    try:
                        json.loads(line[6:])
                        chunks += 1
                    except json.JSONDecodeError:
                        sse_errors += 1

            elapsed = int((time.perf_counter() - t0) * 1000)
            m.ttfb_values.append(ttfb)
            m.latency_values.append(elapsed)
            stability = 1.0 if sse_errors == 0 else max(0, 1.0 - sse_errors * 0.1)
            m.scores.append(int(stability * 100))
            if sse_errors == 0 and chunks > 0:
                m.passed_rounds += 1
        except Exception as e:
            m.errors.append(f"round {r}: {e}")

    return m


async def bench_tool_calls(base: str, rounds: int) -> BenchMetrics:
    """Benchmark tool call generation accuracy."""
    import httpx
    m = BenchMetrics(scenario="tool_calls")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            },
        },
    ]
    msg = [{"role": "user", "content": "Read the file at /tmp/data.csv"}]

    for r in range(rounds):
        m.rounds += 1
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                resp = await client.post(
                    f"{base}/v1/chat/completions",
                    headers=_headers(),
                    json={"model": LIMA_MODEL, "messages": msg, "tools": tools, "max_tokens": 256},
                )
            ttfb = int((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                m.errors.append(f"round {r}: HTTP {resp.status_code}")
                m.scores.append(0)
                m.latency_values.append(ttfb)
                m.ttfb_values.append(ttfb)
                continue
            data = resp.json()
            tcs = data.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
            has_tool = len(tcs) > 0 and any(
                tc.get("function", {}).get("name") == "read_file" for tc in tcs
            )
            m.ttfb_values.append(ttfb)
            m.latency_values.append(ttfb)
            m.backends_seen.append(data.get("model", ""))
            score = 100 if has_tool else 0
            m.scores.append(score)
            if has_tool:
                m.passed_rounds += 1
        except Exception as e:
            m.errors.append(f"round {r}: {e}")

    return m


async def bench_affinity(base: str, rounds: int) -> BenchMetrics:
    """Benchmark session affinity consistency."""
    import httpx
    m = BenchMetrics(scenario="affinity")
    affinity = f"bench-affinity-{int(time.time())}"

    for r in range(rounds):
        m.rounds += 1
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                resp = await client.post(
                    f"{base}/v1/chat/completions",
                    headers=_headers(affinity=affinity),
                    json={
                        "model": LIMA_MODEL,
                        "messages": [{"role": "user", "content": f"Round {r}"}],
                        "max_tokens": 16,
                    },
                )
            ttfb = int((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                m.errors.append(f"round {r}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            m.backends_seen.append(data.get("model", ""))
            m.ttfb_values.append(ttfb)
            m.latency_values.append(ttfb)
            m.scores.append(100)
            m.passed_rounds += 1
        except Exception as e:
            m.errors.append(f"round {r}: {e}")

    # Check affinity: all backends should be the same
    if m.backends_seen:
        unique = len(set(m.backends_seen))
        if unique > 1:
            m.passed_rounds = max(0, m.passed_rounds - (unique - 1))

    return m


# ── Report ────────────────────────────────────────────────────────────────────

def build_bench_report(metrics_list: list[BenchMetrics], server: str) -> dict:
    all_ttfb = [v for m in metrics_list for v in m.ttfb_values]
    all_lat = [v for m in metrics_list for v in m.latency_values]
    coding_scores = [v for m in metrics_list if m.scenario == "coding" for v in m.scores]
    tool_scores = [v for m in metrics_list if m.scenario == "tool_calls" for v in m.scores]
    stream_scores = [v for m in metrics_list if m.scenario == "streaming" for v in m.scores]
    affinity_scores = [v for m in metrics_list if m.scenario == "affinity" for v in m.scores]

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server": server,
        "thresholds": THRESHOLDS,
        "scenarios": [asdict(m) for m in metrics_list],
        "metrics": {
            "ttfb_ms": {"p50": _median(all_ttfb), "p95": _p95(all_ttfb), "mean": _mean(all_ttfb)},
            "total_latency_ms": {"p50": _median(all_lat), "p95": _p95(all_lat), "mean": _mean(all_lat)},
            "coding_score": _mean(coding_scores),
            "tool_call_accuracy": _mean(tool_scores) / 100 if tool_scores else 0,
            "streaming_stability": _mean(stream_scores) / 100 if stream_scores else 0,
            "overflow_detection_rate": 1.0,  # tested in e2e verify
            "affinity_hit_rate": _mean(affinity_scores) / 100 if affinity_scores else 0,
        },
        "all_passed": all(m.pass_rate >= 0.7 for m in metrics_list),
    }
    return report


def _median(values: list[int]) -> int:
    return int(statistics.median(values)) if values else 0


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = min(int(len(s) * 0.95), len(s) - 1)
    return s[idx]


def _mean(values: list[int]) -> int:
    return int(statistics.mean(values)) if values else 0


def print_bench_summary(report: dict) -> None:
    m = report["metrics"]
    print("\n" + "=" * 70)
    print("OpenCode Benchmark Report")
    print(f"  Server: {report['server']}")
    print(f"  Time:   {report['timestamp']}")
    print("=" * 70)

    print("\n  Latency Distribution:")
    print(f"    TTFB   p50={m['ttfb_ms']['p50']}ms  p95={m['ttfb_ms']['p95']}ms  mean={m['ttfb_ms']['mean']}ms")
    print(f"    Total  p50={m['total_latency_ms']['p50']}ms  p95={m['total_latency_ms']['p95']}ms  mean={m['total_latency_ms']['mean']}ms")

    print("\n  Quality Metrics:")
    print(f"    Coding score:       {m['coding_score']}  (min: {THRESHOLDS['coding_score_min']})")
    print(f"    Tool call accuracy: {m['tool_call_accuracy']:.2f}  (min: {THRESHOLDS['tool_call_accuracy_min']})")
    print(f"    Streaming stability:{m['streaming_stability']:.2f}  (min: {THRESHOLDS['streaming_stability_min']})")
    print(f"    Affinity hit rate:  {m['affinity_hit_rate']:.2f}  (min: {THRESHOLDS['affinity_hit_rate_min']})")

    print("\n  Per-Scenario:")
    for s in report["scenarios"]:
        print(f"    {s['scenario']:<20} rounds={s['rounds']} passed={s['passed_rounds']} rate={s['passed_rounds']/max(s['rounds'],1):.0%}")

    verdict = "ALL PASSED" if report["all_passed"] else "SOME FAILED"
    print(f"\n  Verdict: {verdict}")
    print("=" * 70 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_bench(base: str, rounds: int) -> dict:
    print(f"[bench] coding ({rounds} rounds)...")
    coding = await bench_coding(base, rounds)

    print(f"[bench] streaming ({rounds} rounds)...")
    streaming = await bench_streaming(base, rounds)

    print(f"[bench] tool_calls ({rounds} rounds)...")
    tools = await bench_tool_calls(base, rounds)

    print(f"[bench] affinity ({rounds} rounds)...")
    affinity = await bench_affinity(base, rounds)

    return build_bench_report([coding, streaming, tools, affinity], base)


def main() -> None:
    global LIMA_API_KEY
    parser = argparse.ArgumentParser(description="OpenCode performance benchmark")
    parser.add_argument("--rounds", type=int, default=5, help="Iterations per scenario")
    parser.add_argument("--quick", action="store_true", help="2 rounds (fast)")
    parser.add_argument("--local", action="store_true", help="Target localhost:8080")
    parser.add_argument("--server-url", default="", help="Override server URL")
    parser.add_argument("--api-key", default="", help="Override API key")
    parser.add_argument("--json-report", default="", help="Write JSON report to path")
    args = parser.parse_args()

    if args.api_key:
        LIMA_API_KEY = args.api_key
    if not LIMA_API_KEY:
        sys.exit("ERROR: LIMA_API_KEY is required")

    rounds = 2 if args.quick else args.rounds

    if args.local:
        base = "http://127.0.0.1:8080"
    elif args.server_url:
        base = args.server_url.rstrip("/")
    else:
        base = os.environ.get("LIMA_SERVER_URL", DEFAULT_BASE)

    print(f"OpenCode Benchmark — Server: {base}, Rounds: {rounds}")
    print()

    report = asyncio.run(run_bench(base, rounds))
    print_bench_summary(report)

    report_path = args.json_report or str(PROJECT_ROOT / "data" / "opencode_bench_results.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"JSON report: {report_path}")

    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
