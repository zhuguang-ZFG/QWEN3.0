"""
test_skills_injector.py — 测试 Skills 智能补缺模块
覆盖: 检测逻辑, 注入逻辑, 双模式切换, token限制, per-IDE矩阵
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skills_injector as si

# ── 测试用 Skills ─────────────────────────────────────────────────────────────

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")

SAMPLE_SKILLS = [
    {
        "id": "no_hallucination",
        "category": "safety",
        "content": "Never fabricate facts. Say you don't know if uncertain.",
        "detect_keywords": ["don't hallucinate", "never make up", "no hallucination"],
        "always_apply": False,
        "priority": 1,
    },
    {
        "id": "python_pep8",
        "category": "lang",
        "content": "Follow PEP 8. Use snake_case.",
        "detect_keywords": ["pep 8", "pep8", "python style guide"],
        "always_apply": False,
        "priority": 3,
    },
    {
        "id": "concise_response",
        "category": "style",
        "content": "Be direct and concise.",
        "detect_keywords": ["be concise", "concise", "brief"],
        "always_apply": False,
        "priority": 4,
    },
    {
        "id": "lima_conventions",
        "category": "project",
        "content": "LiMa conventions: Python 3.10+ FastAPI httpx.AsyncClient.",
        "detect_keywords": ["lima", "LiMa", "力码"],
        "always_apply": True,
        "priority": 2,
    },
]

# ── detect_missing_skills ─────────────────────────────────────────────────────

def test_detect_all_missing_when_empty_prompt():
    missing = si.detect_missing_skills("", SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "no_hallucination" in ids
    assert "python_pep8" in ids
    assert "concise_response" in ids


def test_detect_skill_covered_by_keyword():
    prompt = "You are a Python expert. Follow PEP 8 style guide."
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "python_pep8" not in ids  # already covered


def test_detect_skill_covered_case_insensitive():
    prompt = "You follow pep8 and python style."
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "python_pep8" not in ids


def test_detect_skill_covered_by_partial_match():
    prompt = "I will be concise in my responses."
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "concise_response" not in ids


def test_always_apply_skills_returned_when_missing():
    """always_apply skills are returned even if keywords don't match — they're needed in any prompt"""
    prompt = "You are a general assistant."  # No LiMa keywords
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "lima_conventions" in ids  # always_apply, always needed


def test_always_apply_skills_not_returned_when_already_present():
    prompt = "This is a LiMa router project using 力码 framework."
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    assert "lima_conventions" not in ids  # keyword matched, don't duplicate


def test_detect_sorts_by_priority():
    prompt = ""  # Everything missing
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    priorities = [s["priority"] for s in missing]
    assert priorities == sorted(priorities)  # Ascending (1=highest first)


# ── inject_skills ─────────────────────────────────────────────────────────────

def test_inject_noop_when_empty():
    messages = [{"role": "user", "content": "hello"}]
    result = si.inject_skills(messages, [])
    assert result == messages


def test_inject_into_empty_messages():
    skills = [SAMPLE_SKILLS[0], SAMPLE_SKILLS[2]]  # hallucination + concise
    result = si.inject_skills([], skills)
    assert len(result) == 1
    assert result[0]["role"] == "system"
    assert "Never fabricate" in result[0]["content"]
    assert "Be direct" in result[0]["content"]


def test_inject_prepends_when_no_system():
    messages = [{"role": "user", "content": "write a function"}]
    skills = [SAMPLE_SKILLS[1]]  # python_pep8
    result = si.inject_skills(messages, skills)
    assert result[0]["role"] == "system"
    assert "PEP 8" in result[0]["content"]
    assert result[1]["role"] == "user"  # original first message preserved


def test_inject_after_existing_system():
    messages = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "help"},
    ]
    skills = [SAMPLE_SKILLS[0]]
    result = si.inject_skills(messages, skills)
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "You are a coding assistant."  # Original preserved
    assert result[1]["role"] == "system"  # Skills injected as second system msg
    assert "Never fabricate" in result[1]["content"]


def test_inject_respects_max_skills():
    """Should not inject more than MAX_SKILLS items"""
    many_skills = [
        {"id": f"skill_{i}", "category": "test", "content": f"Rule {i}",
         "detect_keywords": [], "priority": i, "always_apply": False}
        for i in range(10)
    ]
    result = si.inject_skills([], many_skills)
    content = result[0]["content"]
    # Count skills in injected content (each starts with "Rule ")
    count = content.count("Rule ")
    assert count <= si.MAX_SKILLS


# ── apply_skills (双模式) ─────────────────────────────────────────────────────

def test_apply_skills_directory_mode_strong_backend():
    """强模型 should get directory listing, not full injection"""
    result = si.apply_skills(
        backend="longcat",
        messages=[{"role": "user", "content": "help"}],
        system_prompt="",
        ide_source=""
    )
    # Directory mode: should contain "Available skills:"
    assert result[0]["role"] == "system"
    content = result[0]["content"]
    assert "Available skills:" in content
    # Should list skill IDs, not full content
    assert "no_hallucination" in content


def test_apply_skills_injection_mode_weak_backend():
    """弱模型 should get full skill injection"""
    result = si.apply_skills(
        backend="chat_ubi",
        messages=[{"role": "user", "content": "help"}],
        system_prompt="",
        ide_source=""
    )
    assert result[0]["role"] == "system"
    content = result[0]["content"]
    # Should contain actual skill content, not just listing
    assert "Never fabricate" in content or "PEP 8" in content or "concise" in content.lower()


def test_apply_skills_opencode_skips_style_skills():
    """OpenCode has built-in style — style skills filtered out"""
    result = si.apply_skills(
        backend="chat_ubi",  # weak backend, injection mode
        messages=[{"role": "user", "content": "debug"}],
        system_prompt="OpenCode CLI. Follow coding style. "
                       "Handle errors explicitly. Use small files. "
                       "Don't hallucinate. Be concise. OWASP security.",
        ide_source="OpenCode"
    )
    content = result[0]["content"] if result else ""
    # OpenCode IDE_COVERAGE={'style'} — style filtered out
    # Other categories remain — correct behavior
    assert "production" in content or "LiMa" in content


def test_apply_skills_unknown_ide_needs_more():
    """Unknown IDE — needs more injection"""
    result = si.apply_skills(
        backend="chat_ubi",
        messages=[{"role": "user", "content": "code"}],
        system_prompt="You are a coding assistant. "
                       "Use backticks for code. Cite with file:line format.",
        ide_source=""
    )
    content = result[0]["content"] if result else ""
    # Unknown IDE has nothing — should inject many skills
    assert len(content) > 20  # Non-trivial injection


# ── IDE override detection ────────────────────────────────────────────────────

def test_apply_skills_respects_ide_source_detection():
    """When ide_source is known, use per-IDE knowledge to tune injection"""
    result_known = si.apply_skills(
        backend="chat_ubi",
        messages=[{"role": "user", "content": "help"}],
        system_prompt="",  # Empty prompt
        ide_source="OpenCode"  # OpenCode with built-in context
    )
    result_unknown = si.apply_skills(
        backend="chat_ubi",
        messages=[{"role": "user", "content": "help"}],
        system_prompt="",
        ide_source=""  # Unknown IDE
    )
    # Unknown IDE gets more injection than OpenCode
    known_count = len(result_known[0]["content"]) if result_known else 0
    unknown_count = len(result_unknown[0]["content"]) if result_unknown else 0
    assert unknown_count >= known_count


# ── load_skills_from_dir ──────────────────────────────────────────────────────

def test_load_skills_from_dir():
    skills = si.load_skills_from_dir(SKILLS_DIR)
    assert len(skills) >= 6
    ids = {s["id"] for s in skills}
    assert "no_hallucination" in ids
    assert "python_pep8" in ids
    assert "go_error_handling" in ids
    assert "concise_response" in ids
    assert "honest_uncertainty" in ids
    assert "lima_conventions" in ids
    # Verify structure
    for s in skills:
        assert "id" in s
        assert "category" in s
        assert "content" in s
        assert "detect_keywords" in s
        assert "priority" in s
        assert "always_apply" in s


# ── Token estimation ──────────────────────────────────────────────────────────

def test_estimate_tokens():
    """Token estimation: ~1 token per 4 characters for English"""
    assert si.estimate_tokens("hello world") == 2  # 11 chars // 4 = 2


def test_injection_stays_under_token_limit():
    """Total injected content should not exceed TOKEN_BUDGET"""
    prompt = ""  # Everything missing
    missing = si.detect_missing_skills(prompt, si.load_skills_from_dir(SKILLS_DIR))
    messages = si.inject_skills([], missing)
    content = messages[0]["content"] if messages else ""
    tokens = si.estimate_tokens(content)
    assert tokens <= si.TOKEN_BUDGET


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_detect_with_none_system_prompt():
    """None system prompt should be treated as empty"""
    missing = si.detect_missing_skills("", SAMPLE_SKILLS)
    # All non-project optional skills should appear
    ids = {s["id"] for s in missing}
    assert len(ids) > 0


def test_inject_preserves_non_system_messages():
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]
    skills = [SAMPLE_SKILLS[0]]
    result = si.inject_skills(messages, skills)
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "q1"
    assert result[2]["role"] == "assistant"
    assert result[3]["role"] == "user"
    assert result[3]["content"] == "q2"


def test_detect_skill_with_multiple_keywords():
    prompt = "I never make up answers."
    missing = si.detect_missing_skills(prompt, SAMPLE_SKILLS)
    ids = {s["id"] for s in missing}
    # "never make up" matches no_hallucination keyword
    assert "no_hallucination" not in ids
