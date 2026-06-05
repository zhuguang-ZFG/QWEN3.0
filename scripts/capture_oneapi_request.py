#!/usr/bin/env python3
import os

"""Point zhipu channel to echo server, send request, read echo log"""
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

# Find zhipu channel and point to echo server
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

for ch in all_channels:
    if ch.get("name") == "zhipu":
        ch["base_url"] = "http://localhost:9999"
        ch["key"] = os.environ.get("ZHIPU_API_KEY", "")
        ch["type"] = 8
        api_put("/api/channel/", ch)
        print("zhipu -> echo server (type=8, base=http://localhost:9999)")
        break

time.sleep(1)

# Clear echo log
open("/tmp/echo.log", "w").close()
time.sleep(0.5)

# Send request through one-api
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
body = json.dumps({"model": "glm-4-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
req = urllib.request.Request(
    BASE + "/v1/chat/completions",
    data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN},
)
try:
    resp = urllib.request.urlopen(req, timeout=5)
    print("Response: " + resp.read().decode()[:80])
except urllib.error.HTTPError as e:
    print("HTTP" + str(e.code) + ": " + e.read().decode("utf-8", "replace")[:80])
except Exception as e:
    print("Error: " + str(e)[:80])

time.sleep(1)

# Read echo log
print("\n=== ECHO LOG (what one-api actually sent) ===")
try:
    with open("/tmp/echo.log") as f:
        print(f.read())
except Exception:
    print("(empty or not found)")
