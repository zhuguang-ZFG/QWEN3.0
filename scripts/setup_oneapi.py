#!/usr/bin/env python3
"""批量配置 one-api 渠道和分组 tokens"""
import http.cookiejar
import json
import os
import sys
import urllib.request

BASE = "http://localhost:3001"

def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Content-Type": "application/json"})
    resp = opener.open(req)
    return json.loads(resp.read().decode())

# Login
api("POST", "/api/user/login", {"username": "root", "password": require_env("ONEAPI_ADMIN_PASSWORD")})
print("Logged in.")

# 渠道列表: (name, type, key, base_url, models, groups, priority)
channels = [
    ("zhipu", 1, os.environ.get("ZHIPU_API_KEY", ""),
     "https://open.bigmodel.cn/api/paas/v4",
     "glm-4-flash,glm-4.7-flash", "trivial,general", 100),
    ("siliconflow", 1, os.environ.get("SILICONFLOW_API_KEY", ""),
     "https://api.siliconflow.cn/v1",
     "Qwen/Qwen3-8B,THUDM/glm-4-9b-chat,deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
     "trivial,general,thinking", 100),
    ("baidu", 1, os.environ.get("BAIDU_API_KEY", ""),
     "https://qianfan.baidubce.com/v2",
     "ernie-3.5-8k,ernie-speed-8k", "trivial,general", 90),
    ("volcengine", 1, os.environ.get("VOLCENGINE_API_KEY", ""),
     "https://ark.cn-beijing.volces.com/api/v3",
     "doubao-1-5-pro-256k", "general,thinking", 80),
    ("aliyun", 1, os.environ.get("ALIYUN_API_KEY", ""),
     "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "qwen3-8b,qwen-3-coder-plus", "general,code", 80),
    ("tencent", 1, os.environ.get("TENCENT_API_KEY", ""),
     "https://api.hunyuan.cloud.tencent.com/v1",
     "hunyuan-lite", "general", 70),
    ("groq", 1, os.environ.get("GROQ_API_KEY", ""),
     "https://api.groq.com/openai/v1",
     "llama-3.3-70b-versatile,openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3-32b,meta-llama/llama-4-scout-17b-16e-instruct,llama-3.1-8b-instant",
     "trivial,code,general,thinking", 95),
    ("mistral", 1, os.environ.get("MISTRAL_API_KEY", ""),
     "https://api.mistral.ai/v1",
     "mistral-large-latest,mistral-small-latest,mistral-medium-latest,devstral-small-latest,pixtral-large-latest",
     "code,general,thinking,vision", 85),
    ("mistral-codestral", 1, os.environ.get("MISTRAL_CODESTRAL_API_KEY", ""),
     "https://codestral.mistral.ai/v1",
     "codestral-latest",
     "code", 90),
    ("nvidia", 1, os.environ.get("NVIDIA_API_KEY", ""),
     "https://integrate.api.nvidia.com/v1",
     "nvidia/llama-3.3-nemotron-super-49b-v1,meta/llama-3.3-70b-instruct,qwen/qwen3-coder-480b-a35b-instruct,meta/llama-4-maverick-17b-128e-instruct,mistralai/mistral-large-3-675b-instruct-2512,microsoft/phi-4-mini-instruct",
     "code,general,thinking,trivial", 80),
    ("github", 1, os.environ.get("GITHUB_TOKEN", ""),
     "https://models.inference.ai.azure.com",
     "gpt-4o,gpt-4o-mini,gpt-5,o3-mini,o4-mini,DeepSeek-R1,Llama-3.3-70B-Instruct,Codestral-2501",
     "code,general,thinking,vision", 85),
    ("google", 1, os.environ.get("GOOGLE_AI_KEY", ""),
     "https://generativelanguage.googleapis.com/v1beta/openai",
     "gemini-3.1-flash-lite,gemini-2.5-flash,gemini-3-flash,gemma-3-27b-it",
     "general,thinking,vision", 80),
    ("cerebras", 1, os.environ.get("CEREBRAS_API_KEY", ""),
     "https://api.cerebras.ai/v1",
     "qwen-3-235b-a22b-instruct-2507,llama3.1-8b,gpt-oss-120b",
     "code,thinking", 75),
    ("openrouter", 1, os.environ.get("OPENROUTER_API_KEY", ""),
     "https://openrouter.ai/api/v1",
     "deepseek/deepseek-v4-flash:free,qwen/qwen3-coder:free,meta-llama/llama-3.3-70b-instruct:free,nvidia/llama-3.3-nemotron-super-49b-v1:free,qwen/qwen3-next-80b-a3b-instruct:free,nvidia/nemotron-3-super-120b-a12b:free,openai/gpt-oss-120b:free,z-ai/glm-4.5-air:free,minimax/minimax-m2.5:free,google/gemma-4-31b-it:free",
     "code,general,thinking", 60),
    ("longcat", 1, os.environ.get("LONGCAT_API_KEY", ""),
     "https://api.longcat.chat/anthropic/v1",
     "LongCat-Flash-Lite,LongCat-Flash-Chat,LongCat-Flash-Thinking,LongCat-2.0-Preview",
     "general,thinking,code", 85),
    ("deepseek", 1, os.environ.get("DEEPSEEK_API_KEY", ""),
     "https://api.deepseek.com/v1",
     "deepseek-v4-pro,deepseek-v4-flash",
     "thinking,code", 70),
    ("chinamobile", 1, os.environ.get("CHINAMOBILE_API_KEY", ""),
     "https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1",
     "minimax-m25",
     "general", 75),
    ("cloudflare", 1, os.environ.get("CLOUDFLARE_API_KEY", ""),
     "https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1",
     "cf-llama-vision,cf-mistral-small",
     "vision,general", 70),
    ("uncloseai-hermes", 1, "none",
     "https://hermes.ai.unturf.com/v1",
     "adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic",
     "trivial,general", 65),
    ("uncloseai-qwen", 1, "none",
     "https://qwen.ai.unturf.com/v1",
     "Qwen3.6-27B-UD-Q4_K_XL.gguf",
     "code,general", 65),
    ("chat-ubi", 1, "none",
     "https://ch.at/v1",
     "gpt-3",
     "trivial,general", 60),
    ("llm7", 1, "none",
     "https://api.llm7.io/v1",
     "auto",
     "general,code", 50),
    ("pollinations", 1, "none",
     "https://text.pollinations.ai/openai",
     "openai",
     "general", 40),
]

# 从云端 .env 读取实际 Key 替换 placeholder
KEY_MAP = {
    "GROQ_KEY_PLACEHOLDER": os.environ.get("GROQ_API_KEY", ""),
    "MISTRAL_KEY_PLACEHOLDER": os.environ.get("MISTRAL_API_KEY", ""),
    "NVIDIA_KEY_PLACEHOLDER": os.environ.get("NVIDIA_API_KEY", ""),
    "GITHUB_KEY_PLACEHOLDER": os.environ.get("GITHUB_TOKEN", ""),
    "GOOGLE_KEY_PLACEHOLDER": os.environ.get("GOOGLE_AI_KEY", ""),
    "CEREBRAS_KEY_PLACEHOLDER": os.environ.get("CEREBRAS_API_KEY", ""),
    "OPENROUTER_KEY_PLACEHOLDER": os.environ.get("OPENROUTER_API_KEY", ""),
    "LONGCAT_KEY_PLACEHOLDER": os.environ.get("LONGCAT_API_KEY", ""),
    "DEEPSEEK_KEY_PLACEHOLDER": os.environ.get("DEEPSEEK_API_KEY", ""),
    "CHINAMOBILE_KEY_PLACEHOLDER": os.environ.get("CHINAMOBILE_API_KEY", ""),
    "CLOUDFLARE_KEY_PLACEHOLDER": os.environ.get("CLOUDFLARE_API_KEY", ""),
}

# 创建渠道
print("\n=== Creating Channels ===")
created = 0
skipped = 0
for name, ch_type, key, base_url, models, groups, priority in channels:
    actual_key = KEY_MAP.get(key, key)
    if not actual_key or actual_key == "":
        print(f"  SKIP: {name} (no key)")
        skipped += 1
        continue
    body = {
        "name": name,
        "type": ch_type,
        "key": actual_key,
        "base_url": base_url,
        "models": models,
        "group": groups,
        "priority": priority,
        "weight": 1,
    }
    try:
        r = api("POST", "/api/channel/", body)
        if r.get("success"):
            created += 1
            print(f"  OK: {name} ({models[:40]}...)")
        else:
            print(f"  FAIL: {name} -> {r.get('message', '')}")
    except Exception as e:
        print(f"  ERR: {name} -> {str(e)[:60]}")

print(f"\nChannels: {created} created, {skipped} skipped")

# 创建分组 tokens
print("\n=== Creating Group Tokens ===")
groups_list = ["trivial", "code", "general", "thinking", "vision"]
for g in groups_list:
    body = {
        "name": f"lima-{g}",
        "remain_quota": 0,
        "expired_time": -1,
        "unlimited_quota": True,
        "group": g,
    }
    try:
        r = api("POST", "/api/token/", body)
        if r.get("success"):
            print(f"  {g}: token created")
        else:
            print(f"  {g}: FAIL -> {r.get('message', '')}")
    except Exception as e:
        print(f"  {g}: ERR -> {str(e)[:60]}")

print("\n=== Done ===")
