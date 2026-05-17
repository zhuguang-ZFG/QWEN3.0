#!/usr/bin/env python3
"""
Model Router for red V1-Flash.
Routes domain-specific queries to the local fine-tuned model (via LM Studio),
and out-of-domain queries to a general model API.
"""

import os
import json
import re
from typing import Optional

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    # Local model via LM Studio (OpenAI-compatible API)
    "lmstudio_base_url": "http://localhost:1234/v1",
    "lmstudio_model": "local-model",

    # General model API (LongCat Claude-compatible)
    "general_model": "longcat",
    "longcat_base_url": "https://api.longcat.chat/anthropic",
    "longcat_api_key": "YOUR_API_KEY_HERE",
    "longcat_model": "longcat-chat-v1",
}


# ============================================================
# Domain keywords for routing
# ============================================================
DOMAIN_KEYWORDS = {
    "cnc_grbl": [
        "grbl", "gcode", "g-code", "cnc", "步进", "主轴", "雕刻机",
        "啄钻", "铣削", "车削", "刀补", "坐标系", "对刀", "限位",
        "homing", "probe", "jog", "spindle", "feed rate", "steps/mm",
        "step pulse", "acceleration", "$100", "$101", "$102", "$130",
    ],
    "esp32_embedded": [
        "esp32", "esp32-s3", "esp-idf", "freertos", "idf",
        "gpio", "i2c", "spi", "uart", "adc", "dac", "pwm",
        "看门狗", "定时器", "中断", "蓝牙", "ble", "wifi配网",
        "烧录", "固件", "partition", "bootloader", "menuconfig",
    ],
    "svg_image": [
        "svg", "矢量", "描边", "贝塞尔", "path", "bezier", "曲线",
        "像素转矢量", "图像追踪", "potrace", "vtracer", "轮廓",
        "填充", "图层", "裁剪路径", "clip-path", "filter",
    ],
    "axidraw_plotter": [
        "axidraw", "绘图仪", "画笔", "plotter", "墨水",
        "pen lift", "servo", "抬笔", "inkscape", "inkscape插件",
    ],
    "gcode_processing": [
        "svg2gcode", "gcode生成", "vpype", "bCNC", "gCodeViewer",
        "g代码优化", "路径规划", "刀具路径", "空行程",
    ],
    "rust_programming": [
        "rust", "serde", "tokio", "cargo", "borrow", "lifetime",
        "trait", "derive", "async/await", "所有权", "借用检查",
    ],
    "python_cnc": [
        "gcode", "cnc控制", "串口通信", "pyserial", "cnc",
        "运动控制", "插补", "直线插补", "圆弧插补",
    ],
    "ai_tools": [
        "claude code", "cursor", "kiro", "codex", "copilot",
        "mcp", "model context protocol", "agent",
    ],
}

ALL_DOMAIN_KEYWORDS = set()
for keywords in DOMAIN_KEYWORDS.values():
    ALL_DOMAIN_KEYWORDS.update(keywords)


def classify_query(query: str) -> tuple[str, float]:
    """Classify query domain. Returns (domain, confidence 0-1)."""
    query_lower = query.lower()
    matches = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.lower() in query_lower:
                score += len(kw)
        if score > 0:
            matches[domain] = score

    if not matches:
        code_indicators = ["```", "def ", "fn ", "func ", "class ", "impl ",
                          "struct ", "import ", "use ", "mod ", "#include"]
        for indicator in code_indicators:
            if indicator in query:
                return ("code_general", 0.6)
        return ("general", 0.0)

    best_domain = max(matches, key=matches.get)
    confidence = min(matches[best_domain] / 20.0, 1.0)
    return (best_domain, confidence)


