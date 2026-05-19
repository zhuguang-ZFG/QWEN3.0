#!/usr/bin/env python3
"""Fix one-api: set all channels to default group, use model-based routing"""
import urllib.request, json, http.cookiejar, sys, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:3001"
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
api_post("/api/user/login", {"username": "root", "password": "123456"})
print("Logged in.")

# Update all channels to include "default" group
print("\n=== Updating channels to default group ===")
channels = api_get("/api/channel/?p=0&size=50")
for ch in channels.get("data", []):
    ch_id = ch.get("id")
    name = ch.get("name", "?")
    group = ch.get("group", "")
    if "default" not in group:
        new_group = "default," + group if group else "default"
        ch["group"] = new_group
        r = api_put("/api/channel/", ch)
        if r.get("success"):
            print("  " + name + ": added default group")
        else:
            print("  " + name + ": FAIL " + r.get("message", ""))
    else:
        print("  " + name + ": already has default")

# Test with admin token (which is in default group)
print("\n=== Testing with admin token ===")
TOKEN = "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b"

tests = [
    ("glm-4-flash", "trivial"),
    ("codestral-latest", "code"),
    ("gpt-5", "thinking"),
]

for model, intent in tests:
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
        used_model = data.get("model", "?")
        print("  " + model + " (" + intent + "): OK " + str(ms) + "ms [" + used_model + "] " + content[:40])
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:150]
        print("  " + model + " (" + intent + "): HTTP " + str(e.code) + " " + body_err)
    except Exception as e:
        print("  " + model + " (" + intent + "): FAIL " + str(e)[:80])
