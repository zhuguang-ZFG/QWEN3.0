#!/usr/bin/env python3
import os
"""Re-populate all one-api channel keys (they were wiped by PUT updates)"""
import urllib.request, json, http.cookiejar, sys, time, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:3001"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body,
        headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

def api_get(path):
    req = urllib.request.Request(BASE + path)
    return json.loads(opener.open(req).read().decode())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="PUT",
        headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

api_post("/api/user/login", {"username": "root", "password": "123456"})
print("Logged in.\n")

# Channel name -> API key mapping
KEYS = {
    "zhipu": os.environ.get("ZHIPU_API_KEY", ""),
    "siliconflow": os.environ.get("SILICONFLOW_API_KEY", ""),
    "baidu": os.environ.get("BAIDU_API_KEY", ""),
    "volcengine": os.environ.get("VOLCENGINE_API_KEY", ""),
    "aliyun": os.environ.get("ALIYUN_API_KEY", ""),
    "tencent": os.environ.get("TENCENT_API_KEY", ""),
    "groq": os.environ.get("GROQ_API_KEY", ""),
    "mistral": os.environ.get("MISTRAL_API_KEY", ""),
    "mistral-codestral": os.environ.get("MISTRAL_API_KEY", ""),
    "nvidia": os.environ.get("NVIDIA_API_KEY", ""),
    "github": os.environ.get("GITHUB_TOKEN", ""),
    "google": os.environ.get("GOOGLE_AI_KEY", ""),
    "cerebras": os.environ.get("CEREBRAS_API_KEY", ""),
    "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
    "longcat": os.environ.get("LONGCAT_API_KEY", ""),
    "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
    "chinamobile": os.environ.get("CHINAMOBILE_API_KEY", ""),
    "cloudflare": os.environ.get("CLOUDFLARE_TOKEN", ""),
    "uncloseai-hermes": "none",
    "uncloseai-qwen": "none",
    "chat-ubi": "none",
    "llm7": "none",
    "pollinations": "none",
}

# Get all channels
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Re-populating keys for " + str(len(all_channels)) + " channels ===")
fixed = 0
skipped = 0
for ch in all_channels:
    name = ch.get("name", "?")
    key = KEYS.get(name, "")
    if not key:
        print("  SKIP: " + name + " (no key in env)")
        skipped += 1
        continue
    ch["key"] = key
    r = api_put("/api/channel/", ch)
    if r.get("success"):
        fixed += 1
        klen = str(len(key))
        print("  OK: " + name + " (" + klen + " chars)")
    else:
        print("  FAIL: " + name + " -> " + r.get("message", "")[:60])

print("\nFixed: " + str(fixed) + ", Skipped: " + str(skipped))

# Quick test
print("\n=== Quick Test ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("llama-3.3-70b-versatile", "groq"),
    ("qwen3-8b", "aliyun"),
]
for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:30]
        print("  Y " + provider + ": " + str(ms) + "ms -> " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + provider + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + ": " + str(e)[:60])
