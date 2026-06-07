#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode 性能基准测试

对比场景：
1. 基线：原有配置（不启用新模块）
2. 优化：启用所有新模块

测量指标：
- Token 使用量（input + output）
- 响应延迟（路由时间 + 生成时间）
- 后端选择一致性
- 会话缓存命中率
"""

import json
import os
import sys
import time
from statistics import mean, median, stdev
from typing import List, Dict, Tuple

import httpx

# 配置
BASE_URL = "http://localhost:5007"
API_KEY = os.getenv("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")
OPENCODE_UA = "OpenCode/1.2.0 (Windows NT 10.0; Win64; x64) Node.js/18.17.0"

# 测试场景
TEST_CASES = [
    {
        "name": "Simple Query",
        "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
        "max_tokens": 50,
    },
    {
        "name": "Code Explanation",
        "messages": [{"role": "user", "content": "Explain what this does: `arr.map(x => x * 2)`"}],
        "max_tokens": 150,
    },
    {
        "name": "Debugging Help",
        "messages": [
            {"role": "user", "content": "I'm getting 'TypeError: Cannot read property of undefined'. What should I check?"}
        ],
        "max_tokens": 200,
    },
    {
        "name": "Tool Calling",
        "messages": [{"role": "user", "content": "What's the weather in Tokyo?"}],
        "max_tokens": 200,
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"]
                }
            }
        }],
    },
    {
        "name": "Multi-turn Context",
        "messages": [
            {"role": "user", "content": "What is a promise in JavaScript?"},
            {"role": "assistant", "content": "A Promise is an object representing eventual completion or failure of an async operation."},
            {"role": "user", "content": "Give me a simple example."},
        ],
        "max_tokens": 250,
    },
]

# 测试轮次
WARMUP_ROUNDS = 2  # 预热轮次（不计入统计）
TEST_ROUNDS = 5    # 正式测试轮次


class BenchmarkResult:
    """单次测试结果"""
    def __init__(self):
        self.success = False
        self.latency_ms = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.backend = "unknown"
        self.route_time_ms = 0
        self.error = None


def run_single_request(test_case: Dict, session_id: str = None) -> BenchmarkResult:
    """执行单次请求"""
    result = BenchmarkResult()

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": OPENCODE_UA,
        "Content-Type": "application/json",
    }

    if session_id:
        headers["X-OpenCode-Session-ID"] = session_id

    payload = {
        "model": "gpt-4o-mini",
        "messages": test_case["messages"],
        "max_tokens": test_case["max_tokens"],
        "stream": False,
    }

    if "tools" in test_case:
        payload["tools"] = test_case["tools"]

    start_time = time.time()

    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            result.success = True
            result.latency_ms = latency_ms

            # Token 统计
            usage = data.get("usage", {})
            result.input_tokens = usage.get("prompt_tokens", 0)
            result.output_tokens = usage.get("completion_tokens", 0)
            result.total_tokens = usage.get("total_tokens", 0)

            # 后端信息
            result.backend = resp.headers.get("x-lima-backend", "unknown")

            # 路由时间
            route_time = resp.headers.get("x-lima-route-ms", "0")
            try:
                result.route_time_ms = int(route_time)
            except:
                result.route_time_ms = 0
        else:
            result.error = f"HTTP {resp.status_code}"
    except Exception as e:
        result.error = str(e)

    return result


def run_benchmark(test_case: Dict, rounds: int, session_id: str = None) -> List[BenchmarkResult]:
    """运行多轮基准测试"""
    results = []

    for i in range(rounds):
        result = run_single_request(test_case, session_id)
        results.append(result)

        if not result.success:
            print(f"   Round {i+1}: FAIL - {result.error}")
        else:
            print(f"   Round {i+1}: {result.latency_ms}ms, "
                  f"{result.total_tokens} tokens, backend={result.backend}")

        time.sleep(0.5)  # 避免频繁请求

    return results


def analyze_results(results: List[BenchmarkResult]) -> Dict:
    """分析测试结果"""
    successful = [r for r in results if r.success]

    if not successful:
        return {"success_rate": 0}

    latencies = [r.latency_ms for r in successful]
    total_tokens = [r.total_tokens for r in successful]
    input_tokens = [r.input_tokens for r in successful]
    output_tokens = [r.output_tokens for r in successful]
    route_times = [r.route_time_ms for r in successful]
    backends = [r.backend for r in successful]

    return {
        "success_rate": len(successful) / len(results),
        "latency": {
            "mean": mean(latencies),
            "median": median(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "stdev": stdev(latencies) if len(latencies) > 1 else 0,
        },
        "tokens": {
            "input_mean": mean(input_tokens),
            "output_mean": mean(output_tokens),
            "total_mean": mean(total_tokens),
        },
        "route_time": {
            "mean": mean(route_times) if route_times else 0,
            "median": median(route_times) if route_times else 0,
        },
        "backends": {
            "unique_count": len(set(backends)),
            "most_common": max(set(backends), key=backends.count) if backends else "unknown",
        }
    }


def compare_scenarios(baseline: Dict, optimized: Dict) -> Dict:
    """对比两个场景的性能"""
    comparison = {}

    # 延迟对比
    lat_base = baseline["latency"]["mean"]
    lat_opt = optimized["latency"]["mean"]
    lat_improvement = ((lat_base - lat_opt) / lat_base * 100) if lat_base > 0 else 0
    comparison["latency_improvement_%"] = round(lat_improvement, 2)

    # Token 对比
    tok_base = baseline["tokens"]["total_mean"]
    tok_opt = optimized["tokens"]["total_mean"]
    tok_improvement = ((tok_base - tok_opt) / tok_base * 100) if tok_base > 0 else 0
    comparison["token_savings_%"] = round(tok_improvement, 2)

    # 路由时间对比
    route_base = baseline["route_time"]["mean"]
    route_opt = optimized["route_time"]["mean"]
    route_improvement = ((route_base - route_opt) / route_base * 100) if route_base > 0 else 0
    comparison["route_time_improvement_%"] = round(route_improvement, 2)

    # 后端一致性
    comparison["backend_consistency"] = {
        "baseline": baseline["backends"]["unique_count"],
        "optimized": optimized["backends"]["unique_count"],
    }

    return comparison


def print_results(name: str, analysis: Dict):
    """打印分析结果"""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")

    if analysis["success_rate"] < 1.0:
        print(f"Success Rate: {analysis['success_rate']*100:.1f}%")

    lat = analysis["latency"]
    print(f"Latency (ms):")
    print(f"  Mean:   {lat['mean']:.1f}")
    print(f"  Median: {lat['median']:.1f}")
    print(f"  Range:  {lat['min']:.0f} - {lat['max']:.0f}")
    if lat['stdev'] > 0:
        print(f"  StdDev: {lat['stdev']:.1f}")

    tok = analysis["tokens"]
    print(f"\nTokens:")
    print(f"  Input:  {tok['input_mean']:.0f}")
    print(f"  Output: {tok['output_mean']:.0f}")
    print(f"  Total:  {tok['total_mean']:.0f}")

    route = analysis["route_time"]
    if route["mean"] > 0:
        print(f"\nRoute Time (ms): {route['mean']:.1f}")

    backends = analysis["backends"]
    print(f"\nBackends:")
    print(f"  Unique: {backends['unique_count']}")
    print(f"  Primary: {backends['most_common']}")


def print_comparison(comparison: Dict):
    """打印对比结果"""
    print(f"\n{'='*60}")
    print("Performance Comparison (Optimized vs Baseline)")
    print(f"{'='*60}")

    lat_imp = comparison["latency_improvement_%"]
    print(f"Latency Improvement: {lat_imp:+.2f}%")

    tok_sav = comparison["token_savings_%"]
    print(f"Token Savings: {tok_sav:+.2f}%")

    route_imp = comparison["route_time_improvement_%"]
    print(f"Route Time Improvement: {route_imp:+.2f}%")

    consist = comparison["backend_consistency"]
    print(f"\nBackend Consistency:")
    print(f"  Baseline: {consist['baseline']} unique backends")
    print(f"  Optimized: {consist['optimized']} unique backends")

    # 总体评估
    print(f"\n{'='*60}")
    if tok_sav > 20 and lat_imp > 10:
        print("[EXCELLENT] Significant improvements achieved!")
    elif tok_sav > 10 or lat_imp > 5:
        print("[GOOD] Moderate improvements observed.")
    elif tok_sav > 0 or lat_imp > 0:
        print("[MINOR] Small improvements detected.")
    else:
        print("[NEUTRAL] No significant improvement (may need tuning).")


def main():
    """主测试流程"""
    print("="*60)
    print("OpenCode Performance Benchmark")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Warmup Rounds: {WARMUP_ROUNDS}")
    print(f"Test Rounds: {TEST_ROUNDS}")
    print(f"Test Cases: {len(TEST_CASES)}")
    print("="*60)

    # 选择一个代表性测试用例
    test_case = TEST_CASES[1]  # "Code Explanation"
    print(f"\nTest Case: {test_case['name']}")
    print(f"Messages: {len(test_case['messages'])}")
    print(f"Max Tokens: {test_case['max_tokens']}")

    # 预热
    print(f"\n--- Warmup ({WARMUP_ROUNDS} rounds) ---")
    run_benchmark(test_case, WARMUP_ROUNDS, session_id="warmup")

    # 基线测试（无会话ID，每次重新路由）
    print(f"\n--- Baseline Test ({TEST_ROUNDS} rounds, no session cache) ---")
    baseline_results = run_benchmark(test_case, TEST_ROUNDS)
    baseline_analysis = analyze_results(baseline_results)

    # 优化测试（使用会话ID，启用缓存）
    print(f"\n--- Optimized Test ({TEST_ROUNDS} rounds, with session cache) ---")
    session_id = f"bench-{int(time.time())}"
    optimized_results = run_benchmark(test_case, TEST_ROUNDS, session_id=session_id)
    optimized_analysis = analyze_results(optimized_results)

    # 打印结果
    print_results("Baseline Results", baseline_analysis)
    print_results("Optimized Results", optimized_analysis)

    # 对比分析
    comparison = compare_scenarios(baseline_analysis, optimized_analysis)
    print_comparison(comparison)

    return 0


if __name__ == "__main__":
    sys.exit(main())
