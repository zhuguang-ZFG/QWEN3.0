#!/usr/bin/env python3
import os
"""Fix one-api: register groups in system config, then fix tokens"""
import urllib.request, json, http.cookiejar, sys, os

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

# Login
api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})
print("Logged in.")

# Step 1: Check system option for GroupRatio
print("\n=== Step 1: Check/Set Group Config ===")
try:
    opts = api_get("/api/option/")
    print("  Options keys: " + str(list(opts.get("data", {}).keys()))[:200])
except Exception as e:
    print("  Get options error: " + str(e)[:100])

# Step 2: Set GroupRatio to include our groups
# one-api uses GroupRatio option to define valid groups
group_ratio = {
    "default": 1,
    "trivial": 1,
    "code": 1,
    "general": 1,
    "thinking": 1,
    "vision": 1,
}
try:
    r = api_put("/api/option/", {"key": "GroupRatio", "value": json.dumps(group_ratio)})
    print("  GroupRatio set: " + str(r.get("success", False)))
except Exception as e:
    print("  GroupRatio error: " + str(e)[:100])

# Step 3: Verify token groups
print("\n=== Step 2: Verify Token Groups ===")
tokens = api_get("/api/token/?p=0&size=20")
for t in tokens.get("data", []):
    name = t.get("name", "?")
    group = t.get("group", "?")
    key = t.get("key", "")[:15]
    print("  " + name + ": group=" + group + " key=" + key + "...")

# Step 4: Test call with trivial token
print("\n=== Step 3: Test Call ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
body = json.dumps({
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_tokens": 10
}).encode()
req = urllib.request.Request(
    BASE + "/v1/chat/completions", data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
import time
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    ms = int((time.time() - t0) * 1000)
    content = data["choices"][0]["message"]["content"]
    print("  OK " + str(ms) + "ms: " + content[:60])
except urllib.error.HTTPError as e:
    body_err = e.read().decode("utf-8", errors="replace")[:200]
    print("  HTTP " + str(e.code) + ": " + body_err)
except Exception as e:
    print("  FAIL: " + str(e)[:100])
