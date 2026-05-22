#!/usr/bin/env python3
import os
"""
Final one-api channel fix based on verified behavior:
- type=8 (Custom) appends /v1/chat/completions to base_url
- base_url should NOT include /v1 for standard providers
- Non-standard paths (zhipu /v4, volcengine /v3, github no-/v1) need native types
- GFW-blocked endpoints need proxy (configured via container env)
"""
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

# Verified rule: type=8 appends /v1/chat/completions
# Standard /v1 providers: base_url = root (without /v1)
# Non-standard: use native types or accept direct-only
CHANNEL_CONFIG = {
    # === Standard /v1 providers (type=8, base without /v1) ===
    "siliconflow":      (8, "https://api.siliconflow.cn", "SILICONFLOW_API_KEY"),
    "groq":             (8, "https://api.groq.com/openai", "GROQ_API_KEY"),
    "deepseek":         (8, "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "cerebras":         (8, "https://api.cerebras.ai", "CEREBRAS_API_KEY"),
    "openrouter":       (8, "https://openrouter.ai/api", "OPENROUTER_API_KEY"),
    "aliyun":           (8, "https://dashscope.aliyuncs.com/compatible-mode", "ALIYUN_API_KEY"),
    "tencent":          (8, "https://api.hunyuan.cloud.tencent.com", "TENCENT_API_KEY"),
    "nvidia":           (8, "https://integrate.api.nvidia.com", "NVIDIA_API_KEY"),
    "chinamobile":      (8, "https://maas.gd.chinamobile.com:36007/ai/uifm/open", "CHINAMOBILE_API_KEY"),
    "llm7":             (8, "https://api.llm7.io", None),
    "uncloseai-hermes": (8, "https://hermes.ai.unturf.com", None),
    "uncloseai-qwen":   (8, "https://qwen.ai.unturf.com", None),
    "chat-ubi":         (8, "https://ch.at", None),
    "pollinations":     (8, "https://text.pollinations.ai/openai", None),
    # === Non-standard paths (use native one-api types) ===
    "zhipu":            (18, "https://open.bigmodel.cn", "ZHIPU_API_KEY"),
    "volcengine":       (40, "https://ark.cn-beijing.volces.com/api/v3", "VOLCENGINE_API_KEY"),
    "baidu":            (15, "https://qianfan.baidubce.com", "BAIDU_API_KEY"),
    # === Special endpoints ===
    "github":           (3, "https://models.inference.ai.azure.com", "GITHUB_TOKEN"),
    "longcat":          (14, "https://api.longcat.chat", "LONGCAT_API_KEY"),
    # === GFW-blocked (need proxy, type=8 with root domain) ===
    "mistral":          (8, "https://api.mistral.ai", "MISTRAL_API_KEY"),
    "mistral-codestral":(8, "https://codestral.mistral.ai", "MISTRAL_API_KEY"),
    "google":           (8, "https://generativelanguage.googleapis.com/v1beta/openai", "GOOGLE_AI_KEY"),
    "cloudflare":       (25, "https://api.cloudflare.com/client/v4/accounts/" + os.environ.get("CLOUDFLARE_ACCOUNT_ID","") + "/ai", "CLOUDFLARE_TOKEN"),
}

# Get all channels
all_channels = []
for page in range(5):
    resp = api_get("/api/channel/?p=" + str(page) + "&size=10")
    data = resp.get("data", [])
    if not data:
        break
    all_channels.extend(data)

print("=== Applying definitive fixes to " + str(len(all_channels)) + " channels ===")
fixed = 0
for ch in all_channels:
    name = ch.get("name", "?")
    config = CHANNEL_CONFIG.get(name)
    if not config:
        print("  SKIP: " + name + " (no config)")
        continue
    ch_type, base_url, key_env = config
    ch["type"] = ch_type
    ch["base_url"] = base_url
    if key_env:
        ch["key"] = os.environ.get(key_env, "")
    else:
        ch["key"] = "none"
    r = api_put("/api/channel/", ch)
    if r.get("success"):
        fixed += 1
        print("  OK: " + name + " (type=" + str(ch_type) + ", base=" + base_url[:40] + ")")
    else:
        print("  FAIL: " + name + " -> " + r.get("message", "")[:60])

print("\nFixed: " + str(fixed) + "/" + str(len(all_channels)))

# Test all channels
print("\n=== Testing all channels ===")
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")
tests = [
    ("Qwen/Qwen3-8B", "siliconflow"),
    ("llama-3.1-8b-instant", "groq"),
    ("deepseek-chat", "deepseek"),
    ("llama3.1-8b", "cerebras"),
    ("qwen3-8b", "aliyun"),
    ("gpt-4o-mini", "github"),
    ("gpt-3", "chat-ubi"),
    ("openai", "pollinations"),
    ("glm-4-flash", "zhipu"),
    ("minimax-m25", "chinamobile"),
    ("auto", "llm7"),
]

ok_count = 0
for model, provider in tests:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "say hi"}],
        "max_tokens": 5
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        ms = int((time.time() - t0) * 1000)
        content = data["choices"][0]["message"]["content"][:25]
        ok_count += 1
        print("  Y " + provider + "/" + model + ": " + str(ms) + "ms " + content)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:60]
        print("  N " + provider + "/" + model + ": HTTP" + str(e.code) + " " + body_err)
    except Exception as e:
        print("  N " + provider + "/" + model + ": " + str(e)[:50])

print("\nResult: " + str(ok_count) + "/" + str(len(tests)) + " passed")
