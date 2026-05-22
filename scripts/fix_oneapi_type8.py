#!/usr/bin/env python3
import os
"""Fix: change channels back to type=8 (Custom) which only appends /chat/completions"""
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

# Load keys from env
for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

KEYS = {
    "zhipu": os.environ.get("ZHIPU_API_KEY", ""),
    "siliconflow": os.environ.get("SILICONFLOW_API_KEY", ""),
    "groq": os.environ.get("GROQ_API_KEY", ""),
    "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
    "nvidia": os.environ.get("NVIDIA_API_KEY", ""),
    "cerebras": os.environ.get("CEREBRAS_API_KEY", ""),
    "github": os.environ.get("GITHUB_TOKEN", ""),
    "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
    "longcat": os.environ.get("LONGCAT_API_KEY", ""),
    "chinamobile": os.environ.get("CHINAMOBILE_API_KEY", ""),
    "aliyun": os.environ.get("ALIYUN_API_KEY", ""),
    "volcengine": os.environ.get("VOLCENGINE_API_KEY", ""),
    "tencent": os.environ.get("TENCENT_API_KEY", ""),
    "google": os.environ.get("GOOGLE_AI_KEY", ""),
    "mistral": os.environ.get("MISTRAL_API_KEY", ""),
    "mistral-codestral": os.environ.get("MISTRAL_API_KEY", ""),
    "baidu": os.environ.get("BAIDU_API_KEY", ""),
    "cloudflare": os.environ.get("CLOUDFLARE_TOKEN", ""),
}

# All channels should use type=8 (Custom) with base_url that already includes /v1
# type=8 appends /chat/completions (NOT /v1/chat/completions)
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Setting all to type=8 + re-keying ===")
for ch in all_channels:
    name = ch.get("name", "?")
    ch["type"] = 8
    key = KEYS.get(name, "")
    if key:
        ch["key"] = key
    elif name in ("uncloseai-hermes", "uncloseai-qwen", "chat-ubi", "llm7", "pollinations"):
        ch["key"] = "none"
    r = api_put("/api/channel/", ch)
    status = "OK" if r.get("success") else "FAIL " + r.get("message", "")[:40]
    print("  " + name + ": " + status)

# Test
print("\n=== Testing (type=8) ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("qwen3-8b", "aliyun"),
    ("doubao-1-5-pro-256k", "volcengine"),
    ("openai", "pollinations"),
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
        print("  Y " + provider + " (" + model + "): " + str(ms) + "ms " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + provider + " (" + model + "): HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + " (" + model + "): " + str(e)[:60])
