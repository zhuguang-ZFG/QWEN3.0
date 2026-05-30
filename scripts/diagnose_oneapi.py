#!/usr/bin/env python3
import os
"""Diagnose each one-api channel individually"""
import urllib.request, json, http.cookiejar, sys, time

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

api_post("/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})

TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")

# Get all channels and their first model
channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    channels.extend(data)

print("Testing " + str(len(channels)) + " channels via one-api...\n")

results = []
for ch in channels:
    name = ch.get("name", "?")
    models = ch.get("models", "")
    first_model = models.split(",")[0] if models else "unknown"
    ch_type = ch.get("type", 0)

    body = json.dumps({
        "model": first_model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    status = "?"
    detail = ""
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:30]
        status = "OK"
        detail = str(ms) + "ms: " + content
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        body_err = e.read().decode("utf-8", errors="replace")[:100]
        status = "HTTP" + str(e.code)
        detail = str(ms) + "ms: " + body_err
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        status = "ERR"
        detail = str(ms) + "ms: " + str(e)[:60]

    icon = "Y" if status == "OK" else "N"
    print(icon + " " + name + " [type=" + str(ch_type) + "] model=" + first_model)
    print("  " + status + " " + detail)
    print()
    results.append((name, status, first_model))

print("\n=== SUMMARY ===")
ok = [r for r in results if r[1] == "OK"]
fail = [r for r in results if r[1] != "OK"]
print("OK: " + str(len(ok)) + "/" + str(len(results)))
for name, st, model in ok:
    print("  + " + name + " (" + model + ")")
print("FAIL: " + str(len(fail)))
for name, st, model in fail:
    print("  - " + name + " [" + st + "] (" + model + ")")
