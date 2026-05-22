#!/usr/bin/env python3
import os
"""Test: find the correct base_url format for one-api type=8
Since type=8 appends /v1/chat/completions, we need base_url WITHOUT /v1
For zhipu: correct URL is /api/paas/v4/chat/completions
So base_url should be /api/paas/v4 and we need type that appends /chat/completions only"""
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

all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")

# Since type=8 appends /v1/chat/completions, for providers that use /v1:
# base_url should be the root (without /v1)
# e.g. siliconflow: base_url = https://api.siliconflow.cn
#      -> one-api calls https://api.siliconflow.cn/v1/chat/completions ✓
#
# For zhipu which uses /v4:
# We can't use type=8 directly. Try type=1 with base_url = root
# type=1 might append /v1/chat/completions too, or just /chat/completions

# Test with siliconflow first (uses standard /v1)
for ch in all_channels:
    if ch.get("name") == "siliconflow":
        ch["base_url"] = "https://api.siliconflow.cn"
        ch["key"] = os.environ.get("SILICONFLOW_API_KEY", "")
        ch["type"] = 8
        api_put("/api/channel/", ch)
        print("siliconflow -> base=https://api.siliconflow.cn (type=8)")
        break

time.sleep(0.5)

body = json.dumps({
    "model": "Qwen/Qwen3-8B",
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
    content = data["choices"][0]["message"]["content"][:40]
    print("  Y siliconflow: " + str(ms) + "ms -> " + content)
except urllib.error.HTTPError as e:
    body_err = e.read().decode("utf-8", errors="replace")[:100]
    print("  N siliconflow: HTTP" + str(e.code) + " " + body_err)
except Exception as e:
    print("  N siliconflow: " + str(e)[:60])

# Now test groq (also uses /v1)
for ch in all_channels:
    if ch.get("name") == "groq":
        ch["base_url"] = "https://api.groq.com/openai"
        ch["key"] = os.environ.get("GROQ_API_KEY", "")
        ch["type"] = 8
        api_put("/api/channel/", ch)
        print("\ngroq -> base=https://api.groq.com/openai (type=8)")
        break

time.sleep(0.5)

body = json.dumps({
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_tokens": 5
}).encode()
req = urllib.request.Request(
    BASE + "/v1/chat/completions", data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    ms = int((time.time() - t0) * 1000)
    content = data["choices"][0]["message"]["content"][:40]
    print("  Y groq: " + str(ms) + "ms -> " + content)
except urllib.error.HTTPError as e:
    body_err = e.read().decode("utf-8", errors="replace")[:100]
    print("  N groq: HTTP" + str(e.code) + " " + body_err)
except Exception as e:
    print("  N groq: " + str(e)[:60])
