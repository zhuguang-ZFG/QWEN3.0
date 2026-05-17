#!/usr/bin/env python3
"""
Triple-API parallel distillation.
Uses Claude + DeepSeek + GPT simultaneously.
Each issue gets 3 answers, best one wins.
"""

import sys, os, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INPUT = r"D:\GIT\github_issues_training_data.json"
OUTPUT = r"D:\GIT\distilled_triple.json"
CHECKPOINT = r"D:\GIT\distilled_triple_checkpoint.json"

APIS = {
    "claude": {
        "url": "https://www.right.codes/claude-aws/v1/messages",
        "key": "YOUR_API_KEY_HERE",
        "model": "claude-sonnet-4-6",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/anthropic/v1/messages",
        "key": "YOUR_API_KEY_HERE",
        "model": "deepseek-chat",
    },
    "gpt": {
        "url": "https://www.right.codes/codex/v1/chat/completions",
        "key": "YOUR_API_KEY_HERE",
        "model": "gpt-5.5",
    },
}

SYSTEM = """你是CNC/3D打印/嵌入式系统专家。把Issue转成中文问答对。直接返回JSON: {"instruction":"中文问题","output":"中文回答"}。从讨论中提取实际解决方案，200-800字，引用代码和参数。不要任何markdown格式"""  # Keep it short for Claude/DeepSeek

WORKERS = 5  # Per API


def call_claude(prompt):
    payload = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 512, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(APIS["claude"]["url"], data=payload, headers={"Content-Type": "application/json", "x-api-key": APIS["claude"]["key"], "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["content"][0]["text"]


def call_deepseek(prompt):
    payload = json.dumps({"model": "deepseek-chat", "max_tokens": 512, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}).encode("utf-8")
    req = urllib.request.Request(APIS["deepseek"]["url"], data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {APIS['deepseek']['key']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["content"][0]["text"]


def call_gpt(prompt):
    payload = json.dumps({"model": "gpt-5.5", "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 512}).encode("utf-8")
    req = urllib.request.Request(APIS["gpt"]["url"], data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {APIS['gpt']['key']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def parse_json(text):
    """Extract JSON from model response."""
    if not text: return None
    text = text.strip()
    import re
    m = re.search(r'\{[^{}]*"instruction"[^{}]*"output"[^{}]*\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    if text.startswith("{"):
        try: return json.loads(text)
        except: pass
    return None


def distill_one(issue):
    title = issue.get("instruction", "")[:500]
    body = issue.get("instruction", "")[500:1500]
    source = issue["source"]
    comments = issue.get("comments", 0)
    prompt = f"Issue: {title}\n\n{body}\n\nSource: {source} ({comments} comments)"

    results = []
    for api_name, api_func in [("claude", call_claude), ("deepseek", call_deepseek), ("gpt", call_gpt)]:
        try:
            parsed = parse_json(api_func(prompt))
            if parsed and parsed.get("output", "") and len(parsed["output"]) > 50:
                parsed["source"] = source
                parsed["api"] = api_name
                results.append(parsed)
        except:
            pass

    if not results:
        return None

    # Pick the best: longest output with most technical content
    def score(r):
        o = r.get("output", "")
        return len(o) + o.count("`") * 10 + sum(o.count(k) for k in ["配置","参数","代码","文件","引脚","*"])

    best = max(results, key=score)
    return best


def main():
    print(f"Triple-API Distillation (3 APIs x {WORKERS} threads each)")

    issues = json.load(open(INPUT, 'r', encoding='utf-8'))
    valuable = [i for i in issues if i.get("comments", 0) >= 5]
    print(f"Total: {len(issues)}, Valuable: {len(valuable)}")

    cp = json.load(open(CHECKPOINT, 'r', encoding='utf-8')) if os.path.exists(CHECKPOINT) else {"done":[],"results":[]}
    done = set(cp["done"])
    results = cp["results"]
    print(f"Done: {len(done)}, Results: {len(results)}")

    pending = [i for i in valuable if i["source"] not in done]
    print(f"Pending: {len(pending)}")

    for b in range(0, len(pending), 50):
        batch = pending[b:b+50]
        print(f"\nBatch {b//50+1}: {len(batch)} issues")

        with ThreadPoolExecutor(max_workers=15) as ex:
            futs = {ex.submit(distill_one, iss): iss for iss in batch}
            for f in as_completed(futs):
                r = f.result()
                if r:
                    results.append(r)
                done.add(futs[f]["source"])

        print(f"Progress: {len(results)} pairs")
        json.dump({"done":list(done),"results":results}, open(CHECKPOINT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)

    json.dump(results, open(OUTPUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nDone: {len(results)} triple-distilled pairs -> {OUTPUT}")


if __name__ == '__main__':
    main()
