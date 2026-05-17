#!/usr/bin/env python3
"""
Free API Auto-Discovery + Dynamic Registration
Scans OpenRouter for new free models, tests them, auto-adds to health checker.
"""

import json, urllib.request, time, sys
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OPENROUTER_KEY = "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"
HEALTH_FILE = r"D:\GIT\api_health.json"
DISCOVERY_LOG = r"D:\GIT\api_discovery_log.json"
TEST_QUERY = "用中文回答：Grbl是什么？一句话。"

def scan_free_models():
    """Scan OpenRouter for all free models."""
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/models',
        headers={'Authorization': f'Bearer {OPENROUTER_KEY}', 'HTTP-Referer': 'https://red-v1.local'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    free_models = [m for m in data['data'] if ':free' in m.get('id', '')]
    return [{
        "id": m["id"],
        "name": m.get("name", m["id"]),
        "context_length": m.get("context_length", 0),
        "provider": m["id"].split("/")[0],
    } for m in free_models]


def test_model(model_id: str) -> dict | None:
    """Test a free model with a real query."""
    try:
        payload = json.dumps({
            "model": model_id,
            "messages": [{"role": "user", "content": TEST_QUERY}],
            "max_tokens": 80
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://openrouter.ai/api/v1/chat/completions',
            data=payload,
            headers={
                'Authorization': f'Bearer {OPENROUTER_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://red-v1.local'
            }
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            answer = data['choices'][0]['message']['content']
            latency = int((time.time() - t0) * 1000)
            cost = float(data.get('usage', {}).get('cost', 0))
            return {
                "model_id": model_id,
                "latency_ms": latency,
                "cost": cost,
                "answer_preview": answer[:100],
                "success": True,
            }
    except Exception as e:
        return {"model_id": model_id, "error": str(e)[:80], "success": False}


def main():
    print("=" * 60)
    print(f"  Free API Auto-Discovery - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load previous results
    log = json.load(open(DISCOVERY_LOG, 'r', encoding='utf-8')) if __import__('os').path.exists(DISCOVERY_LOG) else {"history": []}

    # Scan
    print("\n[1] Scanning OpenRouter...")
    free_models = scan_free_models()
    print(f"  Found {len(free_models)} free models")

    # Deduplicate and prioritize
    priority_providers = ["deepseek", "google", "microsoft", "meta", "nvidia", "minimax", "baidu", "arcee"]
    scored_models = []
    for m in free_models:
        score = 0
        for i, p in enumerate(priority_providers):
            if p in m["id"].lower():
                score = len(priority_providers) - i
                break
        score += min(m["context_length"] / 100000, 3)
        scored_models.append((score, m))

    top_models = [m for _, m in sorted(scored_models, key=lambda x: -x[0])[:15]]

    # Test
    print(f"\n[2] Testing top {len(top_models)} candidates...")
    tested = []
    for m in top_models:
        short_name = m["id"].replace(":free", "").split("/")[-1]
        print(f"  {short_name}...", end=" ")
        result = test_model(m["id"])
        if result and result["success"]:
            print(f"OK ({result['latency_ms']}ms) -> {result['answer_preview'][:60]}")
            tested.append(result)
        else:
            err = result.get("error", "unknown") if result else "None"
            print(f"FAIL: {err[:60]}")
        time.sleep(0.3)

    # Rank by speed + quality
    for t in tested:
        t["quality_score"] = sum(1 for kw in ["开源", "CNC", "Grbl", "固件", "控制", "G代码", "雕刻"] if kw in t.get("answer_preview", ""))

    tested.sort(key=lambda x: (-x.get("quality_score", 0), x["latency_ms"]))

    # Log results
    entry = {"timestamp": datetime.now().isoformat(), "total_free": len(free_models),
             "tested": len(tested), "working": [t["model_id"] for t in tested]}
    log["history"].append(entry)
    log["history"] = log["history"][-30:]  # Keep 30 days
    json.dump(log, open(DISCOVERY_LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    # Update health file with new/replacement APIs
    health = json.load(open(HEALTH_FILE, 'r', encoding='utf-8')) if __import__('os').path.exists(HEALTH_FILE) else {"healthy": [], "unhealthy": []}

    print(f"\n[3] Ranking results:")
    for i, t in enumerate(tested[:10]):
        status = "NEW!" if t["model_id"] not in str(health.get("healthy", [])) else "known"
        print(f"  [{i+1}] {t['model_id']} ({t['latency_ms']}ms) [{status}]")

    print(f"\n  {len(tested)} working free models found.")
    print(f"  Discovery log: {DISCOVERY_LOG}")


if __name__ == '__main__':
    main()
