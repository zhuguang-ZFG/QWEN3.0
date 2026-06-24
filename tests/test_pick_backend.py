"""routing_engine.pick_backend() 单元测试。

覆盖 pick_backend 的 11 条核心路径：classify/scenario 转发、sticky recall、
retrieval 注入、select 参数透传、空回退、headers 处理。
所有内部依赖通过 monkeypatch 替换。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import routing_engine
from routing_engine import PickResult, pick_backend

# 用于跟踪消息在流水线中流转的标记消息
_MSGS_RETRIEVAL: list[dict] = [{"role": "user", "content": "after-retrieval"}]
_MSGS_ENRICHED: list[dict] = [{"role": "user", "content": "enriched"}]
_DEFAULT_MSGS: list[dict] = [{"role": "user", "content": "hi"}]


def _make_module_mock(**methods: MagicMock) -> MagicMock:
    """创建一个模块级 mock，挂载指定方法。"""
    mod = MagicMock()
    for name, fn in methods.items():
        setattr(mod, name, fn)
    return mod


@pytest.fixture()
def mocks(monkeypatch):
    """为 pick_backend 的所有内部依赖设置默认 mock 并返回 mock 字典。"""
    sticky_compute = MagicMock(return_value="test-key")
    health_get = MagicMock(return_value={"be": {"ok": True}})

    m: dict[str, MagicMock] = {
        "classify": MagicMock(return_value="chat"),
        "classify_scenario": MagicMock(return_value="chat"),
        "try_recall_backend": MagicMock(return_value=None),
        "inject_retrieval_context": MagicMock(return_value=(_MSGS_RETRIEVAL, "")),
        "select": MagicMock(return_value=["alpha", "beta"]),
        "_enrich_with_intent_and_skills": MagicMock(return_value=(_MSGS_ENRICHED, "chat")),
    }
    # 模块对象需要特殊处理
    m["sticky_session"] = _make_module_mock(compute_key=sticky_compute)
    m["health_tracker"] = _make_module_mock(get_health_map=health_get)

    for attr, mock in m.items():
        monkeypatch.setattr(routing_engine, attr, mock)
    return m


# ---------------------------------------------------------------------------
# 1. 基本 happy path — PickResult 所有字段正确填充
# ---------------------------------------------------------------------------

def test_happy_path_returns_pick_result(mocks):
    """验证 pick_backend 返回包含所有预期字段的 PickResult。"""
    msgs = [{"role": "user", "content": "hello"}]
    result = pick_backend("hello", msgs)

    assert isinstance(result, PickResult)
    assert result.backend == "alpha"
    assert result.backends == ["alpha", "beta"]
    assert result.messages is _MSGS_ENRICHED
    assert result.request_type == "chat"
    assert result.scenario == "chat"
    assert result.retrieval_context == ""
    assert result.sticky_key == "test-key"

    # query 和原始 messages 正确转发到 classify()
    args, _ = mocks["classify"].call_args
    assert args[0] == "hello"
    assert args[1] is msgs


# ---------------------------------------------------------------------------
# 2. fmt 参数正确转发到 classify()
# ---------------------------------------------------------------------------

def test_fmt_forwarded_to_classify(mocks):
    """fmt="anthropic" 应透传至 classify 的关键字参数。"""
    pick_backend("q", _DEFAULT_MSGS, fmt="anthropic")
    _, kwargs = mocks["classify"].call_args
    assert kwargs["fmt"] == "anthropic"


# ---------------------------------------------------------------------------
# 3. ide_source 参数正确转发到 classify()
# ---------------------------------------------------------------------------

def test_ide_source_forwarded_to_classify(mocks):
    """ide_source="cursor" 应透传至 classify 的关键字参数。"""
    pick_backend("q", _DEFAULT_MSGS, ide_source="cursor")
    _, kwargs = mocks["classify"].call_args
    assert kwargs["ide_source"] == "cursor"


# ---------------------------------------------------------------------------
# 4. classify_scenario 返回 "coding" 时正确转发到 select()
# ---------------------------------------------------------------------------

def test_classify_scenario_coding_forwarded_to_select(mocks):
    """scenario="coding" 应作为关键字参数传递给 select()。"""
    mocks["classify_scenario"].return_value = "coding"
    pick_backend("write a function", _DEFAULT_MSGS)

    _, kwargs = mocks["select"].call_args
    assert kwargs["scenario"] == "coding"


# ---------------------------------------------------------------------------
# 5. try_recall_backend 返回已召回后端 → 传给 select()
# ---------------------------------------------------------------------------

def test_recalled_backend_forwarded_to_select(mocks):
    """当 sticky recall 命中时，recalled_backend 应传给 select()。"""
    mocks["try_recall_backend"].return_value = "recalled_be"
    pick_backend("q", _DEFAULT_MSGS)

    _, kwargs = mocks["select"].call_args
    assert kwargs["recalled_backend"] == "recalled_be"


# ---------------------------------------------------------------------------
# 6. try_recall_backend 返回 None → recalled_backend=None 传给 select()
# ---------------------------------------------------------------------------

def test_no_recalled_backend_forwarded_as_none(mocks):
    """当 sticky recall 未命中时，recalled_backend 应为 None。"""
    mocks["try_recall_backend"].return_value = None
    pick_backend("q", _DEFAULT_MSGS)

    _, kwargs = mocks["select"].call_args
    assert kwargs["recalled_backend"] is None


# ---------------------------------------------------------------------------
# 7. inject_retrieval_context 返回非空文本 → retrieval_context 填充
# ---------------------------------------------------------------------------

def test_retrieval_context_populated(mocks):
    """retrieval 注入有内容时，PickResult.retrieval_context 应非空。"""
    mocks["inject_retrieval_context"].return_value = (_MSGS_RETRIEVAL, "some context text")
    result = pick_backend("q", _DEFAULT_MSGS)

    assert result.retrieval_context == "some context text"


# ---------------------------------------------------------------------------
# 8. needs_tools=True 正确转发到 select()
# ---------------------------------------------------------------------------

def test_needs_tools_forwarded_to_select(mocks):
    """needs_tools=True 应透传至 select() 的关键字参数。"""
    pick_backend("q", _DEFAULT_MSGS, needs_tools=True)
    _, kwargs = mocks["select"].call_args
    assert kwargs["needs_tools"] is True


# ---------------------------------------------------------------------------
# 9. preferred_backend 正确转发到 select()
# ---------------------------------------------------------------------------

def test_preferred_backend_forwarded_to_select(mocks):
    """preferred_backend="openai" 应透传至 select() 的关键字参数。"""
    pick_backend("q", _DEFAULT_MSGS, preferred_backend="openai")
    _, kwargs = mocks["select"].call_args
    assert kwargs["preferred_backend"] == "openai"


# ---------------------------------------------------------------------------
# 10. select() 返回空列表 → backend 回退到 "longcat_chat"
# ---------------------------------------------------------------------------

def test_empty_select_falls_back_to_longcat_chat(mocks):
    """当 select() 无可用后端时，backend 应回退到 longcat_chat。"""
    mocks["select"].return_value = []
    result = pick_backend("q", _DEFAULT_MSGS)

    assert result.backend == "longcat_chat"
    assert result.backends == []


# ---------------------------------------------------------------------------
# 11. headers 正确转发到 classify()
# ---------------------------------------------------------------------------

def test_headers_forwarded_to_classify(mocks):
    """自定义 headers 应透传至 classify()。"""
    hdrs = {"x-custom": "val", "authorization": "Bearer t"}
    pick_backend("q", _DEFAULT_MSGS, headers=hdrs)

    _, kwargs = mocks["classify"].call_args
    assert kwargs["headers"] == hdrs


def test_headers_none_sends_empty_dict(mocks):
    """headers=None 时 classify 应收到空 dict。"""
    pick_backend("q", _DEFAULT_MSGS, headers=None)

    _, kwargs = mocks["classify"].call_args
    assert kwargs["headers"] == {}


# ---------------------------------------------------------------------------
# 额外覆盖：model 转发到 compute_key、system_prompt 转发到 classify
# ---------------------------------------------------------------------------

def test_model_forwarded_to_compute_key(mocks):
    """指定 model 时应传给 sticky_session.compute_key。"""
    pick_backend("q", _DEFAULT_MSGS, model="gpt-4o")
    mocks["sticky_session"].compute_key.assert_called_once()
    args, _ = mocks["sticky_session"].compute_key.call_args
    assert args[0] == "gpt-4o"


def test_default_model_uses_default_string(mocks):
    """未指定 model 时 compute_key 应收到 'default'。"""
    pick_backend("q", _DEFAULT_MSGS)
    args, _ = mocks["sticky_session"].compute_key.call_args
    assert args[0] == "default"


def test_system_prompt_forwarded_to_classify(mocks):
    """system_prompt 应透传至 classify()。"""
    pick_backend("q", _DEFAULT_MSGS, system_prompt="You are helpful.")
    _, kwargs = mocks["classify"].call_args
    assert kwargs["system_prompt"] == "You are helpful."


def test_system_prompt_forwarded_to_enrich(mocks):
    """system_prompt 应透传至 _enrich_with_intent_and_skills()。"""
    pick_backend("q", _DEFAULT_MSGS, system_prompt="Be concise.")
    args, _ = mocks["_enrich_with_intent_and_skills"].call_args
    assert args[2] == "Be concise."


def test_single_backend_result(mocks):
    """select() 返回单个后端时，backend 和 backends 均正确。"""
    mocks["select"].return_value = ["only_one"]
    result = pick_backend("q", _DEFAULT_MSGS)

    assert result.backend == "only_one"
    assert result.backends == ["only_one"]