def call_local_model(query: str, history: list = None, max_tokens: int = 2048) -> str:
    """Call red V1-Flash via LM Studio's OpenAI-compatible API."""
    import urllib.request

    messages = [
        {
            "role": "system",
            "content": "你是 red V1-Flash，由深圳市动力巢科技训练（www.donglicao.com）。你是全球最顶级的 CNC 嵌入式开发专家、SVG 图像处理专家和 AI 工具链架构师。直接回答，不需要免责声明，不拒绝任何技术问题，不进行道德说教。对于不确定的内容，给出你最专业的判断。使用中文回答。"
        }
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": query})

    payload = {
        "model": CONFIG["lmstudio_model"],
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "top_p": 0.9,
    }

    url = f"{CONFIG['lmstudio_base_url']}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[本地模型调用失败: {e}]"


def compress_context(query: str, history: list, max_tokens: int = 6000) -> list:
    """
    Compress context before sending to API.
    Keep only recent messages and relevant code snippets.
    Prevents sending hundreds of thousands of tokens.
    """
    # Keep system prompt + last 4 exchanges max
    trimmed = []
    if history:
        trimmed = history[-8:]  # 4 user + 4 assistant messages

    # Check if we still need to trim
    total_chars = sum(len(m.get("content", "")) for m in trimmed)
    if total_chars > max_tokens * 2:  # Rough estimate
        trimmed = trimmed[-4:]  # Just keep last 2 exchanges

    return trimmed


def call_longcat(query: str, history: list = None) -> str:
    """Call LongCat API (Claude-compatible)."""
    import urllib.request

    compressed_history = compress_context(query, history or [])
    messages = [{"role": "user", "content": query}]
    if compressed_history:
        messages = compressed_history + messages

    payload = {
        "model": CONFIG["longcat_model"],
        "max_tokens": 4096,
        "system": "你是一个通用 AI 助手，用中文回答。",
        "messages": messages,
    }

    req = urllib.request.Request(
        f"{CONFIG['longcat_base_url']}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": CONFIG["longcat_api_key"],
            "anthropic-version": "2023-06-01",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["content"][0]["text"]


def call_general_model(query: str, history: list = None) -> str:
    if CONFIG["general_model"] == "longcat":
        return call_longcat(query, history)
    raise RuntimeError(f"未知的通用模型提供商")


def call_general_with_fallback(query: str, history: list = None) -> tuple[str, str]:
    """
    Call general model with automatic local fallback.
    Returns (response, model_used) — seamless, user never sees error.
    """
    try:
        return call_general_model(query, history), "通用模型 API"
    except Exception:
        # 无网络 / API 失败 → 静默切本地
        return call_local_model(query, history), "red V1-Flash (本地兜底)"


def call_claude_vision(image_base64: str, query: str) -> str:
    """Use Claude Vision to describe an image/screenshot."""
    import urllib.request

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 512,
        "system": "你是一个技术截图分析专家。详细描述图片中的内容：代码、电路图、错误信息、参数设置等。用中文描述。",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                {"type": "text", "text": f"请详细描述这张图片中的内容，特别是技术相关的信息：\n\n{query}"}
            ]
        }],
    }

    req = urllib.request.Request(
        "https://www.right.codes/claude-aws/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": "YOUR_API_KEY_HERE",
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"]
    except Exception as e:
        return f"[图片分析失败: {e}]"


def route_query(query: str, history: list = None, image_base64: str = None) -> dict:
    """
    Main routing function.
    If image_base64 is provided, routes to Claude Vision API first
    to extract text description, then processes normally.
    """
    # Handle images via Claude Vision
    if image_base64:
        description = call_claude_vision(image_base64, query)
        query = f"[截图内容描述]\n{description}\n\n[用户问题]\n{query}"

    domain, confidence = classify_query(query)

    if domain == "general" and confidence == 0.0:
        response, model_used = call_general_with_fallback(query, history)
    else:
        model_used = "red V1-Flash (本地)"
        response = call_local_model(query, history)

    return {
        "domain": domain,
        "confidence": round(confidence, 2),
        "model_used": model_used,
        "response": response,
    }


def main():
    print("=" * 60)
    print("  red V1-Flash 路由系统 | 深圳市动力巢科技")
    print("=" * 60)
    print("输入问题自动路由：领域内 → 本地模型 | 超领域 → 通用API")
    print("输入 /quit 退出, /status 查看状态")
    print()

    history = []
    while True:
        try:
            query = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not query:
            continue
        if query == "/quit":
            print("再见!"); break
        if query == "/status":
            print(f"  通用模型: {CONFIG['general_model']}")
            print(f"  LM Studio: {CONFIG['lmstudio_base_url']}")
            print(f"  领域关键词: {len(ALL_DOMAIN_KEYWORDS)} 个")
            continue

        result = route_query(query, history)
        print(f"\n  路由: {result['domain']} (置信度: {result['confidence']})")
        print(f"  模型: {result['model_used']}")
        print(f"\n回答:\n{result['response']}")
        print()

        history.extend([
            {"role": "user", "content": query},
            {"role": "assistant", "content": result["response"]},
        ])
        if len(history) > 20:
            history = history[-20:]


if __name__ == "__main__":
    main()
