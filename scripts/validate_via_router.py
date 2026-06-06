#!/usr/bin/env python3
"""Correct validation: test keys via smart_router call_api (uses GFW proxy)"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "/opt/lima-router")

for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

from smart_router import BACKENDS, call_api

backends_to_test = [
    "zhipu_flash", "silicon_qwen8b", "baidu_ernie", "groq_llama4",
    "groq_llama8b", "nvidia_phi4", "github_gpt4o_mini", "google_flash_lite",
    "mistral_small", "cerebras_llama8b", "or_llama70b", "deepseek_flash",
    "longcat_lite", "chat_ubi", "pollinations", "aliyun_qwen3",
    "volcengine_doubao", "tencent_hunyuan", "chinamobile",
]

msgs = [{"role": "user", "content": "hi"}]

print("=== Key Validation via smart_router call_api ===\n")
ok = []
fail = []
for name in backends_to_test:
    if name not in BACKENDS:
        print("  SKIP " + name + " (not in BACKENDS)")
        continue
    t0 = time.time()
    answer = call_api(name, msgs, mt=10)
    ms = int((time.time() - t0) * 1000)
    if answer and len(answer) > 2 and "error" not in answer.lower()[:20]:
        ok.append(name)
        print("  Y " + name + ": " + str(ms) + "ms -> " + answer[:30])
    else:
        fail.append(name)
        preview = (answer or "None")[:50]
        print("  N " + name + ": " + str(ms) + "ms -> " + preview)

print("\n=== SUMMARY ===")
print("OK: " + str(len(ok)) + "/" + str(len(ok)+len(fail)))
print("  " + ", ".join(ok))
print("FAIL: " + str(len(fail)))
print("  " + ", ".join(fail))
