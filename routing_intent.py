"""Intent detection helpers (migrated from legacy router_intent/router_image)."""
from __future__ import annotations

import re
from typing import Any

_IMAGE_PATTERNS = [
    re.compile(r"画一[个只张幅副]", re.IGNORECASE),
    re.compile(r"画个", re.IGNORECASE),
    re.compile(r"生成.*图", re.IGNORECASE),
    re.compile(r"画.*图", re.IGNORECASE),
    re.compile(r"设计.*logo", re.IGNORECASE),
    re.compile(r"generate.*image", re.IGNORECASE),
    re.compile(r"\bdraw\b", re.IGNORECASE),
    re.compile(r"create.*picture", re.IGNORECASE),
    re.compile(r"画.*画", re.IGNORECASE),
    re.compile(r"帮我画", re.IGNORECASE),
    re.compile(r"给我画", re.IGNORECASE),
    re.compile(r"生成.*照片", re.IGNORECASE),
    re.compile(r"生成.*插画", re.IGNORECASE),
    re.compile(r"make.*image", re.IGNORECASE),
]

_IMAGE_STRIP_PATTERNS = [
    re.compile(r"^(请|帮我|给我|帮忙)?(画一[个只张幅副]|画个|画一下|画)"),
    re.compile(r"^(请|帮我|给我)?生成(一[张幅副])?(.*?)(图片?|图像|照片|插画)的?"),
    re.compile(r"^(请|帮我|给我)?设计(一个)?"),
    re.compile(r"^(请|帮我|给我)?(create|generate|make)\s+(a\s+)?(picture|image|photo)\s+of\s*"),
    re.compile(r"^(请|帮我|给我)?draw\s+"),
]

_THINKING_PATTERNS = [
    re.compile(r"仔细想想|深度分析|深入分析|深度思考|仔细分析|认真想|好好想|慢慢想", re.IGNORECASE),
    re.compile(r"逐步推理|一步一步|分步骤|详细推导|严格证明|严谨分析", re.IGNORECASE),
    re.compile(r"证明.*(?:定理|公式|等式|不等式|无理数|收敛|存在)", re.IGNORECASE),
    re.compile(r"数学证明|形式化证明|逻辑推导|归纳证明|反证法", re.IGNORECASE),
    re.compile(r"复杂度分析|时间复杂度|空间复杂度|算法.*证明", re.IGNORECASE),
    re.compile(r"系统架构.*设计|分布式.*设计|微服务.*拆分", re.IGNORECASE),
    re.compile(r"think carefully|think step by step|step by step|think harder", re.IGNORECASE),
    re.compile(r"prove that|formal proof|mathematical proof|rigorous proof", re.IGNORECASE),
    re.compile(r"deep analysis|in-depth analysis|thorough analysis", re.IGNORECASE),
    re.compile(r"multi.?step.*(?:reason|logic|problem)", re.IGNORECASE),
    re.compile(r"code architecture.*design|system design.*from scratch", re.IGNORECASE),
    re.compile(r"证明.*根号|证明.*√|prove.*sqrt|prove.*irrational", re.IGNORECASE),
    re.compile(r"求证|证明如下|请证明|帮我证明", re.IGNORECASE),
]


def detect_image_intent(query: str) -> tuple[bool, str]:
    """Return (is_image_request, pollinations_prompt)."""
    if not query:
        return (False, "")

    is_image = any(pattern.search(query) for pattern in _IMAGE_PATTERNS)
    if not is_image:
        return (False, "")

    prompt = query.strip()
    for strip_pat in _IMAGE_STRIP_PATTERNS:
        prompt = strip_pat.sub("", prompt).strip()

    if not prompt or len(prompt) < 2:
        prompt = query.strip()

    prompt = re.sub(r"[。！？.!?]+$", "", prompt).strip()

    if re.search(r"[一-鿿]", prompt):
        prompt = f"high quality, detailed, {prompt}"

    return (True, prompt)


def detect_thinking_intent(query: str) -> bool:
    """Detect requests that ask for step-by-step or deep reasoning."""
    if not query:
        return False
    return any(pattern.search(query) for pattern in _THINKING_PATTERNS)


# ── Legacy-compatible intent analyzer (ported from router_classifier.py) ──────

_ANALYZE_RULES = [
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
}

_SIGNAL_WEIGHTS = {
    "identity": 3.0,
    "tools": 2.0,
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
            "needs_code": best_intent is not None and "code" in best_intent,
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
        return {
            "intent": "thinking",
            "complexity": 0.9,
            "needs_code": False,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "thinking_detect",
            "confidence": 0.95,
        }

    result = _enhanced_classify(query, system_prompt, ide)
    if result:
        return result

    return {
        "intent": "unknown",
        "complexity": 0.5,
        "needs_code": False,
        "domain_keywords": [],
        "cnc_subdomain": "general",
        "source": "default_fallback",
        "confidence": 0.5,
    }
