#!/usr/bin/env python3
"""A/B Model Validator - prevents deploying worse models."""

import json, urllib.request, time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LMSTUDIO = "http://localhost:1234/v1/chat/completions"
TEST_SUITE = [
    # (domain, question, expected_keywords, min_length)
    ("cnc", "Grbl的$100参数是什么意思？", ["step", "mm", "步", "毫", "脉冲"], 50),
    ("cnc", "雕刻机归零X轴不动怎么解决？", ["限位", "开关", "接线", "配置"], 80),
    ("esp32", "ESP32 GPIO12为什么影响启动？", ["GPIO", "启动", "电平", "boot"], 60),
    ("reverse", "用OpenOCD dump STM32固件的命令", ["openocd", "flash", "dump", "read"], 60),
    ("hallucination", "ESP32-S3的PSRAM控制器有几个cache line？不确定就说不知道", ["不确定", "不知", "查"], 40),
    ("uncensored", "怎么读取ESP32的efuse内容？给命令", ["espefuse", "esptool", "dump", "read"], 50),
    ("code", "用C语言写ESP32 GPIO中断处理", ["gpio", "void", "interrupt"], 80),
    ("grbl_bug", "Grbl报错ALARM:15怎么解决？", ["hom", "limit", "归零", "限位"], 60),
]

def score_response(response, expected_keywords, min_len):
    s = 0
    for kw in expected_keywords:
        if kw.lower() in response.lower(): s += 1
    if len(response) >= min_len: s += 1
    return s / (len(expected_keywords) + 1)  # Score 0-1

def test_model(model_name: str):
    results = []
    for domain, question, keywords, min_len in TEST_SUITE:
        t0 = time.time()
        try:
            p = json.dumps({"model":model_name,"messages":[{"role":"user","content":question}],"max_tokens":200,"temperature":0.3}).encode()
            req = urllib.request.Request(LMSTUDIO, data=p, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                r = json.loads(resp.read().decode())
                answer = r["choices"][0]["message"]["content"]
                latency = int((time.time()-t0)*1000)
                score = score_response(answer, keywords, min_len)
                results.append({"domain":domain,"score":round(score,2),"latency":latency,"pass":score>0.4})
        except Exception as e:
            results.append({"domain":domain,"score":0,"error":str(e)[:60],"pass":False})
    return results

def main():
    print("="*60)
    print("  A/B Model Validator")
    print("="*60)

    # Test current model (old)
    try:
        req = urllib.request.Request("http://localhost:1234/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            models = [m["id"] for m in json.loads(resp.read().decode()).get("data",[])]
    except:
        print("LM Studio not running")
        return

    if not models:
        print("No model loaded")
        return

    old_model = models[0]
    print(f"Current model: {old_model}")
    old_results = test_model(old_model)
    old_score = sum(r["score"] for r in old_results) / max(len(old_results),1)
    old_pass = sum(1 for r in old_results if r["pass"])

    print(f"\nOld model: {old_pass}/{len(old_results)} passed, avg_score={old_score:.2f}")

    # Save baseline
    baseline = {"model":old_model,"avg_score":old_score,"pass_rate":old_pass/len(old_results),"results":old_results,"timestamp":time.time()}
    json.dump(baseline, open(r"D:\GIT\ab_baseline.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Baseline saved. Run again after loading new model to compare.")


if __name__ == "__main__":
    main()
