#!/usr/bin/env python3
"""Fix one-api token groups - assign each token to its correct group"""
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

# Get all tokens
tokens = api_get("/api/token/?p=0&size=20")
token_list = tokens.get("data", [])

# Fix token groups
GROUP_MAP = {
    "lima-trivial": "trivial",
    "lima-code": "code",
    "lima-general": "general",
    "lima-thinking": "thinking",
    "lima-vision": "vision",
}

print("\n=== Fixing Token Groups ===")
for t in token_list:
    name = t.get("name", "")
    expected_group = GROUP_MAP.get(name)
    if not expected_group:
        continue
    current_group = t.get("group", "default")
    if current_group == expected_group:
        print("  " + name + ": already correct (" + expected_group + ")")
        continue
    # Update token group
    token_id = t.get("id")
    update_data = {
        "id": token_id,
        "name": name,
        "group": expected_group,
        "remain_quota": t.get("remain_quota", 0),
        "expired_time": t.get("expired_time", -1),
        "unlimited_quota": t.get("unlimited_quota", True),
    }
    r = api_put("/api/token/", update_data)
    if r.get("success"):
        print("  " + name + ": fixed -> " + expected_group)
    else:
        print("  " + name + ": FAIL -> " + r.get("message", ""))
