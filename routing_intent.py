"""Intent detection helpers (migrated from legacy router_intent/router_image)."""

from __future__ import annotations

import re
from typing import Any

from models.structured_outputs import IntentResult
from models.structured_outputs.validator import validate_value
from routing_intent_modal import detect_image_intent, detect_thinking_intent

__all__ = [
    "detect_image_intent",
    "detect_thinking_intent",
    "analyze_intent",
    "intent_to_prompt_scenario",
]

# Map granular device intents to prompt_engineering scenario keys.
_DEVICE_PROMPT_SCENARIOS = {
    "device_draw": "device_draw",
    "device_write": "device_write",
    "device_home": "device_control",
    "device_stop": "device_control",
    "device_status": "device_control",
    "device_task_query": "device_control",
    "device_control": "device_control",
}


def intent_to_prompt_scenario(intent: str) -> str | None:
    """Map analyze_intent output to prompt_engineering/layers scenario."""
    return _DEVICE_PROMPT_SCENARIOS.get(intent)


# ── Legacy-compatible intent analyzer (ported from router_classifier.py) ──────

_DEVICE_RULES = [
    (r"回家|home|回原点|归位", "device_home", 0.95),
    (r"停止|stop|急停|emergency", "device_stop", 0.95),
    (r"笔绘|plotter|笔绘机.*画|让机器画", "device_draw", 0.93),
    (r"写一行|写个|写字|书写|write\s", "device_write", 0.92),
    (r"查.*任务|task.*status|任务.*进度", "device_task_query", 0.90),
    (r"设备.*状态|device.*status|在线.*吗", "device_status", 0.90),
]

_ANALYZE_RULES = _DEVICE_RULES + [
    (r"你是什么|什么模型|who are you|what model|你好|hello|hi$|hey$", "trivial", 0.95),
    (r"^.{1,5}$", "trivial", 0.90),
    (r"\$\d+|步数.*mm|steps.*mm|steps_per_mm", "grbl_config", 0.95),
    (r"归零|homing|\$22|\$23|\$24|\$25|\$26|\$27", "grbl_config", 0.95),
    (r"G0|G1|G2|G3|G28|G38|G54|G92|M3|M5|M8|圆弧|插补|进给", "gcode_help", 0.90),
    (r"error:\d+|alarm:\d+|ALARM|报警|错误码", "grbl_config", 0.90),
    (r"失步|抖动|噪音|异响|卡顿|不动|乱走|偏移", "cnc_trouble", 0.85),
    (r"限位|limit switch|触发|短路|接线", "cnc_trouble", 0.85),
    (r"ESP32|WiFi|蓝牙|WebUI|OTA|FreeRTOS|RTOS", "embedded_dev", 0.85),
    (r"STM32|HAL|CubeMX|定时器|中断|DMA|寄存器", "embedded_dev", 0.85),
    (r"写.*代码|生成.*代码|实现.*函数|代码示例", "code_generation", 0.85),
    (r"架构|设计|方案|选型|对比|哪个好", "architecture", 0.80),
    (r"写.*SQL|生成.*SQL|查询.*语句|SELECT|INSERT|UPDATE|DELETE.*FROM", "tool_task", 0.90),
    (r"正则|regex|匹配.*模式|pattern", "tool_task", 0.85),
    (r"修复.*代码|fix.*code|debug.*this|帮我改.*bug", "tool_task", 0.80),
    (r"JSON.*Schema|生成.*schema|转换.*JSON", "tool_task", 0.85),
    (r"翻译.*代码|convert.*to.*python|改写.*成", "tool_task", 0.80),
    (r"画一[个张只幅]|画.*图|生成.*图片|draw|generate.*image|create.*image|画.*picture", "image_gen", 0.92),
    (r"图片.*生成|AI.*画|AI.*绘|文生图|text.to.image|帮我画|给我画", "image_gen", 0.90),
    (r"FOC|PID|闭环|编码器|伺服|变频器|VFD", "complex_theory", 0.85),
    (r"PCB|雕刻|激光|切割|主轴|转速|RPM", "general_cnc", 0.80),
]

_SIGNALS: dict[str, dict[str, list[str]]] = {
    "code_generation": {
        "identity": ["写代码", "实现", "开发", "编写", "create", "implement", "write a"],
        "tools": ["python", "javascript", "typescript", "react", "vue", "rust", "go"],
        "complexity": ["算法", "架构", "设计模式", "重构", "优化"],
    },
    "debugging": {
        "identity": ["报错", "bug", "修复", "error", "fix", "crash", "失败"],
        "tools": ["traceback", "stack trace", "exception", "TypeError", "undefined"],
        "context": ["为什么", "不工作", "怎么解决"],
    },
    "explanation": {
        "identity": ["解释", "什么是", "怎么理解", "原理", "区别", "对比"],
        "context": ["为什么要", "有什么用", "怎么选"],
    },
    "hardware": {
        "identity": ["esp32", "stm32", "arduino", "grbl", "gpio", "固件"],
        "tools": ["串口", "i2c", "spi", "pwm", "adc", "uart"],
        "config": ["\\$\\d+", "参数", "配置", "烧录"],
    },
    "trivial": {
        "identity": ["你好", "hello", "hi", "谢谢", "再见", "在吗"],
    },
    "device_draw": {
        "identity": ["画", "draw", "plotter", "笔绘", "绘个", "生成图片"],
        "tools": ["简笔画", "线条", "黑白", "g-code"],
        "action": ["画一只", "画一个", "画张", "plot"],
    },
    "device_write": {
        "identity": ["写", "write", "写字", "书写", "写一行"],
        "tools": ["字体", "笔画", "汉字", "calligraphy"],
        "action": ["写个", "写一句", "写首诗"],
    },
    "device_control": {
        "identity": ["回家", "回原点", "停止", "急停", "home", "stop", "emergency"],
        "tools": ["g28", "m5", "归位"],
        "action": ["回", "停", "急停"],
    },
}

