#!/usr/bin/env python3
"""Fix one-api group configuration and test"""
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

def api_get(path):
    req = urllib.request.Request(BASE + path)
    return json.loads(opener.open(req).read().decode())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body,
        headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="PUT",
        headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read().decode())

# Login
api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})
print("Logged in.")

# Check tokens
print("\n=== Current Tokens ===")
tokens = api_get("/api/token/?p=0&size=20")
for t in tokens.get("data", []):
    name = t.get("name", "?")
    group = t.get("group", "default")
    key = t.get("key", "")[:20]
    print("  " + name + ": group=" + group + " key=" + key + "...")

# Check channels
print("\n=== Current Channels ===")
channels = api_get("/api/channel/?p=0&size=30")
for ch in channels.get("data", []):
    name = ch.get("name", "?")
    group = ch.get("group", "default")
    models = ch.get("models", "")[:40]
    print("  " + name + ": group=" + group + " models=" + models)
