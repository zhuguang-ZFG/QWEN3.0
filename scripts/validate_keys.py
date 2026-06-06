#!/usr/bin/env python3
"""Verify which API keys are still valid by direct calls (bypass one-api)"""
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

def test(name, url, key, model, timeout=10):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key and key != "none":
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=body, headers=headers)
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        ms = int((time.time() - t0) * 1000)
        data = json.loads(resp.read().decode())
        c = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:20]
        return "Y " + str(ms) + "ms: " + c
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        err = e.read().decode("utf-8", "replace")[:60]
        return "N HTTP" + str(e.code) + " " + str(ms) + "ms: " + err
    except Exception as e:
        return "N " + str(e)[:50]

print("=== Direct Key Validation (bypass one-api) ===\n")

tests = [
    ("zhipu", "https://open.bigmodel.cn/api/paas/v4/chat/completions",
     os.environ.get("ZHIPU_API_KEY",""), "glm-4-flash"),
    ("siliconflow", "https://api.siliconflow.cn/v1/chat/completions",
     os.environ.get("SILICONFLOW_API_KEY",""), "Qwen/Qwen3-8B"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions",
     os.environ.get("GROQ_API_KEY",""), "llama-3.1-8b-instant"),
    ("aliyun", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     os.environ.get("ALIYUN_API_KEY",""), "qwen3-8b"),
    ("nvidia", "https://integrate.api.nvidia.com/v1/chat/completions",
     os.environ.get("NVIDIA_API_KEY",""), "microsoft/phi-4-mini-instruct"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions",
     os.environ.get("OPENROUTER_API_KEY",""), "meta-llama/llama-3.3-70b-instruct:free"),
    ("cerebras", "https://api.cerebras.ai/v1/chat/completions",
     os.environ.get("CEREBRAS_API_KEY",""), "llama3.1-8b"),
    ("deepseek", "https://api.deepseek.com/v1/chat/completions",
     os.environ.get("DEEPSEEK_API_KEY",""), "deepseek-chat"),
    ("github", "https://models.inference.ai.azure.com/chat/completions",
     os.environ.get("GITHUB_TOKEN",""), "gpt-4o-mini"),
    ("chat-ubi", "https://ch.at/v1/chat/completions", "none", "gpt-3"),
    ("pollinations", "https://text.pollinations.ai/openai/chat/completions",
     "none", "openai"),
]

ok = []
fail = []
for name, url, key, model in tests:
    result = test(name, url, key, model)
    print("  " + name + ": " + result)
    if result.startswith("Y"):
        ok.append(name)
    else:
        fail.append(name)

print("\n=== SUMMARY ===")
print("Valid keys: " + str(len(ok)) + " -> " + ", ".join(ok))
print("Invalid/expired: " + str(len(fail)) + " -> " + ", ".join(fail))
