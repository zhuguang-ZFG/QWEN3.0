#!/usr/bin/env python3
"""API Health Checker. Daily run updates api_health.json for router_v3."""
import json, urllib.request, time, sys, os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TEST_PROMPT = "Say OK."

APIS = {
    "claude_rightcodes": {"url":"https://www.right.codes/claude-aws/v1/messages","key":os.environ.get("CLAUDE_API_KEY",""),"model":"claude-sonnet-4-6","type":"anthropic","priority":1},
    "deepseek_official": {"url":"https://api.deepseek.com/anthropic/v1/messages","key":os.environ.get("DEEPSEEK_API_KEY",""),"model":"deepseek-chat","type":"anthropic","priority":2},
    "gpt55_rightcodes": {"url":"https://www.right.codes/codex/v1/chat/completions","key":os.environ.get("GPT_API_KEY",""),"model":"gpt-5.5","type":"openai","priority":2},
    "nvidia_dsv4": {"url":"https://integrate.api.nvidia.com/v1/chat/completions","key":os.environ.get("NVIDIA_API_KEY",""),"model":"deepseek-ai/deepseek-v4-flash","type":"openai","priority":3},
    "openrouter_dsv4_free": {"url":"https://openrouter.ai/api/v1/chat/completions","key":os.environ.get("OPENROUTER_API_KEY",""),"model":"deepseek/deepseek-v4-flash:free","type":"openrouter","priority":3},
    "openrouter_minimax_free": {"url":"https://openrouter.ai/api/v1/chat/completions","key":os.environ.get("OPENROUTER_API_KEY",""),"model":"minimax/minimax-m2.5:free","type":"openrouter","priority":4},
    "openrouter_nemotron_free": {"url":"https://openrouter.ai/api/v1/chat/completions","key":os.environ.get("OPENROUTER_API_KEY",""),"model":"nvidia/nemotron-3-super-120b-a12b:free","type":"openrouter","priority":4},
}

def check_all():
    results = {"timestamp": datetime.now().isoformat(), "healthy": [], "unhealthy": []}
    for name, cfg in APIS.items():
        print(f"  {name}...", end=" ")
        try:
            t0 = time.time(); t = cfg["type"]
            if t == "openai":
                p = json.dumps({"model":cfg["model"],"messages":[{"role":"user","content":TEST_PROMPT}],"max_tokens":10}).encode()
                r = urllib.request.Request(cfg["url"],data=p,headers={"Content-Type":"application/json","Authorization":f"Bearer {cfg['key']}"})
            elif t == "anthropic":
                p = json.dumps({"model":cfg["model"],"max_tokens":10,"system":TEST_PROMPT,"messages":[{"role":"user","content":"t"}]}).encode()
                h = {"Content-Type":"application/json","anthropic-version":"2023-06-01"}
                if "deepseek" in cfg["url"]: h["Authorization"] = f"Bearer {cfg['key']}"
                else: h["x-api-key"] = cfg["key"]
                r = urllib.request.Request(cfg["url"],data=p,headers=h)
            elif t == "openrouter":
                p = json.dumps({"model":cfg["model"],"messages":[{"role":"user","content":TEST_PROMPT}],"max_tokens":10}).encode()
                r = urllib.request.Request(cfg["url"],data=p,headers={"Content-Type":"application/json","Authorization":f"Bearer {cfg['key']}","HTTP-Referer":"https://red-v1.local"})
            with urllib.request.urlopen(r,timeout=15) as resp:
                lat = int((time.time()-t0)*1000)
                results["healthy"].append({"name":name,"model":cfg["model"],"latency_ms":lat,"priority":cfg["priority"]})
                print(f"OK ({lat}ms)")
        except Exception as e:
            results["unhealthy"].append({"name":name,"model":cfg["model"],"error":str(e)[:80]})
            print("FAIL")

    with open(r"D:\GIT\api_config.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(r"D:\GIT\api_health.json", 'w', encoding='utf-8') as f:
        json.dump({"healthy":[h["name"] for h in results["healthy"]],"unhealthy":[u["name"] for u in results["unhealthy"]],"updated":results["timestamp"]}, f, ensure_ascii=False, indent=2)
    print(f"\n  Healthy: {len(results['healthy'])} | Unhealthy: {len(results['unhealthy'])}")

if __name__ == '__main__': check_all()
