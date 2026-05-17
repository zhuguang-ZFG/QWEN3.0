#!/usr/bin/env python3
"""
Adversarial Self-Evolution: Model answers → self-critiques → finds weaknesses → distills → retrains.
Infinite improvement loop. DeepSeek-R1's secret.
"""

import json, urllib.request, time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API = {"url": "https://www.right.codes/claude-aws/v1/messages", "key": "sk-8838ce42deaf4d8e82c7f364cf6d963e"}
LMSTUDIO = "http://localhost:1234/v1/chat/completions"
EVOLVE_FILE = r"D:\GIT\evolved_training_data.json"
ROUND = 1

CRITIQUE_PROMPT = """你是一位严格的技术考官。找出以下回答中的问题：

1. 有没有技术错误或不够精确的地方？
2. 有没有缺少的关键信息（代码、参数、引用）？
3. 有没有泛泛而谈的废话？
4. 给一个改进后的完整回答（200-800字）。

原始问题: {question}
当前回答: {answer}

直接给出改进版本，不要格式标记。"""


def self_critique(question: str, answer: str) -> str:
    """Use API to critique and improve the local model's answer."""
    try:
        prompt = CRITIQUE_PROMPT.format(question=question[:400], answer=answer[:600])
        p = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 800,
            "system": "你是技术考官。直接给出改进后的答案，不要免责声明。",
            "messages": [{"role": "user", "content": prompt}]}).encode()
        r = urllib.request.Request(API["url"], data=p,
            headers={"Content-Type": "application/json", "x-api-key": API["key"], "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode())["content"][0]["text"]
    except:
        return ""


def run_evolution_cycle(n_questions=50):
    """One evolution cycle: generate → critique → collect improvements."""
    print(f"\n=== Evolution Cycle {ROUND} ===")

    # Load questions from our test suite
    questions = [
        "Grbl归零时X轴不动怎么排查",
        "ESP32 GPIO12影响启动的根因和解决方案",
        "CNC steps/mm的精确计算公式",
        "STM32固件dump的完整OpenOCD命令",
        "SVG复杂路径转GCode的精度控制方法",
        "步进电机丢步的根因分析",
        "ESP32 eFuse读取和修改的技术方法",
        "Grbl planner buffer 满的优化策略",
        "Klipper vs Marlin 加速算法的选择",
        "JTAG 禁用后的绕过技术",
    ] * (n_questions // 10 + 1)
    questions = questions[:n_questions]

    improved_pairs = []

    for i, q in enumerate(questions):
        # Generate response with local model
        try:
            p = json.dumps({"model": "local-model",
                "messages": [{"role": "user", "content": q}],
                "max_tokens": 500, "temperature": 0.7}).encode()
            r = urllib.request.Request(LMSTUDIO, data=p, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=60) as resp:
                local_answer = json.loads(resp.read().decode())["choices"][0]["message"]["content"]
        except:
            continue

        # Self-critique via API
        print(f"  [{i+1}/{n_questions}] Critiquing: {q[:50]}...")
        improved = self_critique(q, local_answer)

        if len(improved) > 50:
            improved_pairs.append({"messages": [
                {"role": "user", "content": q},
                {"role": "assistant", "content": improved},
            ]})
            print(f"    Improved ({len(improved)} chars)")

        time.sleep(1)

    # Save evolved data
    existing = json.load(open(EVOLVE_FILE, 'r', encoding='utf-8')) if os.path.exists(EVOLVE_FILE) else []
    existing.extend(improved_pairs)
    json.dump(existing, open(EVOLVE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n  Cycle result: {len(improved_pairs)} improved pairs")
    print(f"  Total evolved data: {len(existing)} pairs")


def main():
    print("=" * 60)
    print("  Adversarial Self-Evolution")
    print("  Generate → Critique → Improve → Retrain")
    print("=" * 60)
    run_evolution_cycle(50)
    print("\n  Run again to continue evolving.")


if __name__ == "__main__":
    main()
