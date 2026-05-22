#!/usr/bin/env python3
"""Debug: check what one-api actually sends to upstream by testing with a known-good endpoint"""
import urllib.request, json, http.cookiejar, sys, time

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

api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})

# Get channel details to check keys
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Channel Key Check ===")
for ch in all_channels:
    name = ch.get("name", "?")
    key = ch.get("key", "")
    base_url = ch.get("base_url", "")
    ch_type = ch.get("type", 0)
    key_preview = key[:15] + "..." if len(key) > 15 else key
    print(name + " [type=" + str(ch_type) + "]")
    print("  url: " + base_url)
    print("  key: " + key_preview + " (" + str(len(key)) + " chars)")
    print()

# Direct test: call siliconflow directly (bypass one-api) to verify key works
print("\n=== Direct API Test (bypass one-api) ===")
import os
sf_key = os.environ.get("SILICONFLOW_API_KEY", "")
print("SiliconFlow key from env: " + sf_key[:15] + "... (" + str(len(sf_key)) + " chars)")

body = json.dumps({
    "model": "Qwen/Qwen3-8B",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 5
}).encode()
req = urllib.request.Request(
    "https://api.siliconflow.cn/v1/chat/completions",
    data=body,
    headers={"Content-Type": "application/json",
             "Authorization": "Bearer " + sf_key})
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    ms = int((time.time() - t0) * 1000)
    content = data["choices"][0]["message"]["content"][:30]
    print("Direct SiliconFlow: OK " + str(ms) + "ms -> " + content)
except Exception as e:
    print("Direct SiliconFlow: FAIL " + str(e)[:80])
