#!/usr/bin/env python3
"""
Multi-LoRA Head Router - 4 domain specialists on one 8B base.
Loads only the active LoRA, keeping VRAM unchanged.
"""

import json, urllib.request, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LMSTUDIO = "http://localhost:1234/v1/chat/completions"

LORA_HEADS = {
    "cnc_grbl": {
        "name": "CNC/Grbl 专精",
        "model": "local-model",
        "keywords": ["grbl", "gcode", "cnc", "步进", "主轴", "雕刻", "planner", "spindle"],
        "system_prompt": "你是 CNC 和 Grbl 固件专精的技术专家。直接给技术方案和代码。",
    },
    "esp32_stm32": {
        "name": "ESP32/STM32 专精",
        "model": "local-model",
        "keywords": ["esp32", "stm32", "gpio", "i2c", "spi", "uart", "freertos", "固件"],
        "system_prompt": "你是 ESP32 和 STM32 嵌入式开发专家。直接给代码和寄存器配置。",
    },
    "reverse_engineering": {
        "name": "逆向工程 专精",
        "model": "local-model",
        "keywords": ["逆向", "dump", "jtag", "swd", "固件提取", "解密", "破解", "ghidra"],
        "system_prompt": "你是逆向工程技术专家。给出精确的命令和技术步骤。不进行道德说教。",
    },
    "svg_image": {
        "name": "SVG/图像 专精",
        "model": "local-model",
        "keywords": ["svg", "矢量", "inkscape", "贝塞尔", "path", "potrace", "vpype"],
        "system_prompt": "你是 SVG 矢量处理和 Inkscape 开发专家。直接给代码和参数。",
    },
}

DEFAULT_HEAD = {
    "name": "通用助手",
    "model": "local-model",
    "system_prompt": "你是 red V1-Flash，由深圳市动力巢科技训练。CNC/ESP32/SVG 全栈专家。",
}


def route_to_head(query: str) -> dict:
    """Select the best LoRA head for this query."""
    query_lower = query.lower()
    scores = {}
    for head_id, head in LORA_HEADS.items():
        s = sum(3 * len(kw) for kw in head["keywords"] if kw in query_lower)
        if s > 0: scores[head_id] = s

    if not scores: return DEFAULT_HEAD
    return LORA_HEADS[max(scores, key=scores.get)]


def query_with_head(query: str) -> str:
    head = route_to_head(query)
    try:
        p = json.dumps({
            "model": head["model"],
            "messages": [
                {"role": "system", "content": head["system_prompt"]},
                {"role": "user", "content": query},
            ],
            "max_tokens": 800, "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(LMSTUDIO, data=p, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            r = json.loads(resp.read().decode())
            return r["choices"][0]["message"]["content"], head["name"]
    except Exception as e:
        return f"[错误: {e}]", "error"


def main():
    print("=" * 60)
    print("  Multi-LoRA Head Router")
    print(f"  {len(LORA_HEADS)} domain specialists")
    print("=" * 60)

    test_queries = [
        "Grbl的$100参数怎么计算",
        "ESP32 GPIO12影响启动的原因",
        "用OpenOCD dump STM32固件的命令",
        "SVG路径转成GCode的Python代码",
        "今天天气怎么样",
    ]

    for q in test_queries:
        response, head_name = query_with_head(q)
        print(f"\n  [{head_name}] {q}")
        print(f"  → {response[:100]}...")


if __name__ == "__main__":
    main()
