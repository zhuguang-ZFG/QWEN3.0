"""Layer 1: request type and scenario classification (CQ-014 slice 11)."""

from __future__ import annotations

import router_v3


def classify(query: str, messages: list[dict], *,
             fmt: str = "openai", ide_source: str = "",
             system_prompt: str = "", headers: dict = None) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        return "ide"

    if ide_source and ide_source in router_v3.IDE_SOURCES:
        return "ide"

    ua = headers.get("user-agent", "")
    if router_v3.detect_ide_from_user_agent(ua):
        return "ide"

    if system_prompt and router_v3.detect_ide_from_system_prompt(system_prompt):
        return "ide"

    if _has_image_blocks(messages):
        return "vision"

    return "chat"


def classify_scenario(query: str, messages: list[dict], *,
                      ide_source: str = "", request_type: str = "") -> str:
    """判断场景: coding / chat。决定走质量路径还是速度路径。"""
    if request_type == "ide":
        return "coding"
    if ide_source and ide_source.lower() in router_v3.IDE_SOURCES:
        return "coding"

    last_content = ""
    if messages:
        last = messages[-1]
        last_content = last.get("content", "") if isinstance(last, dict) else ""
        if isinstance(last_content, list):
            last_content = " ".join(
                b.get("text", "") for b in last_content if isinstance(b, dict))

    text = last_content or query

    if "```" in text:
        return "coding"
    if any(kw in text for kw in ("Traceback", "Error:", "TypeError", "SyntaxError")):
        return "coding"

    code_signals = ("def ", "class ", "import ", "function ", "const ", "async ",
                    "return ", "if __name__", "from ", "export ")
    if sum(1 for s in code_signals if s in text) >= 2:
        return "coding"

    # Chinese coding signals
    cn_code_signals = ("写一个", "写个", "编写", "实现", "函数", "代码",
                       "编程", "开发", "重构", "修复", "调试", "测试",
                       "Python", "JavaScript", "Golang", "Rust", "Java")
    if sum(1 for s in cn_code_signals if s in text) >= 2:
        return "coding"

    # English coding intent signals
    en_code_signals = ("write a", "implement", "create a function",
                       "sort", "algorithm", "function", "code",
                       "fix bug", "refactor", "test case")
    if sum(1 for s in en_code_signals if s.lower() in text.lower()) >= 2:
        return "coding"

    import re
    if re.search(r'\w+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp)\b', text):
        return "coding"

    return "chat"


def classify_agent_task(query: str, messages: list[dict], *,
                       ide_source: str = "", system_prompt: str = "") -> bool:
    """Detect requests that benefit from Hermes Agent capabilities.

    Returns True when the request involves:
      - Multi-file operations (read/write/modify multiple files)
      - Shell command execution (git, npm, docker, etc.)
      - Browser automation tasks
      - Long multi-step reasoning/debugging loops
      - Project scaffolding / system-level operations
    """
    # Extract last user message text
    last_text = ""
    if messages:
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    last_text = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict))
                elif isinstance(content, str):
                    last_text = content
                break

    text = (query or last_text or "").lower()

    # ── Multi-file operation signals ──
    multi_file_signals = (
        "multiple files", "across the project", "entire codebase",
        "refactor the", "migrate from", "migrate to",
        "update all", "rename all", "every file",
    )
    if any(s in text for s in multi_file_signals):
        return True

    # ── Shell command signals ──
    shell_signals = (
        "git clone", "git init", "git add", "git commit", "git push",
        "npm install", "npm run", "npm init", "npm build",
        "pip install", "pip freeze", "pip uninstall",
        "docker build", "docker run", "docker compose", "docker-compose",
        "ssh ", "scp ", "rsync ", "curl ", "wget ",
        "systemctl", "sudo ", "chmod ", "chown ",
        "cargo build", "cargo run", "go build", "go install",
        "make ", "cmake ", "./configure",
        "deploy to", "deploy the", "restart the service",
    )
    if any(s in text for s in shell_signals):
        return True

    # ── Browser automation signals ──
    browser_signals = (
        "scrape", "crawl", "browser automation",
        "open browser", "take screenshot", "web scraping",
        "fill form", "click button", "navigate to http",
        "playwright", "selenium", "puppeteer",
    )
    if any(s in text for s in browser_signals):
        return True

    # ── Multi-step task signals ──
    multistep_signals = (
        "step by step", "first ", "then ", "finally ",
        "create a project", "set up a project", "scaffold",
        "build a", "build an app", "create an app",
        "full stack", "full-stack", "end to end",
        "database migration", "schema migration",
        "debug this", "fix all", "refactor the entire",
        "from scratch", "boilerplate",
    )
    if any(s in text for s in multistep_signals):
        return True

    # ── Explicit agent-tool signal in system prompt ──
    if system_prompt:
        agent_sp_signals = ("agent mode", "autonomous", "use tools",
                           "execute commands", "terminal access")
        if any(s in system_prompt.lower() for s in agent_sp_signals):
            return True

    return False


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False


def classify_difficulty(query: str, messages: list[dict], *,
                        scenario: str = "") -> int:
    """Estimate coding task difficulty for tiered model selection.

    Returns 0-100 score. Call after classify_scenario() for coding tasks.
    Non-coding scenarios return 0 (no tier preference).
    """
    if scenario != "coding":
        return 0
    from routing_difficulty import estimate_difficulty
    return estimate_difficulty(query, messages, scenario=scenario)
