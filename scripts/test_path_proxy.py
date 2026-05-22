#!/usr/bin/env python3
import os
"""Final test: zhipu/github via Python path proxy through one-api"""
import urllib.request, json, http.cookiejar, sys, os, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

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
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

def api_get(path):
    req = urllib.request.Request(BASE + path)
    return json.loads(opener.open(req).read().decode())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="PUT", headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})

# Step 1: Test path proxy directly from host
print("=== Direct proxy test (from host) ===")
ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
GITHUB_KEY = os.environ.get("GITHUB_TOKEN", "")

for port, key, model, name in [
    (8901, ZHIPU_KEY, "glm-4-flash", "zhipu"),
    (8902, GITHUB_KEY, "gpt-4o-mini", "github"),
]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
    req = urllib.request.Request("http://localhost:" + str(port) + "/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        ms = int((time.time() - t0) * 1000)
        data = json.loads(resp.read().decode())
        c = data["choices"][0]["message"]["content"][:20]
        print("  " + name + " (:" + str(port) + "): OK " + str(ms) + "ms -> " + c)
    except Exception as e:
        print("  " + name + " (:" + str(port) + "): FAIL " + str(e)[:60])

# Step 2: Test from container gateway IP (simulating one-api container)
print("\n=== Proxy test via 10.88.0.1 (container gateway) ===")
for port, key, model, name in [
    (8901, ZHIPU_KEY, "glm-4-flash", "zhipu"),
    (8902, GITHUB_KEY, "gpt-4o-mini", "github"),
]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
    req = urllib.request.Request("http://10.88.0.1:" + str(port) + "/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        ms = int((time.time() - t0) * 1000)
        data = json.loads(resp.read().decode())
        c = data["choices"][0]["message"]["content"][:20]
        print("  " + name + " (10.88.0.1:" + str(port) + "): OK " + str(ms) + "ms -> " + c)
    except Exception as e:
        print("  " + name + " (10.88.0.1:" + str(port) + "): FAIL " + str(e)[:60])

# Step 3: Test through one-api (channels already point to 10.88.0.1)
print("\n=== Through one-api ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
for model, name in [("glm-4-flash", "zhipu"), ("gpt-4o-mini", "github")]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        ms = int((time.time() - t0) * 1000)
        data = json.loads(resp.read().decode())
        c = data["choices"][0]["message"]["content"][:20]
        print("  Y " + name + "/" + model + ": " + str(ms) + "ms -> " + c)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + name + "/" + model + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + name + "/" + model + ": " + str(e)[:60])
