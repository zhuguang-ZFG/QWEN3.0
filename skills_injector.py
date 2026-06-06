"""
LiMa Skills Injector — 智能补缺注入
基于 OpenCode 逆向分析设计。

双模式:
- 强模型(可 tool call): 列目录，让模型自己拉取 (OpenCode 模式)
- 弱模型(无 tool call): 检测缺失，预注入最少 skills

核心原则: 逐条检测 → 只补缺的 → 最多5条 → 不超200 token
"""

import glob as glob_mod
import logging
import os

from backends import STRONG_MODELS
from opencode_config import OPENCODE_SKIPPED_SKILL_CATEGORIES

_log = logging.getLogger(__name__)

# ─── 常量 ─────────────────────────────────────────────────────────────────────

MAX_SKILLS = 5
TOKEN_BUDGET = 200
CHARS_PER_TOKEN = 4

IDE_COVERAGE = {
    # IDE → set of categories already well-covered by built-in system prompt
    "OpenCode": {"style"},  # 已内置安全和语言指导，跳过style类别
}


# ─── YAML frontmatter 解析 (零依赖) ───────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 --- ... --- frontmatter，返回 (meta, body)"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            elif val.lower() in ("true", "false"):
                meta[key] = val.lower() == "true"
            elif val.isdigit():
                meta[key] = int(val)
            else:
                meta[key] = val.strip("\"'")
    return meta, text[end + 3:].strip()


# ─── Skills 加载 ──────────────────────────────────────────────────────────────

def load_skills_from_dir(skills_dir: str) -> list[dict]:
    """从 skills/ 目录加载所有 .md 文件，解析 frontmatter + body"""
    skills = []
    pattern = os.path.join(skills_dir, "**", "*.md")
    for fpath in glob_mod.glob(pattern, recursive=True):
        try:
            with open(fpath, encoding="utf-8") as f:
                raw = f.read()
            meta, body = _parse_frontmatter(raw)
            if not meta or "id" not in meta:
                continue
            skills.append({
                "id": meta["id"],
                "category": meta.get("category", "general"),
                "content": body,
                "detect_keywords": meta.get("detect_keywords", []),
                "always_apply": meta.get("always_apply", False),
                "priority": meta.get("priority", 5),
                "globs": meta.get("globs", []),
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "skills_injector: failed to load %s: %s", fpath, type(exc).__name__)
            continue
    return skills


# ─── 检测缺失 ─────────────────────────────────────────────────────────────────

def detect_missing_skills(system_prompt: str, skills: list[dict]) -> list[dict]:
    """逐条检测 system prompt 中缺失的 skills，按 priority 排序返回"""
    prompt_lower = (system_prompt or "").lower()
    missing = []
    for skill in skills:
        if not _covered(skill, prompt_lower):
            missing.append(skill)
    missing.sort(key=lambda s: s.get("priority", 5))
    return missing


def _covered(skill: dict, prompt_lower: str) -> bool:
    """检查 skill 是否已被 system prompt 覆盖"""
    keywords = skill.get("detect_keywords", [])
    if not keywords:
        return False
    for kw in keywords:
        if kw.lower() in prompt_lower:
            return True
    return False


# ─── 注入 Skills ──────────────────────────────────────────────────────────────

def inject_skills(messages: list[dict], missing_skills: list[dict]) -> list[dict]:
    """在 messages 中插入补缺 skills（不修改用户原有内容）"""
    if not missing_skills:
        return list(messages)

    limited = missing_skills[:MAX_SKILLS]
    skills_text = "\n".join(s["content"] for s in limited)
    skills_text = _trim_to_budget(skills_text, TOKEN_BUDGET)

    skills_msg = {"role": "system", "content": skills_text}

    if not messages:
        return [skills_msg]

    result = list(messages)
    if result and result[0].get("role") == "system":
        result.insert(1, skills_msg)
    else:
        result.insert(0, skills_msg)
    return result


def _trim_to_budget(text: str, max_tokens: int) -> str:
    """按 token 预算截断文本"""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


# ─── 双模式入口 ───────────────────────────────────────────────────────────────

def apply_skills(backend: str, messages: list[dict],
                 system_prompt: str = "", ide_source: str = "",
                 skills_dir: str = "") -> list[dict]:
    """
    根据后端能力选择策略:
    - 强模型 → 目录模式 (只列 skill 名)
    - 弱模型 → 补缺模式 (检测缺失，预注入)
    """
    if skills_dir:
        all_skills = load_skills_from_dir(skills_dir)
    else:
        all_skills = load_skills_from_dir(
            os.path.join(os.path.dirname(__file__), "skills"))

    if not all_skills:
        return list(messages)

    result: list[dict]
    if backend in STRONG_MODELS:
        result = _directory_mode(messages, all_skills)
    else:
        result = _injection_mode(messages, all_skills, system_prompt, ide_source)

    # ── Integrate reasoning_bridge provider-specific system prompt ──
    if backend:
        try:
            from opencode_reasoning_bridge import select_provider_system_prompt
            provider_hint = select_provider_system_prompt(backend)
            if provider_hint:
                result = _append_to_system(result, provider_hint)
        except (ImportError, Exception) as _e:
            _log.debug("skills_injector: reasoning_bridge provider hint failed: %s", _e)

    return result


def _append_to_system(messages: list[dict], text: str) -> list[dict]:
    """Append text to the first system message, or create one."""
    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                result[i] = {**msg, "content": content.rstrip() + "\n" + text}
            elif isinstance(content, list):
                result[i] = {
                    **msg,
                    "content": content + [{"type": "text", "text": text}],
                }
            return result
    result.insert(0, {"role": "system", "content": text})
    return result


def _directory_mode(messages: list[dict], all_skills: list[dict]) -> list[dict]:
    """强模型: 只列目录，让模型自己决定需要什么"""
    names = ", ".join(s["id"] for s in all_skills)
    dir_msg = {"role": "system",
               "content": f"Available skills: {names}"}
    result = list(messages)
    if result and result[0].get("role") == "system":
        result.insert(1, dir_msg)
    else:
        result.insert(0, dir_msg)
    return result


def _injection_mode(messages: list[dict], all_skills: list[dict],
                    system_prompt: str, ide_source: str) -> list[dict]:
    """弱模型: 检测缺失，预注入"""
    relevant = _filter_by_ide(all_skills, ide_source)
    missing = detect_missing_skills(system_prompt, relevant)
    return inject_skills(messages, missing)


def _filter_by_ide(skills: list[dict], ide_source: str) -> list[dict]:
    """根据 IDE 已覆盖内容过滤不需要的 skills"""
    if not ide_source:
        return skills
    # For OpenCode, use config from opencode_config
    if ide_source and "opencode" in ide_source.lower():
        covered_cats = OPENCODE_SKIPPED_SKILL_CATEGORIES
    else:
        covered_cats = IDE_COVERAGE.get(ide_source, set())
    if not covered_cats:
        return skills  # Unknown or Cursor — keep all
    return [s for s in skills
            if s.get("category") not in covered_cats
            or s.get("always_apply")]


# ─── Token 估算 ───────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """粗略估算: 1 token ≈ 4 字符"""
    return max(1, len(text) // CHARS_PER_TOKEN)
