#!/usr/bin/env python3
import os
"""Fix one-api channel types for each provider"""
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
print("Logged in.")

# one-api channel type reference:
# 1=OpenAI, 3=Azure, 8=Custom(OpenAI-compat), 14=Anthropic
# 15=Baidu, 17=Ali(Tongyi), 18=Xunfei, 24=Groq
# 25=Cloudflare, 31=SiliconFlow, 33=Cohere
# 36=DeepSeek, 40=Volcengine, 41=Hunyuan

# Type 8 = Custom (OpenAI compatible) works for most providers
# that support /v1/chat/completions format

TYPE_MAP = {
    "zhipu": 8,
    "siliconflow": 31,
    "baidu": 15,
    "volcengine": 40,
    "aliyun": 17,
    "tencent": 41,
    "groq": 24,
    "mistral": 8,
    "mistral-codestral": 8,
    "nvidia": 8,
    "github": 8,
    "google": 8,
    "cerebras": 8,
    "openrouter": 8,
    "longcat": 14,
    "deepseek": 36,
    "chinamobile": 8,
    "cloudflare": 25,
    "uncloseai-hermes": 8,
    "uncloseai-qwen": 8,
    "chat-ubi": 8,
    "llm7": 8,
    "pollinations": 8,
}

print("\n=== Updating channel types ===")
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

fixed = 0
for ch in all_channels:
    name = ch.get("name", "?")
    current_type = ch.get("type", 1)
    expected_type = TYPE_MAP.get(name, 8)
    if current_type != expected_type:
        ch["type"] = expected_type
        r = api_put("/api/channel/", ch)
        if r.get("success"):
            fixed += 1
            print("  " + name + ": type " + str(current_type) + " -> " + str(expected_type))
        else:
            print("  " + name + ": FAIL " + r.get("message", "")[:60])
    else:
        print("  " + name + ": OK (type=" + str(current_type) + ")")

print("\nFixed: " + str(fixed) + " channels")

# Test again
print("\n=== Testing ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("Qwen/Qwen3-8B", "siliconflow"),
    ("llama-3.3-70b-versatile", "groq"),
]

for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi in 3 words"}],
        "max_tokens": 20
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
        content = data["choices"][0]["message"]["content"]
        print("  " + model + " [" + provider + "]: OK " + str(ms) + "ms -> " + content[:40])
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:120]
        print("  " + model + " [" + provider + "]: HTTP " + str(e.code) + " " + body_err)
    except Exception as e:
        print("  " + model + " [" + provider + "]: FAIL " + str(e)[:80])
