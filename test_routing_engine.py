"""
test_routing_engine.py — 测试统一路由引擎
覆盖: classify(5) / select(4) / inject(2) / execute(3) / route(1)
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import routing_engine as re_


# ── classify ─────────────────────────────────────────────────────────────────

def test_classify_ide_from_anthropic_fmt():
    r = re_.classify("how to sort in Python", [], fmt="anthropic", ide_source="")
    assert r == "ide"


def test_classify_ide_from_ua():
    r = re_.classify("help", [], fmt="openai",
                     ide_source="Claude Code", headers={"user-agent": "claude-code/2.1"})
    assert r == "ide"


def test_classify_ide_from_system_prompt_fingerprint():
    r = re_.classify("fix bug", [], fmt="openai", ide_source="",
                     system_prompt="You are Cursor, an AI coding assistant. Use <user_query> tags.")
    assert r == "ide"


def test_classify_chat_default():
    r = re_.classify("hello world", [], fmt="openai", ide_source="")
    assert r == "chat"


def test_classify_vision_from_image_blocks():
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "what is this?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}}
    ]}]
    r = re_.classify("", msgs, fmt="openai", ide_source="")
    assert r == "vision"


# ── select ───────────────────────────────────────────────────────────────────

def make_healthy_map() -> dict:
    return {"longcat_chat": "healthy", "deepseek_flash": "healthy",
            "naga_llama70b": "healthy", "naga_gpt41mini": "healthy",
            "freetheai_ds": "healthy", "unclose_hermes": "healthy",
            "longcat_lite": "healthy", "chat_ubi": "healthy",
            "llm7": "healthy", "pollinations": "healthy",
            "local_qwen_coder": "healthy"}


def test_select_ide_excludes_floor():
    """IDE 请求不走 floor 层"""
    backends = re_.select("ide", make_healthy_map())
    assert "chat_ubi" not in backends
    assert "pollinations" not in backends
    assert "local_qwen_coder" not in backends


def test_select_chat_includes_floor():
    """Chat 请求当 strong+medium 全死时 fallback 到 floor"""
    hmap = make_healthy_map()
    # 把 chat pool 的 strong + medium 全标死
    import router_v3
    pool = router_v3.POOLS["chat"]
    for b in pool.get("strong", []) + pool.get("medium", []):
        hmap[b] = "dead"
    backends = re_.select("chat", hmap)
    # 应该包含 floor 层后端
    floor_backends = set(pool.get("floor", []))
    has_floor = any(b in floor_backends for b in backends)
    assert has_floor


def test_select_excludes_dead():
    hmap = make_healthy_map()
    hmap["longcat_chat"] = "dead"
    backends = re_.select("chat", hmap)
    assert "longcat_chat" not in backends


def test_select_sticky_priority():
    backends = re_.select("chat", make_healthy_map(), sticky_key=None)
    # Without sticky, no priority — just verify we get a list
    assert len(backends) > 0
    assert isinstance(backends, list)


# ── inject skills ───────────────────────────────────────────────────────────

def test_inject_skills_calls_skills_injector():
    """验证 skills 注入被调用且不抛异常"""
    msgs = [{"role": "user", "content": "write python code"}]
    result = re_.inject_skills(msgs, backend="chat_ubi", ide_source="",
                               system_prompt="")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_inject_skills_strong_backend_directory_mode():
    msgs = [{"role": "user", "content": "help"}]
    result = re_.inject_skills(msgs, backend="longcat_chat", ide_source="",
                               system_prompt="")
    content = result[0]["content"] if result else ""
    assert "Available skills:" in content


# ── execute ──────────────────────────────────────────────────────────────────

def fake_call_fn(backend, messages, max_tokens=4096):
    """模拟后端调用：所有后端成功（测试路由逻辑，非后端行为）"""
    return f"Hello from {backend}, I am LiMa."


def fake_call_fn_all_fail(backend, messages, max_tokens=4096):
    raise Exception("all down")


def test_execute_success_first_try():
    backends = ["longcat_chat", "deepseek_flash"]
    backend, answer, errors = re_.execute(
        backends, fake_call_fn, [{"role": "user", "content": "hi"}])
    assert backend == "longcat_chat"
    assert "LiMa" in answer
    assert errors == 0


def test_execute_fallback_on_failure():
    """第一个失败，第二个成功"""
    def _call(backend, messages, max_tokens=4096):
        if backend == "deepseek_flash":
            return "Fallback answer"
        raise Exception("fail")
    backends = ["longcat_chat", "deepseek_flash"]
    backend, answer, errors = re_.execute(
        backends, _call, [{"role": "user", "content": "hi"}])
    assert backend == "deepseek_flash"
    assert answer == "Fallback answer"


def test_execute_exhausted_all_fail():
    backends = ["longcat_chat", "deepseek_flash"]
    backend, answer, errors = re_.execute(
        backends, fake_call_fn_all_fail,
        [{"role": "user", "content": "hi"}])
    assert backend == "exhausted"
    assert answer == ""


# ── route (end-to-end) ──────────────────────────────────────────────────────

def test_route_e2e_chat():
    """完整流程：classify → select → inject → execute → respond"""
    result = re_.route(
        query="write a python sort function",
        messages=[{"role": "user", "content": "write a python sort function"}],
        fmt="openai", call_fn=fake_call_fn,
    )
    assert result.backend != "exhausted"
    assert result.request_type == "chat"
    assert result.ms >= 0
    assert isinstance(result.answer, str)
    assert len(result.answer) > 0


def test_route_e2e_ide_no_floor():
    """IDE 请求不路由到 floor"""
    result = re_.route(
        query="refactor this",
        messages=[{"role": "user", "content": "refactor this"}],
        fmt="anthropic", ide_source="Claude Code",
        call_fn=fake_call_fn,
    )
    assert result.request_type == "ide"
    # IDE 结果不应来自 floor 后端
    assert result.backend not in ("chat_ubi", "llm7", "pollinations",
                                   "local_qwen_coder", "exhausted")
