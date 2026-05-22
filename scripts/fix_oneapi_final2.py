#!/usr/bin/env python3
import os
"""Fix deepseek and github channels, test all working ones"""
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

all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

# Fix deepseek: add deepseek-chat to models list
# Fix github: base_url should stay as-is (no /v1 needed, it's Azure)
print("=== Fixing channels ===")
for ch in all_channels:
    name = ch.get("name", "")
    if name == "deepseek":
        ch["models"] = "deepseek-v4-pro,deepseek-v4-flash,deepseek-chat,deepseek-reasoner"
        ch["base_url"] = "https://api.deepseek.com"
        ch["key"] = os.environ.get("DEEPSEEK_API_KEY", "")
        ch["type"] = 8
        r = api_put("/api/channel/", ch)
        print("  deepseek: " + ("OK" if r.get("success") else "FAIL"))
    elif name == "github":
        # GitHub Models uses /chat/completions directly (no /v1 prefix)
        # So base_url should include the full path minus /chat/completions
        # Actually GitHub endpoint is: https://models.inference.ai.azure.com/chat/completions
        # type=8 appends /v1/chat/completions -> wrong
        # We need base_url that when /v1/chat/completions is appended gives the right URL
        # That's impossible. Let's try without /v1 in the path
        # Actually the correct approach: set base_url to root and hope type=8 works
        # OR: the GitHub endpoint might accept /v1/chat/completions too
        ch["base_url"] = "https://models.inference.ai.azure.com"
        ch["key"] = os.environ.get("GITHUB_TOKEN", "")
        ch["type"] = 8
        r = api_put("/api/channel/", ch)
        print("  github: " + ("OK" if r.get("success") else "FAIL"))

# Test all potentially working channels
print("\n=== Testing all channels ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("deepseek-chat", "deepseek"),
    ("deepseek-v4-flash", "deepseek"),
    ("gpt-4o-mini", "github"),
    ("gpt-3", "chat-ubi"),
    ("openai", "pollinations"),
]

for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi"}],
        "max_tokens": 5
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:30]
        print("  Y " + provider + "/" + model + ": " + str(ms) + "ms -> " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:80]
        print("  N " + provider + "/" + model + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + "/" + model + ": " + str(e)[:60])
