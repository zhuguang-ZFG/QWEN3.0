"""Request-local context preflight for LiMa coding routes.

The VPS cannot inspect a user's local IDE workspace directly. This module only
summarizes context already present in the request so backends get a compact,
truthful orientation block.
"""

from __future__ import annotations

import re


PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s`'\"<>|]+|/(?:[\w .-]+/)+[\w .-]+\.\w+|[\w.-]+(?:/[\w.-]+)+\.\w+)"
)
ERROR_RE = re.compile(
    r"(Traceback|SyntaxError|TypeError|ValueError|ImportError|ModuleNotFoundError|"
    r"AssertionError|FAILED [^\n]+|error[:\s][^\n]+|Exception[:\s][^\n]+)",
    re.IGNORECASE,
)
PYTHON_RE = re.compile(r"\b(def |import |pytest|Traceback|\.py\b|SyntaxError|TypeError)\b", re.I)
JS_RE = re.compile(r"\b(function |const |let |npm |tsx?\b|jsx?\b|TypeScript|JavaScript)\b", re.I)
RUST_RE = re.compile(r"\b(fn |cargo |\.rs\b|borrow checker|rustc)\b", re.I)
GO_RE = re.compile(r"\b(func |go test|go.mod|\.go\b)\b", re.I)


def build_context_digest(
    query: str,
    messages: list[dict],
    *,
    system_prompt: str = "",
    ide_source: str = "",
    max_chars: int = 1600,
) -> str:
    """Build a compact digest from request-local coding context."""
    text = "\n".join([system_prompt or "", query or ""] + [_message_text(m) for m in messages])
    paths = _unique(PATH_RE.findall(text), limit=8)
    signals = _extract_signals(messages, text, limit=6)
    language = _detect_language(text)
    task = _detect_task(query or _last_user_text(messages))
    workspace = _extract_workspace_hint(system_prompt or text)
    ide = ide_source or _detect_ide(text)

    if not any([paths, signals, workspace, ide]) and language == "general":
        return ""

    lines = ["LiMa context preflight:"]
    if ide:
        lines.append(f"- IDE: {ide}")
    if workspace:
        lines.append(f"- Workspace hint: {workspace}")
    if task:
        lines.append(f"- Task shape: {task}")
    if language != "general":
        lines.append(f"- Language: {language}")
    if paths:
        lines.append("- Files mentioned: " + ", ".join(paths))
    if signals:
        lines.append("- Tool/error signals: " + " | ".join(signals))
    lines.append(
        "- Boundary: VPS cannot read the user's local workspace directly; rely on client tool results and explicit file context."
    )

    return _truncate("\n".join(lines), max_chars)


def _message_text(message: dict) -> str:
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block.get("type") == "tool_result":
                parts.append(str(block.get("content", "")))
        return "\n".join(parts)
    return str(content)


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return _message_text(message)
    return ""


def _extract_signals(messages: list[dict], text: str, *, limit: int) -> list[str]:
    found: list[str] = []
    for message in messages:
        role = message.get("role") if isinstance(message, dict) else ""
        body = _message_text(message)
        if role == "tool" and body.strip():
            found.append(_clean_line(body))
        for match in ERROR_RE.findall(body):
            found.append(_clean_line(match if isinstance(match, str) else match[0]))
    for match in ERROR_RE.findall(text):
        found.append(_clean_line(match if isinstance(match, str) else match[0]))
    return _unique([s for s in found if s], limit=limit)


def _detect_language(text: str) -> str:
    scores = {
        "python": len(PYTHON_RE.findall(text)),
        "javascript": len(JS_RE.findall(text)),
        "rust": len(RUST_RE.findall(text)),
        "go": len(GO_RE.findall(text)),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def _detect_task(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in ("traceback", "error", "bug", "fix", "failed")):
        return "debug/fix"
    if any(k in lowered for k in ("refactor", "restructure", "clean up")):
        return "refactor"
    if any(k in lowered for k in ("test", "pytest", "coverage")):
        return "test"
    if any(k in lowered for k in ("explain", "analyze", "review")):
        return "analysis/review"
    return ""


def _detect_ide(text: str) -> str:
    lowered = text.lower()
    if "claude code" in lowered or "claude-code" in lowered:
        return "Claude Code"
    if "cursor" in lowered:
        return "Cursor"
    if "continue" in lowered:
        return "Continue"
    if "vscode" in lowered or "vs code" in lowered:
        return "VS Code"
    return ""


def _extract_workspace_hint(text: str) -> str:
    patterns = (
        r"(?:Working directory|Workspace Path|cwd|Current directory)[:=]\s*([^\n\r]+)",
        r"(?:工作目录|项目目录)[:=]\s*([^\n\r]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _clean_line(match.group(1))[:160]
    return ""


def _clean_line(text: str) -> str:
    return " ".join(str(text).strip().split())[:180]


def _unique(items: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _clean_line(item)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return text[: max_chars - 3].rstrip() + "..."
