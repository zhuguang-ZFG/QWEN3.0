#!/usr/bin/env python3
import os
"""Fix: one-api container can't reach host's localhost, use host.containers.internal"""
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

# Find the host IP that the container can reach
# For podman: host.containers.internal or 10.88.0.1 (default gateway)
import subprocess
result = subprocess.run(["podman", "inspect", "one-api", "--format", "{{.NetworkSettings.Gateway}}"],
    capture_output=True, text=True)
gateway = result.stdout.strip()
print("Container gateway: " + gateway)

# Use gateway IP for nginx proxy
HOST_IP = gateway if gateway else "10.88.0.1"

all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("\n=== Fixing zhipu/github to use host IP ===")
for ch in all_channels:
    name = ch.get("name", "")
    if name == "zhipu":
        ch["type"] = 8
        ch["base_url"] = "http://" + HOST_IP + ":8901"
        ch["key"] = os.environ.get("ZHIPU_API_KEY", "")
        r = api_put("/api/channel/", ch)
        print("  zhipu -> " + ch["base_url"] + ": " + ("OK" if r.get("success") else "FAIL"))
    elif name == "github":
        ch["type"] = 8
        ch["base_url"] = "http://" + HOST_IP + ":8902"
        ch["key"] = os.environ.get("GITHUB_TOKEN", "")
        r = api_put("/api/channel/", ch)
        print("  github -> " + ch["base_url"] + ": " + ("OK" if r.get("success") else "FAIL"))

time.sleep(1)

# Test
print("\n=== Testing through one-api ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("glm-4-flash", "zhipu"),
    ("gpt-4o-mini", "github"),
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
