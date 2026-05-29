#!/usr/bin/env python3
"""End-to-end test: smart_router route() with one-api + fallback"""
import sys, os, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "/opt/lima-router")

# Load env
for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

from smart_router import route, ONEAPI_ENABLED

print("ONEAPI_ENABLED: " + str(ONEAPI_ENABLED))
print()

tests = [
    "你好",
    "写个快排算法",
    "解释微服务架构的优缺点",
]

for query in tests:
    t0 = time.time()
    r = route(query)
    ms = int((time.time() - t0) * 1000)
    backend = r.get("backend", "?")
    intent = r.get("intent", {}).get("intent", "?")
    answer = str(r.get("answer", ""))[:80]
    print("[" + str(ms) + "ms] " + query)
    print("  intent=" + intent + " backend=" + backend)
    print("  answer: " + answer)
    print()
