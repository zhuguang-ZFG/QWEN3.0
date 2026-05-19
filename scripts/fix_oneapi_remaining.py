#!/usr/bin/env python3
"""Fix remaining 6 channels with specific issues"""
import urllib.request, json, http.cookiejar, sys, os, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for line in open("/opt/lima-router/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

BASE = "http://localhost:3001"
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

api_post("/api/user/login", {"username": "root", "password": "123456"})
print("Logged in.\n")

all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Fixing remaining channels ===")
for ch in all_channels:
    name = ch.get("name", "")

    if name == "deepseek":
        # Fix: add deepseek-chat to models list
        ch["models"] = "deepseek-v4-pro,deepseek-v4-flash,deepseek-chat,deepseek-reasoner"
        ch["key"] = os.environ.get("DEEPSEEK_API_KEY", "")
        api_put("/api/channel/", ch)
        print("  deepseek: added deepseek-chat to models")

    elif name == "github":
        # Fix: GitHub uses /chat/completions directly (no /v1)
        # type=8 adds /v1 which is wrong. Use type=1 with base_url as-is
        # Actually type=1 in one-api for OpenAI also adds /v1
        # The only way is to use the full URL as base and hope type=8 works
        # OR: just accept github can't work through one-api (use direct fallback)
        # Let's try type=1 with empty base_url (uses default OpenAI behavior)
        ch["type"] = 8
        ch["base_url"] = "https://models.github.ai"
        ch["key"] = os.environ.get("GITHUB_TOKEN", "")
        ch["models"] = "gpt-4o,gpt-4o-mini,gpt-5,o3-mini,o4-mini,DeepSeek-R1,Llama-3.3-70B-Instruct,Codestral-2501"
        api_put("/api/channel/", ch)
        print("  github: try models.github.ai (type=8)")

    elif name == "zhipu":
        # Fix: zhipu uses /api/paas/v4/chat/completions
        # type=18 (Xunfei) is wrong for zhipu
        # zhipu is OpenAI-compatible at /api/paas/v4/
        # Since type=8 adds /v1, we need base without /v1
        # zhipu path: /api/paas/v4/chat/completions
        # If type=8 adds /v1/chat/completions, no base_url works
        # Try: type=1 with base_url = https://open.bigmodel.cn/api/paas/v4
        # type=1 might just add /chat/completions (not /v1/chat/completions)
        ch["type"] = 1
        ch["base_url"] = "https://open.bigmodel.cn/api/paas/v4"
        ch["key"] = os.environ.get("ZHIPU_API_KEY", "")
        api_put("/api/channel/", ch)
        print("  zhipu: type=1, base=/api/paas/v4")

    elif name == "chinamobile":
        # Fix: chinamobile uses /ai/uifm/open/v1/chat/completions
        # type=8 adds /v1/chat/completions
        # So base should be: https://maas.gd.chinamobile.com:36007/ai/uifm/open
        ch["type"] = 8
        ch["base_url"] = "https://maas.gd.chinamobile.com:36007/ai/uifm/open"
        ch["key"] = os.environ.get("CHINAMOBILE_API_KEY", "")
        api_put("/api/channel/", ch)
        print("  chinamobile: base without /v1")

time.sleep(1)

# Test all
print("\n=== Testing ===")
TOKEN = "sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b"
tests = [
    ("deepseek-chat", "deepseek"),
    ("gpt-4o-mini", "github"),
    ("glm-4-flash", "zhipu"),
    ("minimax-m25", "chinamobile"),
    ("llama-3.1-8b-instant", "groq"),
    ("llama3.1-8b", "cerebras"),
    ("gpt-3", "chat-ubi"),
    ("openai", "pollinations"),
    ("auto", "llm7"),
]

ok = 0
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
        content = data["choices"][0]["message"]["content"][:25]
        ok += 1
        print("  Y " + provider + "/" + model + ": " + str(ms) + "ms " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:60]
        print("  N " + provider + "/" + model + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + "/" + model + ": " + str(e)[:50])

print("\nResult: " + str(ok) + "/" + str(len(tests)) + " passed")
