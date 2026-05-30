#!/usr/bin/env python3
"""LiMa Backend Evaluation Script — test each backend across 6 dimensions."""
import sys, os, json, time, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backends import BACKENDS
import http_caller

# ── Test Prompts ──────────────────────────────────────────────────────────────

TESTS = {
    "code": "Write a Python function to reverse a linked list",
    "debug": "This code has a bug: `def fib(n): return fib(n-1) + fib(n-2)`. Fix it.",
    "chinese": "用中文解释什么是递归",
    "english": "Explain what a hash table is in 2 sentences",
    "reasoning": "What is 15 * 17?",
}

MAX_TOKENS = 512
TIMEOUT_SEC = 30


# ── Scoring Functions ─────────────────────────────────────────────────────────

def score_code(text: str) -> int:
    if not text:
        return 0
    has_def = "def " in text
    has_return = "return" in text
    has_codeblock = "```" in text
    if has_def and has_return:
        return 10
    if has_codeblock or has_def:
        return 7
    return 3


def score_debug(text: str) -> int:
    if not text:
        return 0
    lower = text.lower()
    has_base_case = any(k in lower for k in ["base case", "if n<=1", "if n <= 1",
                                              "if n < 2", "if n<=0", "if n == 0",
                                              "if n == 1", "n <= 1", "n < 2"])
    has_code = "def " in text or "```" in text
    if has_base_case:
        return 10
    if has_code:
        return 7
    return 3


def score_chinese(text: str) -> int:
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    total = len(text.strip())
    if total == 0:
        return 0
    ratio = chinese_chars / total
    if ratio > 0.5:
        return 10
    if ratio > 0.2:
        return 7
    return 3


def score_english(text: str) -> int:
    if not text:
        return 0
    words = len(re.findall(r'[a-zA-Z]+', text))
    if words > 30:
        return 10
    if words > 10:
        return 7
    return 3


def score_reasoning(text: str) -> int:
    if not text:
        return 0
    if "255" in text:
        return 10
    if re.search(r'\d+', text):
        return 5
    return 0


def score_speed(ms: float) -> int:
    if ms < 2000:
        return 10
    if ms < 5000:
        return 8
    if ms < 10000:
        return 5
    if ms < 20000:
        return 3
    if ms < 30000:
        return 1
    return 0


SCORERS = {
    "code": score_code,
    "debug": score_debug,
    "chinese": score_chinese,
    "english": score_english,
    "reasoning": score_reasoning,
}


# ── Main Execution ───────────────────────────────────────────────────────────

def eval_backend(name, cfg):
    """Evaluate a single backend. Returns dict of scores."""
    result = {"available": False, "avg_ms": 0}
    for dim in SCORERS:
        result[dim] = 0
    result["speed"] = 0
    result["total"] = 0

    if not cfg.get("key"):
        return result

    total_ms = 0
    success_count = 0

    for dim, prompt in TESTS.items():
        msgs = [{"role": "user", "content": prompt}]
        t0 = time.time()
        try:
            answer = http_caller.call_api(name, msgs, MAX_TOKENS,
                                          system_prompt="", ide="")
            ms = (time.time() - t0) * 1000
            result[dim] = SCORERS[dim](answer)
            total_ms += ms
            success_count += 1
        except Exception:
            ms = 30000
            result[dim] = 0
            total_ms += ms

    if success_count > 0:
        result["available"] = True
        result["avg_ms"] = int(total_ms / len(TESTS))
        result["speed"] = score_speed(result["avg_ms"])
    result["total"] = sum(result.get(d, 0) for d in list(SCORERS.keys()) + ["speed"])
    return result


def main():
    backends_to_test = []
    for name, cfg in BACKENDS.items():
        if cfg.get("key"):
            backends_to_test.append((name, cfg))

    print(f"Testing {len(backends_to_test)} backends (skipping {len(BACKENDS) - len(backends_to_test)} without keys)")
    print("=" * 60)

    results = {}
    for i, (name, cfg) in enumerate(backends_to_test, 1):
        sys.stdout.write(f"  [{i:3d}/{len(backends_to_test)}] {name:30s} ")
        sys.stdout.flush()
        r = eval_backend(name, cfg)
        results[name] = r
        status = "OK" if r["available"] else "FAIL"
        sys.stdout.write(f"[{status}] total={r['total']:2d} avg={r['avg_ms']:5d}ms\n")
        sys.stdout.flush()
        time.sleep(0.2)

    # Save results
    os.makedirs("data", exist_ok=True)
    output = {
        "eval_time": datetime.now().isoformat(),
        "total_tested": len(backends_to_test),
        "available": sum(1 for r in results.values() if r["available"]),
        "results": results,
    }
    with open("data/backend_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("TOP 30 BACKENDS BY TOTAL SCORE")
    print("=" * 60)
    sorted_r = sorted(results.items(), key=lambda x: x[1]["total"], reverse=True)
    print(f"{'Backend':30s} {'Total':>5s} {'Code':>4s} {'Debug':>5s} {'CN':>3s} {'EN':>3s} {'Math':>4s} {'Speed':>5s} {'ms':>6s}")
    print("-" * 80)
    for name, r in sorted_r[:30]:
        if not r["available"]:
            continue
        print(f"{name:30s} {r['total']:5d} {r.get('code',0):4d} {r.get('debug',0):5d} {r.get('chinese',0):3d} {r.get('english',0):3d} {r.get('reasoning',0):4d} {r.get('speed',0):5d} {r['avg_ms']:6d}")

    print(f"\nResults saved to data/backend_eval_results.json")
    print(f"Available: {output['available']}/{output['total_tested']}")


if __name__ == "__main__":
    main()
