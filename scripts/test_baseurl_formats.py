#!/usr/bin/env python3
import os
"""Test: try base_url WITHOUT /v1 for type=1 channels
Theory: type=1 (OpenAI) appends /v1/chat/completions to base_url
So base_url should be the root domain without /v1"""
import urllib.request, json, http.cookiejar, sys, time, os

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
print("Logged in.\n")

# Get zhipu channel and try different base_url formats
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")

# Test different base_url formats for zhipu
zhipu_ch = None
for ch in all_channels:
    if ch.get("name") == "zhipu":
        zhipu_ch = ch
        break

if not zhipu_ch:
    print("zhipu channel not found!")
    sys.exit(1)

# Try 3 formats:
formats = [
    ("type=1, url=https://open.bigmodel.cn/api/paas/v4", 1, "https://open.bigmodel.cn/api/paas/v4"),
    ("type=1, url=https://open.bigmodel.cn/api/paas", 1, "https://open.bigmodel.cn/api/paas"),
    ("type=1, url=https://open.bigmodel.cn", 1, "https://open.bigmodel.cn"),
]

for desc, ch_type, url in formats:
    zhipu_ch["type"] = ch_type
    zhipu_ch["base_url"] = url
    zhipu_ch["key"] = os.environ.get("ZHIPU_API_KEY", "")
    api_put("/api/channel/", zhipu_ch)
    time.sleep(0.5)

    body = json.dumps({
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:20]
        print("Y " + desc + " -> " + str(ms) + "ms: " + content)
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        code = e.code
        print("N " + desc + " -> HTTP" + str(code) + " " + str(ms) + "ms")
    except Exception as e:
        print("N " + desc + " -> " + str(e)[:40])
