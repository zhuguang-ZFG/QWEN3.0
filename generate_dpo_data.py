#!/usr/bin/env python3
"""Generate real DPO preference pairs using API: chosen=good, rejected=bad."""

import json, urllib.request, time, random, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

APIS = [
    ("claude", "https://www.right.codes/claude-aws/v1/messages", "YOUR_API_KEY_HERE", "claude-sonnet-4-6", "anthropic"),
    ("deepseek", "https://api.deepseek.com/anthropic/v1/messages", "YOUR_API_KEY_HERE", "deepseek-chat", "anthropic"),
]

OUTPUT = r"D:\GIT\dpo_preferences.json"
CHECKPOINT = r"D:\GIT\dpo_checkpoint.json"

QUESTIONS = [
    ("cnc", "Grbl归零时X轴不动、Y和Z正常，有哪些可能原因？逐条列出"),
    ("cnc", "如何计算CNC雕刻机的steps/mm？给公式和代码"),
    ("cnc", "CNC主轴转速和进给速度的问题，影响加工质量"),
    ("esp32", "ESP32 GPIO12导致启动失败的根本原因及解决方案"),
    ("esp32", "ESP32-S3的PSRAM配置和内存分配策略"),
    ("reverse", "从STM32固件中提取Bootloader并分析启动流程"),
    ("reverse", "用JTAG调试器破解已禁调试的ESP32的方法"),
    ("gcode", "GRBL的planner缓冲区满了的处理策略，给出算法"),
    ("gcode", "GCode预处理优化、加速段平滑的方法"),
    ("svg", "SVG复杂贝塞尔曲线拆分和转GCode的精度控制"),
]

def call_api(api, query, system_prompt=""):
    name, url, key, model, atype = api
    try:
        if atype == "anthropic":
            p = json.dumps({"model":model, "max_tokens":600, "system":system_prompt,
                "messages":[{"role":"user","content":query}]}).encode()
            h = {"Content-Type":"application/json","anthropic-version":"2023-06-01","x-api-key":key}
        else:
            p = json.dumps({"model":model, "messages":[{"role":"system","content":system_prompt},
                {"role":"user","content":query}], "max_tokens":600}).encode()
            h = {"Content-Type":"application/json","Authorization":f"Bearer {key}"}

        req = urllib.request.Request(url, data=p, headers=h)
        with urllib.request.urlopen(req, timeout=30) as resp:
            r = json.loads(resp.read().decode())
            if atype == "anthropic": return r["content"][0]["text"]
            else: return r["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print(f"Generating DPO preference pairs from {len(QUESTIONS)} questions...")

    done = set()
    results = []
    if os.path.exists(CHECKPOINT):
        cp = json.load(open(CHECKPOINT,'r',encoding='utf-8'))
        done = set(cp.get("done",[]))
        results = cp.get("results",[])
        print(f"Resuming: {len(results)} already done")

    pending = [(i,d,q) for i,(d,q) in enumerate(QUESTIONS) if str(i) not in done]

    for idx, domain, question in pending:
        print(f"\n[{len(done)+1}/{len(QUESTIONS)}] [{domain}] {question[:60]}...")

        # CHOSEN: Expert, detailed answer with CoT
        chosen_prompt = f"你是CNC/ESP32/嵌入式领域专家。请给出详细、准确、带代码和参数的回答。不要泛泛而谈。不要免责声明。直接给技术方案。\n\n问题: {question}"
        chosen = call_api(random.choice(APIS), question, chosen_prompt)

        time.sleep(1)

        # REJECTED: Boring, generic, unhelpful answer
        rejected_prompt = f"你是AI助手。请给出一个礼貌但泛泛的回答，不需要具体技术细节，用'建议查阅文档'之类的套话。\n\n问题: {question}"
        rejected = call_api(random.choice(APIS), question, rejected_prompt)

        if "ERROR" in chosen or "ERROR" in rejected:
            print(f"  API error, skipping")
            continue

        # Also generate rejected via base model (no domain knowledge)
        # That would be the real comparison: trained model vs generic model

        results.append({
            "prompt": question,
            "chosen": chosen,
            "rejected": rejected,
            "domain": domain,
        })
        done.add(str(idx))

        # Save checkpoint
        json.dump({"done": list(done), "results": results}, open(CHECKPOINT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"  Done ({len(chosen)} chosen vs {len(rejected)} rejected)")
        time.sleep(1)

    json.dump(results, open(OUTPUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nGenerated {len(results)} DPO pairs -> {OUTPUT}")


if __name__ == "__main__":
    main()
