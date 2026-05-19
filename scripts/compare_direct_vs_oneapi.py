#!/usr/bin/env python3
"""Compare: direct call vs one-api call for the same model"""
import urllib.request, json, sys, os, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load env
for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
ALIYUN_KEY = os.environ.get("ALIYUN_API_KEY", "")

def call(url, key, model):
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
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        c = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:20]
        return "OK " + str(ms) + "ms: " + c
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        err = e.read().decode("utf-8", errors="replace")[:80]
        return "HTTP" + str(e.code) + " " + str(ms) + "ms: " + err
    except Exception as e:
        return "ERR: " + str(e)[:60]

print("=== Direct vs one-api comparison ===\n")

# Test 1: Zhipu (glm-4-flash)
print("1. Zhipu (glm-4-flash)")
print("   Direct: " + call("https://open.bigmodel.cn/api/paas/v4/chat/completions", ZHIPU_KEY, "glm-4-flash"))
print("   one-api: " + call("http://127.0.0.1:3001/v1/chat/completions", "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b", "glm-4-flash"))
print()

# Test 2: Groq (llama-3.3-70b-versatile)
print("2. Groq (llama-3.3-70b-versatile)")
print("   Direct: " + call("https://api.groq.com/openai/v1/chat/completions", GROQ_KEY, "llama-3.3-70b-versatile"))
print("   one-api: " + call("http://127.0.0.1:3001/v1/chat/completions", "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b", "llama-3.3-70b-versatile"))
print()

# Test 3: Aliyun (qwen3-8b)
print("3. Aliyun (qwen3-8b)")
print("   Direct: " + call("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", ALIYUN_KEY, "qwen3-8b"))
print("   one-api: " + call("http://127.0.0.1:3001/v1/chat/completions", "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b", "qwen3-8b"))
print()

# Test 4: ch.at (no key needed)
print("4. ch.at (gpt-3, no key)")
print("   Direct: " + call("https://ch.at/v1/chat/completions", "none", "gpt-3"))
print("   one-api: " + call("http://127.0.0.1:3001/v1/chat/completions", "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b", "gpt-3"))
