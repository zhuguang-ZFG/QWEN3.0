#!/usr/bin/env python3
import os
"""Fix one-api: correct base_urls for the 5 working channels"""
import urllib.request, json, http.cookiejar, sys, os, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

BASE = "http://localhost:3001"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

def api_get(path):
    req = urllib.request.Request(BASE + path)
    return json.loads(opener.open(req).read().decode())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="PUT", headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

api_post("/api/user/login", {"username": "root", "password": "123456"})
print("Logged in.\n")

all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

# type=8 appends /v1/chat/completions
# So base_url should NOT include /v1
# For zhipu (/v4): can't use type=8, need special handling
FIXES = {
    "nvidia": {"base_url": "https://integrate.api.nvidia.com", "key": os.environ.get("NVIDIA_API_KEY","")},
    "deepseek": {"base_url": "https://api.deepseek.com", "key": os.environ.get("DEEPSEEK_API_KEY","")},
    "github": {"base_url": "https://models.inference.ai.azure.com", "key": os.environ.get("GITHUB_TOKEN","")},
    "chat-ubi": {"base_url": "https://ch.at", "key": "none"},
}

print("=== Fixing base_urls (remove /v1) ===")
for ch in all_channels:
    name = ch.get("name", "?")
    fix = FIXES.get(name)
    if not fix:
        continue
    ch["base_url"] = fix["base_url"]
    ch["key"] = fix["key"]
    ch["type"] = 8
    r = api_put("/api/channel/", ch)
    status = "OK" if r.get("success") else "FAIL"
    print("  " + name + ": " + status + " -> " + fix["base_url"])

# Test the fixed channels
print("\n=== Testing ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("microsoft/phi-4-mini-instruct", "nvidia"),
    ("deepseek-chat", "deepseek"),
    ("gpt-4o-mini", "github"),
    ("gpt-3", "chat-ubi"),
]

for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi in 2 words"}],
        "max_tokens": 10
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:30]
        print("  Y " + provider + " (" + model + "): " + str(ms) + "ms -> " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + provider + " (" + model + "): HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + " (" + model + "): " + str(e)[:60])
