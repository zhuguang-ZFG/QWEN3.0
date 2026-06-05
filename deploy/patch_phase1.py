"""Phase 1 patch: IDE detection + Skills injection + model-specific prompts
Adds to smart_router.py without breaking existing functionality.
"""
import re, json

PATCH_FILE = "/opt/lima-router/smart_router.py"

# === Skills definitions ===
SKILLS_BLOCK = '''
# ══════════════════════════════════════════════════════════════
# Phase 1: IDE 识别 + Skills 注入 + 模型专属 Prompt
# ══════════════════════════════════════════════════════════════

# IDE 指纹检测 — 与 router_v3._IDE_FINGERPRINTS 保持一致（仅 OpenCode）
_IDE_FINGERPRINTS = {
    "OpenCode": ["OpenCode", "opencode", "opencode-ai"],
}

# L0 通用编程 Skills (检测到编程场景时注入)
_CODING_SKILLS_L0 = """[编程规范]
- 不要编造不存在的API/库/函数，不确定时明确说明
- 写完整实现，不要TODO/FIXME/pass占位符
- 优先安全代码：参数化查询、输入验证、错误处理
- 函数单一职责，变量命名有语义"""

# L1 语言专用 Skills
_LANG_SKILLS = {
    "python": "\\n[Python] type hints, f-string, pathlib, 不用bare except, 用dataclass",
    "typescript": "\\n[TypeScript] strict mode, const优先, async/await, 不用any",
    "go": "\\n[Go] error wrapping, defer, context propagation, 不用panic",
    "rust": "\\n[Rust] Result<T,E>, 不用unwrap in production, 所有权明确",
    "java": "\\n[Java] Optional代替null, try-with-resources, 不用raw types",
}

# 模型专属 prompt 前缀
_MODEL_HINTS = {
    "llama": "\\n[指令] 请先分析需求再写代码，一步步思考。",
    "qwen": "",  # Qwen 对中文 prompt 天然友好，不需要额外提示
    "deepseek": "",  # DeepSeek 自带思考能力
    "mistral": "\\n[指令] Be concise. Output code directly.",
    "gemma": "\\n[指令] 请先分析再回答，确保代码完整可运行。",
}


def detect_ide_from_prompt(system_prompt: str) -> str:
    """从 system prompt 内容检测 IDE 来源"""
    if not system_prompt:
        return "unknown"
    sp = system_prompt[:2000]
    for ide, keywords in _IDE_FINGERPRINTS.items():
        for kw in keywords:
            if kw in sp:
                return ide
    # 长度启发式
    if len(system_prompt) > 5000:
        return "ide_long"  # 可能是某种 IDE
    return "unknown"


def detect_language(messages: list) -> str:
    """从消息内容检测编程语言"""
    if not messages:
        return ""
    text = " ".join(m.get("content", "")[:500] for m in messages[-3:] if isinstance(m.get("content"), str))
    # 文件扩展名检测
    ext_map = {
        r"\\.(py|pyw)": "python", r"\\.(ts|tsx)": "typescript",
        r"\\.(js|jsx)": "typescript", r"\\.(go)": "go",
        r"\\.(rs)": "rust", r"\\.(java)": "java",
    }
    for pattern, lang in ext_map.items():
        if re.search(pattern, text):
            return lang
    # 关键词检测
    kw_map = {
        "python": ["def ", "import ", "self.", "print(", "__init__"],
        "typescript": ["const ", "interface ", "=> {", "async ", "export "],
        "go": ["func ", "package ", "go func", "err != nil"],
        "rust": ["fn ", "let mut", "impl ", "pub fn", "unwrap()"],
        "java": ["public class", "System.out", "@Override", "void "],
    }
    for lang, keywords in kw_map.items():
        if sum(1 for kw in keywords if kw in text) >= 2:
            return lang
    return ""


def is_coding_request(messages: list, ide_source: str) -> bool:
    """判断是否为编程相关请求"""
    if ide_source not in ("unknown", ""):
        return True
    if not messages:
        return False
    last_msg = messages[-1].get("content", "") if messages else ""
    if isinstance(last_msg, list):
        last_msg = " ".join(b.get("text", "") for b in last_msg if b.get("type") == "text")
    code_signals = ["代码", "code", "function", "class", "import", "def ",
                    "bug", "error", "fix", "实现", "写一个", "```"]
    return any(s in last_msg for s in code_signals)


def get_model_family(backend_name: str) -> str:
    """从后端名称推断模型族"""
    name = backend_name.lower()
    if "llama" in name or "naga" in name:
        return "llama"
    if "qwen" in name or "aliyun" in name:
        return "qwen"
    if "deepseek" in name:
        return "deepseek"
    if "mistral" in name or "codestral" in name:
        return "mistral"
    if "gemma" in name:
        return "gemma"
    return ""
'''

def apply_patch():
    with open(PATCH_FILE, "r") as f:
        content = f.read()

    # Check if already patched
    if "_IDE_FINGERPRINTS" in content:
        print("Already patched")
        return

    # Find insertion point: after imports, before BACKENDS dict
    # Insert after the last import line
    marker = "BACKENDS = {"
    idx = content.find(marker)
    if idx < 0:
        print("ERROR: BACKENDS marker not found")
        return

    # Insert skills block before BACKENDS
    content = content[:idx] + SKILLS_BLOCK + "\n\n" + content[idx:]
    print("Inserted skills block")

    # Now patch _build_request_body to inject skills
    # Find where sys_prompt is constructed in the openai branch
    old_openai_sys = '''        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += f"\\n\\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
        body = {'model': b['model'], 'max_tokens': mt,
                'messages': [{'role': 'system', 'content': sys_prompt}] + msgs}'''

    new_openai_sys = '''        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += f"\\n\\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
        # Phase 1: Skills 注入
        _ide_detected = detect_ide_from_prompt(msgs[0].get("content","") if msgs and msgs[0].get("role")=="system" else "")
        if _ide_detected == "unknown" and ide not in ("unknown", "未知"):
            _ide_detected = ide
        _lang = detect_language(msgs)
        if is_coding_request(msgs, _ide_detected):
            sys_prompt += _CODING_SKILLS_L0
            if _lang in _LANG_SKILLS:
                sys_prompt += _LANG_SKILLS[_lang]
        _mf = get_model_family(name)
        if _mf in _MODEL_HINTS:
            sys_prompt += _MODEL_HINTS[_mf]
        body = {'model': b['model'], 'max_tokens': mt,
                'messages': [{'role': 'system', 'content': sys_prompt}] + msgs}'''

    if old_openai_sys in content:
        content = content.replace(old_openai_sys, new_openai_sys, 1)
        print("Patched _build_request_body (openai branch)")
    else:
        print("WARNING: Could not find openai sys_prompt pattern")

    with open(PATCH_FILE, "w") as f:
        f.write(content)
    print("Patch applied successfully")


if __name__ == "__main__":
    apply_patch()
