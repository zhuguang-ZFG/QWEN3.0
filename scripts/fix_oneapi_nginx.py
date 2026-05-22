#!/usr/bin/env python3
import os
"""Fix zhipu/github/chinamobile via nginx proxy, then test all channels"""
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

# Step 1: First test nginx proxy directly
print("=== Testing nginx proxy directly ===")
ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
GITHUB_KEY = os.environ.get("GITHUB_TOKEN", "")

# Test zhipu via nginx
body = json.dumps({"model": "glm-4-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
req = urllib.request.Request("http://localhost:8901/v1/chat/completions", data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + ZHIPU_KEY})
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=10)
    ms = int((time.time() - t0) * 1000)
    data = json.loads(resp.read().decode())
    c = data["choices"][0]["message"]["content"][:20]
    print("  zhipu via nginx:8901: OK " + str(ms) + "ms -> " + c)
except Exception as e:
    print("  zhipu via nginx:8901: FAIL " + str(e)[:80])

# Test github via nginx
body = json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
req = urllib.request.Request("http://localhost:8902/v1/chat/completions", data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + GITHUB_KEY})
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=10)
    ms = int((time.time() - t0) * 1000)
    data = json.loads(resp.read().decode())
    c = data["choices"][0]["message"]["content"][:20]
    print("  github via nginx:8902: OK " + str(ms) + "ms -> " + c)
except Exception as e:
    print("  github via nginx:8902: FAIL " + str(e)[:80])

# Step 2: Point one-api channels to nginx proxy
print("\n=== Pointing one-api channels to nginx ===")
for ch in all_channels:
    name = ch.get("name", "")
    if name == "zhipu":
        ch["type"] = 8
        ch["base_url"] = "http://localhost:8901"
        ch["key"] = ZHIPU_KEY
        r = api_put("/api/channel/", ch)
        print("  zhipu -> localhost:8901: " + ("OK" if r.get("success") else "FAIL"))
    elif name == "github":
        ch["type"] = 8
        ch["base_url"] = "http://localhost:8902"
        ch["key"] = GITHUB_KEY
        r = api_put("/api/channel/", ch)
        print("  github -> localhost:8902: " + ("OK" if r.get("success") else "FAIL"))
    elif name == "chinamobile":
        ch["type"] = 8
        ch["base_url"] = "https://maas.gd.chinamobile.com:36007/ai/uifm/open"
        ch["key"] = os.environ.get("CHINAMOBILE_API_KEY", "")
        ch["models"] = "minimax-m25,MiniMax-M1"
        r = api_put("/api/channel/", ch)
        print("  chinamobile: fixed models + base")

time.sleep(1)

# Step 3: Test through one-api
print("\n=== Testing through one-api ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("gpt-4o-mini", "github"),
    ("minimax-m25", "chinamobile"),
    ("deepseek-chat", "deepseek"),
    ("llama-3.1-8b-instant", "groq"),
    ("llama3.1-8b", "cerebras"),
    ("gpt-3", "chat-ubi"),
    ("openai", "pollinations"),
    ("auto", "llm7"),
]

ok = 0
for model, provider in tests:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:25]
        ok += 1
        print("  Y " + provider + "/" + model + ": " + str(ms) + "ms " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:60]
        print("  N " + provider + "/" + model + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + "/" + model + ": " + str(e)[:50])

print("\nResult: " + str(ok) + "/" + str(len(tests)) + " passed")
