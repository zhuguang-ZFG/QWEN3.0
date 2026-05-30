#!/usr/bin/env python3
"""Multi-round stress test: LiMa Server API + LiMa Code Worker.

Uses real VPS API for server tests and real deepcode-cli for worker tests.
No mocking — all calls go to production endpoints.

Usage:
    python scripts/stress_test_lima.py --mode server --rounds 10
    python scripts/stress_test_lima.py --mode worker --rounds 5
    python scripts/stress_test_lima.py --mode all
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

VPS_BASE = "https://chat.donglicao.com"
API_KEY = os.environ.get("LIMA_API_KEY", "lima-local")
ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "LiMa@Admin2026!Secure")
LIMA_CODE_DIR = os.environ.get("LIMA_CODE_DIR", str(Path(__file__).resolve().parent.parent / "deepcode-cli"))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Server API Test Cases ─────────────────────────────────────────────────────

SERVER_CASES = [
    # (category, prompt)
    ("coding_simple", "Write a Python function that computes the factorial of n using recursion."),
    ("coding_simple", "Write a Python function to check if a string is a palindrome."),
    ("coding_simple", "Write a Python function that flattens a nested list."),
    ("coding_medium", "Write a Python class that implements a stack with push, pop, peek, and is_empty methods."),
    ("coding_medium", "Write a Python function that finds the longest common subsequence of two strings."),
    ("coding_medium", "Write a Python decorator that retries a function up to 3 times on exception."),
    ("coding_file", "Read routing_engine.py and explain the 5-layer routing pipeline in detail."),
    ("coding_file", "Read http_caller.py and explain how backend fallback works."),
    ("chat", "Explain the difference between asyncio and threading in Python."),
    ("chat", "What is the GIL and when does it matter?"),
]

# ── LiMa Code Worker Task Cases ──────────────────────────────────────────────

WORKER_CASES = [
    "Create a Python file hello.py that prints 'Hello, LiMa Code!' when executed directly.",
    "Add command-line argument support to hello.py using argparse. Accept --name and --greeting.",
    "Write a test_hello.py with 3 unit tests for hello.py functions.",
    "Review hello.py for code quality issues and fix any problems found.",
    "Refactor hello.py to use a main() function with proper if __name__ == '__main__' guard.",
]


# ── Server API Stress Test ───────────────────────────────────────────────────

def call_server_api(prompt: str, max_tokens: int = 500) -> dict:
    """Send a single request to LiMa Server and collect metrics."""
    body = json.dumps({
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{VPS_BASE}/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            latency_ms = int((time.time() - t0) * 1000)
            answer = ""
            choices = data.get("choices", [])
            if choices:
                answer = choices[0].get("message", {}).get("content", "")
            backend = data.get("x_lima_meta", {}).get("backend", "unknown")
            fallback = data.get("x_lima_meta", {}).get("fallback_used", False)
            return {
                "ok": True,
                "backend": backend,
                "latency_ms": latency_ms,
                "fallback": fallback,
                "answer_len": len(answer),
                "answer_preview": answer[:200],
            }
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": latency_ms,
        }


def run_server_stress(rounds: int) -> list[dict]:
    """Run server API stress test."""
    results = []
    cases = SERVER_CASES[:rounds]

    print(f"\n{'='*60}")
    print(f"  LiMa Server Stress Test — {len(cases)} rounds")
    print(f"{'='*60}\n")

    for i, (category, prompt) in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {category}: {prompt[:50]}...", end=" ", flush=True)
        result = call_server_api(prompt)
        result["round"] = i
        result["category"] = category
        result["prompt"] = prompt
        results.append(result)

        if result["ok"]:
            print(f"→ {result['backend']} ({result['latency_ms']}ms, {result['answer_len']} chars)")
        else:
            print(f"→ FAIL: {result['error'][:60]}")

    return results


# ── LiMa Code Worker Stress Test ─────────────────────────────────────────────

def create_task_on_server(goal: str) -> str | None:
    """Create a task via LiMa Server API and return task_id."""
    body = json.dumps({
        "repo": "local",
        "branch": "main",
        "goal": goal,
        "mode": "patch",
        "max_runtime_sec": 120,
    }).encode()

    req = urllib.request.Request(
        f"{VPS_BASE}/agent/worker/smoke-task",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ADMIN_TOKEN}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("task_id")
    except Exception as e:
        print(f"  Task creation failed: {e}")
        return None


def claim_and_run_task(task_id: str) -> dict:
    """Use real deepcode-cli to claim and run a task."""
    t0 = time.time()
    try:
        result = subprocess.run(
            ["node", str(Path(LIMA_CODE_DIR) / "node_modules" / "tsx" / "dist" / "cli.mjs"),
             "src/index.ts", "lima", "task", task_id],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=LIMA_CODE_DIR,
            env={**os.environ, "LIMA_API_KEY": API_KEY},
        )
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "latency_ms": latency_ms,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-300:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout (180s)", "latency_ms": 180000}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "latency_ms": int((time.time() - t0) * 1000)}


def run_worker_stress(rounds: int) -> list[dict]:
    """Run LiMa Code Worker stress test with real tasks."""
    results = []
    cases = WORKER_CASES[:rounds]

    print(f"\n{'='*60}")
    print(f"  LiMa Code Worker Stress Test — {len(cases)} rounds")
    print(f"{'='*60}\n")

    for i, goal in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] Creating task: {goal[:50]}...")

        # 1. Create task on server
        task_id = create_task_on_server(goal)
        if not task_id:
            results.append({"round": i, "goal": goal, "ok": False, "error": "task creation failed"})
            continue

        print(f"    task_id={task_id}, claiming with deepcode-cli...")

        # 2. Execute with real LiMa Code
        exec_result = claim_and_run_task(task_id)

        # 3. Collect result
        result = {
            "round": i,
            "goal": goal,
            "task_id": task_id,
            "ok": exec_result.get("ok", False),
            "exit_code": exec_result.get("exit_code", -1),
            "latency_ms": exec_result.get("latency_ms", 0),
            "stdout_preview": exec_result.get("stdout", "")[:200],
            "error": exec_result.get("error", ""),
        }
        results.append(result)

        status = "PASS" if result["ok"] else "FAIL"
        print(f"    [{status}] {result['latency_ms']}ms exit={result['exit_code']}")
        if result["error"]:
            print(f"    error: {result['error'][:80]}")
        if result["stdout_preview"]:
            print(f"    output: {result['stdout_preview'][:100]}")

    return results


# ── Learning Loop Verification ────────────────────────────────────────────────

def snapshot_weights() -> dict:
    """Read current routing_weights state."""
    weights_path = DATA_DIR / "lima_routing_weights.json"
    if weights_path.exists():
        try:
            return json.loads(weights_path.read_text(encoding="utf-8"))
        except Exception as exc:
            pass  # scripts/stress_test_lima.py
    return {}


def verify_learning_loop(before: dict, after: dict) -> dict:
    """Compare routing weights before and after stress test."""
    new_keys = set(after.keys()) - set(before.keys())
    changed = {}
    for k in set(before.keys()) & set(after.keys()):
        b, a = before[k], after[k]
        if b.get("weight") != a.get("weight") or b.get("successes") != a.get("successes"):
            changed[k] = {"before": b, "after": a}

    return {
        "new_backends": list(new_keys),
        "changed_backends": changed,
        "total_before": len(before),
        "total_after": len(after),
    }


# ── Report ────────────────────────────────────────────────────────────────────

def print_server_report(results: list[dict]) -> None:
    """Print server stress test summary."""
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]

    print(f"\n{'='*60}")
    print(f"  Server Stress Test Report")
    print(f"{'='*60}")
    print(f"  Total: {len(results)} | Pass: {len(ok)} | Fail: {len(fail)}")

    if ok:
        latencies = [r["latency_ms"] for r in ok]
        backends = {}
        for r in ok:
            b = r["backend"]
            backends[b] = backends.get(b, 0) + 1

        print(f"  Latency: P50={sorted(latencies)[len(latencies)//2]}ms "
              f"P95={sorted(latencies)[int(len(latencies)*0.95)]}ms "
              f"Max={max(latencies)}ms")
        print(f"  Backends: {backends}")

    if fail:
        print(f"  Failures:")
        for r in fail:
            print(f"    [{r['category']}] {r.get('error', 'unknown')[:60]}")


def print_worker_report(results: list[dict]) -> None:
    """Print worker stress test summary."""
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]

    print(f"\n{'='*60}")
    print(f"  LiMa Code Worker Stress Test Report")
    print(f"{'='*60}")
    print(f"  Total: {len(results)} | Pass: {len(ok)} | Fail: {len(fail)}")

    if ok:
        latencies = [r["latency_ms"] for r in ok]
        print(f"  Latency: P50={sorted(latencies)[len(latencies)//2]}ms "
              f"Max={max(latencies)}ms")

    for r in results:
        status = "PASS" if r.get("ok") else "FAIL"
        print(f"  [{status}] Round {r['round']}: {r['goal'][:50]}")


def print_learning_report(loop_data: dict) -> None:
    """Print learning loop verification."""
    print(f"\n{'='*60}")
    print(f"  Learning Loop Verification")
    print(f"{'='*60}")
    print(f"  Backends: {loop_data['total_before']} → {loop_data['total_after']}")
    if loop_data["new_backends"]:
        print(f"  New: {loop_data['new_backends']}")
    if loop_data["changed_backends"]:
        print(f"  Changed:")
        for k, v in loop_data["changed_backends"].items():
            print(f"    {k}: weight {v['before'].get('weight',0):.3f} → {v['after'].get('weight',0):.3f}")
    if not loop_data["new_backends"] and not loop_data["changed_backends"]:
        print("  No changes detected (weights unchanged)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["server", "worker", "all"], default="server")
    parser.add_argument("--rounds", type=int, default=0, help="Number of rounds (0=all)")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    server_results = []
    worker_results = []

    # Snapshot weights before
    weights_before = snapshot_weights()

    if args.mode in ("server", "all"):
        n = args.rounds or len(SERVER_CASES)
        server_results = run_server_stress(n)
        print_server_report(server_results)

    if args.mode in ("worker", "all"):
        n = args.rounds or len(WORKER_CASES)
        worker_results = run_worker_stress(n)
        print_worker_report(worker_results)

    # Snapshot weights after
    weights_after = snapshot_weights()
    learning = verify_learning_loop(weights_before, weights_after)
    print_learning_report(learning)

    # Save results
    date_str = datetime.now().strftime("%Y%m%d")
    output = {
        "timestamp": datetime.now().isoformat(),
        "mode": args.mode,
        "server_results": server_results,
        "worker_results": worker_results,
        "learning_loop": learning,
    }
    out_path = DATA_DIR / f"stress_test_results_{date_str}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
