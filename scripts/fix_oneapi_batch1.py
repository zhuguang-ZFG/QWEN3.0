#!/usr/bin/env python3
import os
"""Fix one-api channels batch 1: fix base_urls and types"""
import urllib.request, json, http.cookiejar, sys, time, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:3001"
def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is required")
    return value

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

api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})
print("Logged in.\n")

# Fixes: channel_name -> {field: new_value}
# Key insight: type=8 (Custom) appends /chat/completions to base_url
# So base_url should be everything BEFORE /chat/completions
FIXES = {
    "zhipu": {"type": 1, "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    "siliconflow": {"type": 1, "base_url": "https://api.siliconflow.cn/v1"},
    "groq": {"type": 1, "base_url": "https://api.groq.com/openai/v1"},
    "openrouter": {"type": 1, "base_url": "https://openrouter.ai/api/v1"},
    "nvidia": {"type": 1, "base_url": "https://integrate.api.nvidia.com/v1"},
    "cerebras": {"type": 1, "base_url": "https://api.cerebras.ai/v1"},
    "github": {"type": 1, "base_url": "https://models.inference.ai.azure.com"},
    "deepseek": {"type": 1, "base_url": "https://api.deepseek.com"},
    "chinamobile": {"type": 1, "base_url": "https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1"},
    "chat-ubi": {"type": 1, "base_url": "https://ch.at/v1"},
    "llm7": {"type": 1, "base_url": "https://api.llm7.io/v1"},
    "uncloseai-hermes": {"type": 1, "base_url": "https://hermes.ai.unturf.com/v1"},
    "uncloseai-qwen": {"type": 1, "base_url": "https://qwen.ai.unturf.com/v1"},
    "longcat": {"type": 1, "base_url": "https://api.longcat.chat/v1"},
    "aliyun": {"type": 1, "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "volcengine": {"type": 1, "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "tencent": {"type": 1, "base_url": "https://api.hunyuan.cloud.tencent.com/v1"},
    "pollinations": {"type": 1, "base_url": "https://text.pollinations.ai/openai"},
}

# Get all channels
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Applying fixes ===")
fixed = 0
for ch in all_channels:
    name = ch.get("name", "?")
    fix = FIXES.get(name)
    if not fix:
        continue
    changed = False
    for field, value in fix.items():
        if ch.get(field) != value:
            ch[field] = value
            changed = True
    if changed:
        r = api_put("/api/channel/", ch)
        if r.get("success"):
            fixed += 1
            print("  " + name + ": FIXED")
        else:
            print("  " + name + ": FAIL " + r.get("message", "")[:60])
    else:
        print("  " + name + ": no change needed")

print("\nFixed: " + str(fixed) + " channels")

# Test the fixed channels
print("\n=== Testing fixed channels ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("Qwen/Qwen3-8B", "siliconflow"),
    ("llama-3.3-70b-versatile", "groq"),
    ("deepseek/deepseek-v4-flash:free", "openrouter"),
    ("gpt-4o", "github"),
]

for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi"}],
        "max_tokens": 10
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:30]
        print("  Y " + provider + " (" + model + "): " + str(ms) + "ms " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + provider + " (" + model + "): HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + " (" + model + "): " + str(e)[:60])