_SIGNAL_WEIGHTS = {
    "identity": 3.0,
    "tools": 2.0,
    "action": 2.0,
    "complexity": 1.5,
    "context": 1.5,
    "config": 1.0,
}

_CODE_BLOCK_RE = re.compile(
    r"```|^\s{4,}\S|def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import",
    re.MULTILINE,
)
_ENGLISH_TECH_RE = re.compile(
    r"\b(function|variable|array|object|string|integer|boolean|async|await|promise|callback|interface|generic|type|enum)\b",
    re.IGNORECASE,
)


def _signal_classify(query: str) -> dict[str, Any] | None:
    q = query[:800].lower()
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for intent, dimensions in _SIGNALS.items():
        score = 0.0
        hits: list[str] = []
        for dim, keywords in dimensions.items():
            weight = _SIGNAL_WEIGHTS.get(dim, 1.0)
            for kw in keywords:
                if re.search(kw, q, re.IGNORECASE):
                    score += weight
                    hits.append(f"{dim}:{kw}")
        if score > 0:
            scores[intent] = score
            evidence[intent] = hits

    if not scores:
        return None

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    if best_score >= 8.0:
        confidence = 0.95
    elif best_score >= 5.0:
        confidence = 0.90
    elif best_score >= 3.0:
        confidence = 0.75
    else:
        return None

    return {
        "intent": best_intent,
        "complexity": 0.7 if best_intent == "code_generation" else 0.3,
        "needs_code": best_intent in ("code_generation", "debugging"),
        "domain_keywords": evidence.get(best_intent, []),
        "cnc_subdomain": "grbl" if "grbl" in q else "general",
        "source": "signal_v2",
        "confidence": confidence,
    }


def _rule_classify(query: str) -> dict[str, Any] | None:
    best_intent, best_conf = None, 0.0
    for pattern, intent, conf in _ANALYZE_RULES:
        if re.search(pattern, query, re.IGNORECASE):
            if conf > best_conf:
                best_intent, best_conf = intent, conf
    if best_conf >= 0.80:
        return {
            "intent": best_intent,
            "complexity": 0.5,
            "needs_code": best_intent in ("code_generation", "debugging"),
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "rules",
            "confidence": best_conf,
        }
    return None


def _context_signals(query: str, system_prompt: str = "", ide: str = "unknown") -> dict[str, Any] | None:
    q = query[:800]

    if _CODE_BLOCK_RE.search(q):
        return {
            "intent": "code_generation",
            "complexity": 0.7,
            "needs_code": True,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "code_detect",
            "confidence": 0.85,
        }

    if ide.lower() in ("cursor", "vscode", "vs code", "jetbrains", "idea"):
        tech_density = len(_ENGLISH_TECH_RE.findall(q))
        if tech_density >= 2:
            return {
                "intent": "code_generation",
                "complexity": 0.6,
                "needs_code": True,
                "domain_keywords": [],
                "cnc_subdomain": "general",
                "source": "ide_context",
                "confidence": 0.80,
            }

    if len(q) > 300 and not any(re.search(p, q, re.IGNORECASE) for p, _, _ in _ANALYZE_RULES[:5]):
        return {
            "intent": "architecture",
            "complexity": 0.7,
            "needs_code": False,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "length_complexity",
            "confidence": 0.72,
        }

    return None


def _enhanced_classify(query: str, system_prompt: str = "", ide: str = "unknown") -> dict[str, Any] | None:
    rule_result = _rule_classify(query)
    if rule_result and rule_result.get("confidence", 0) >= 0.80:
        return rule_result

    signal_result = _signal_classify(query)
    if signal_result and signal_result.get("confidence", 0) >= 0.70:
        return signal_result

    ctx_result = _context_signals(query, system_prompt, ide)
    if ctx_result:
        return ctx_result

    if len(query.strip()) <= 10:
        return {
            "intent": "trivial",
            "complexity": 0.1,
            "needs_code": False,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "length_heuristic",
            "confidence": 0.85,
        }

    return None


def analyze_intent(
    query: str,
    system_prompt: str = "",
    ide: str = "unknown",
) -> dict[str, Any]:
    """Backward-compatible intent analysis (replaces router_classifier.analyze).

    Returns a dict with keys: intent, complexity, needs_code, domain_keywords,
    cnc_subdomain, source, confidence.
    """
    if detect_thinking_intent(query):
        result = {
            "intent": "thinking",
            "complexity": 0.9,
            "needs_code": False,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "thinking_detect",
            "confidence": 0.95,
        }
    else:
        result = _enhanced_classify(query, system_prompt, ide)
        if result is None:
            result = {
                "intent": "chat",
                "complexity": 0.5,
                "needs_code": False,
                "domain_keywords": [],
                "cnc_subdomain": "general",
                "source": "default_fallback",
                "confidence": 0.5,
            }

    validated = validate_value(result, IntentResult)
    return validated.model_dump()
