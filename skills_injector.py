"""
LiMa Skills Injector — 智能补缺注入
基于 Cursor/Claude Code/Codex 逆向分析设计。

双模式:
- 强模型(可 tool call): 列目录，让模型自己拉取 (Cursor 模式)
- 弱模型(无 tool call): 检测缺失，预注入最少 skills

核心原则: 逐条检测 → 只补缺的 → 最多5条 → 不超200 token
"""

import logging
import os
import glob as glob_mod

from backends_constants import STRONG_MODELS
import skills_registry

logger = logging.getLogger(__name__)

# ─── 常量 ─────────────────────────────────────────────────────────────────────

MAX_SKILLS = 5
TOKEN_BUDGET = 200
CHARS_PER_TOKEN = 4

IDE_COVERAGE = {
    # IDE → set of categories already well-covered by built-in system prompt
    "Claude Code": {"safety", "lang", "style"},  # 8000 tok covers almost everything
    "Cursor": set(),  # 642 tok covers almost nothing
    "Codex": {"style"},  # 4000 tok, 30% personality
    "Aider": {"safety", "lang"},  # 2000 tok
    "Cline": {"safety", "style"},  # 4000 tok
}


# ─── YAML frontmatter 解析 (零依赖) ───────────────────────────────────────────


def parse_frontmatter(text: str) -> tuple[dict, str]:
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
    return meta, text[end + 3 :].strip()


# ─── Skills 加载 ──────────────────────────────────────────────────────────────


def load_skills_from_dir(skills_dir: str) -> list[dict]:
    """从 skills/ 目录加载所有 .md 文件，解析 frontmatter + body"""
    skills = []
    pattern = os.path.join(skills_dir, "**", "*.md")
    for fpath in glob_mod.glob(pattern, recursive=True):
        try:
            with open(fpath, encoding="utf-8") as f:
                raw = f.read()
            meta, body = parse_frontmatter(raw)
            if not meta or "id" not in meta:
                continue
            skills.append(
                {
                    "id": meta["id"],
                    "category": meta.get("category", "general"),
                    "content": body,
                    "detect_keywords": meta.get("detect_keywords", []),
                    "always_apply": meta.get("always_apply", False),
                    "priority": meta.get("priority", 5),
                    "globs": meta.get("globs", []),
                }
            )
        except Exception as exc:
            logger.warning("failed to load skill from %s: %s", fpath, exc, exc_info=True)
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
    return text[: max_chars - 3] + "..."


# ─── 双模式入口 ───────────────────────────────────────────────────────────────


def _skills_root(skills_dir: str) -> str:
    return skills_dir or os.path.join(os.path.dirname(__file__), "skills")


def apply_skills(
    backend: str,
    messages: list[dict],
    system_prompt: str = "",
    ide_source: str = "",
    skills_dir: str = "",
    intent: str = "",
    route_role: str = "",
    scenario: str = "",
) -> list[dict]:
    """
    根据后端能力选择策略:
    - 强模型 → 目录模式 (只列 skill 名)
    - 弱模型 → registry 触发注入，否则检测缺失并预注入
    """
    root = _skills_root(skills_dir)
    all_skills = load_skills_from_dir(root)
    registry_skills = skills_registry.load_registry_skills(root)

    if not all_skills and not registry_skills:
        return list(messages)

    if backend in STRONG_MODELS:
        catalog = all_skills or registry_skills
        return _directory_mode(messages, catalog)

    return _injection_mode(
        messages,
        all_skills,
        system_prompt,
        ide_source,
        registry_skills=registry_skills,
        intent=intent,
        route_role=route_role,
        scenario=scenario,
    )


def _directory_mode(messages: list[dict], all_skills: list[dict]) -> list[dict]:
    """强模型: 只列目录，让模型自己决定需要什么"""
    names = ", ".join(s["id"] for s in all_skills)
    dir_msg = {"role": "system", "content": f"Available skills: {names}"}
    result = list(messages)
    if result and result[0].get("role") == "system":
        result.insert(1, dir_msg)
    else:
        result.insert(0, dir_msg)
    return result


def _injection_mode(
    messages: list[dict],
    all_skills: list[dict],
    system_prompt: str,
    ide_source: str,
    *,
    registry_skills: list[dict],
    intent: str = "",
    route_role: str = "",
    scenario: str = "",
) -> list[dict]:
    """弱模型: registry 触发优先，否则检测缺失并预注入"""
    triggered = skills_registry.select_triggered_skills(
        registry_skills,
        intent=intent,
        route_role=route_role,
        scenario=scenario,
    )
    if triggered:
        return inject_skills(messages, triggered)

    if not all_skills:
        return list(messages)

    relevant = _filter_by_ide(all_skills, ide_source)
    missing = detect_missing_skills(system_prompt, relevant)
    return inject_skills(messages, missing)


def _filter_by_ide(skills: list[dict], ide_source: str) -> list[dict]:
    """根据 IDE 已覆盖内容过滤不需要的 skills"""
    if not ide_source:
        return skills
    covered_cats = IDE_COVERAGE.get(ide_source, set())
    if not covered_cats:
        return skills  # Unknown or Cursor — keep all
    return [s for s in skills if s.get("category") not in covered_cats or s.get("always_apply")]


# ─── Token 估算 ───────────────────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """粗略估算: 1 token ≈ 4 字符"""
    return max(1, len(text) // CHARS_PER_TOKEN)
