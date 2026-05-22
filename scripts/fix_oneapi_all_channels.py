#!/usr/bin/env python3
import os
"""Fix ALL one-api channels to include default group"""
import urllib.request, json, http.cookiejar, sys, time, os

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

api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})
print("Logged in.")

# Get ALL channels (page through if needed)
print("\n=== Fixing ALL channels ===")
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("Total channels: " + str(len(all_channels)))

fixed = 0
for ch in all_channels:
    ch_id = ch.get("id")
    name = ch.get("name", "?")
    group = ch.get("group", "")
    if "default" in group.split(","):
        print("  " + name + ": OK (has default)")
        continue
    new_group = "default," + group if group else "default"
    ch["group"] = new_group
    r = api_put("/api/channel/", ch)
    if r.get("success"):
        fixed = fixed + 1
        print("  " + name + ": FIXED -> " + new_group)
    else:
        print("  " + name + ": FAIL " + r.get("message", "")[:60])

print("\nFixed: " + str(fixed) + " channels")

# Test
print("\n=== Testing ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
models_to_test = ["glm-4-flash", "ernie-3.5-8k", "Qwen/Qwen3-8B", "codestral-latest"]

for model in models_to_test:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi"}],
        "max_tokens": 15
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"]
        print("  " + model + ": OK " + str(ms) + "ms -> " + content[:40])
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:100]
        print("  " + model + ": HTTP " + str(e.code) + " " + body_err)
    except Exception as e:
        print("  " + model + ": FAIL " + str(e)[:80])
