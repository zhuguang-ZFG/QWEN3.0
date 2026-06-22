"""Tests for routing_intent.analyze_intent (legacy router_classifier replacement)."""

import routing_intent as intent


def test_analyze_intent_trivial_greeting():
    result = intent.analyze_intent("你好")
    assert result is not None
    assert result["intent"] == "trivial"
    assert result["confidence"] >= 0.90


def test_analyze_intent_grbl_config():
    result = intent.analyze_intent("设置 $100 steps_per_mm")
    assert result is not None
    assert result["intent"] == "grbl_config"


def test_analyze_intent_code_generation():
    result = intent.analyze_intent("帮我用 python 实现一个排序算法")
    assert result is not None
    assert result["intent"] == "code_generation"
    assert result["needs_code"] is True


def test_analyze_intent_thinking_takes_priority():
    result = intent.analyze_intent("请仔细分析并证明根号2是无理数")
    assert result["intent"] == "thinking"
    assert result["source"] == "thinking_detect"


def test_analyze_intent_code_block_detect():
    query = "```python\ndef foo():\n    pass\n```"
    result = intent.analyze_intent(query, ide="cursor")
    assert result["intent"] == "code_generation"
    assert result["source"] in ("code_detect", "rules", "signal_v2", "ide_context")


def test_analyze_intent_default_fallback():
    result = intent.analyze_intent("xyz ambiguous request without strong signals")
    assert result["intent"] == "chat"
    assert result["source"] == "default_fallback"


def test_analyze_intent_device_home():
    result = intent.analyze_intent("帮我回家")
    assert result["intent"] == "device_home"
    assert result["confidence"] >= 0.90


def test_analyze_intent_device_stop():
    result = intent.analyze_intent("急停")
    assert result["intent"] == "device_stop"
    assert result["needs_code"] is False
    assert isinstance(result["needs_code"], bool)


def test_analyze_intent_device_write():
    result = intent.analyze_intent("写一行生日快乐")
    assert result["intent"] == "device_write"


def test_analyze_intent_device_status():
    result = intent.analyze_intent("设备在线吗")
    assert result["intent"] == "device_status"


def test_intent_to_prompt_scenario_maps_stop_to_device_control():
    assert intent.intent_to_prompt_scenario("device_stop") == "device_control"
    assert intent.intent_to_prompt_scenario("device_draw") == "device_draw"
    assert intent.intent_to_prompt_scenario("chat") is None


def test_analyze_intent_signal_device_draw_when_rules_miss():
    result = intent.analyze_intent("帮我画个房子")
    assert result["intent"] in ("device_draw", "image_gen")


def test_detect_thinking_intent_patterns():
    assert intent.detect_thinking_intent("think step by step about this proof") is True
    assert intent.detect_thinking_intent("hello world") is False


def test_pick_backend_scenario_uses_device_prompt_scenario(monkeypatch):
    import routing_engine

    monkeypatch.setattr(routing_engine, "classify", lambda *a, **k: "chat")
    monkeypatch.setattr(routing_engine, "classify_scenario", lambda *a, **k: "chat")
    monkeypatch.setattr(routing_engine, "try_recall_backend", lambda *a, **k: None)
    monkeypatch.setattr(routing_engine, "inject_retrieval_context", lambda msgs: (msgs, ""))
    monkeypatch.setattr(routing_engine, "inject_coding_context", lambda msgs, *a, **k: (msgs, ""))
    monkeypatch.setattr(routing_engine, "assess_complexity", lambda *a, **k: {})
    monkeypatch.setattr(routing_engine.sticky_session, "compute_key", lambda *a, **k: "k")
    monkeypatch.setattr(routing_engine.health_tracker, "get_health_map", lambda: {})
    monkeypatch.setattr(routing_engine, "select", lambda *a, **k: ["longcat_chat"])

    picked = routing_engine.pick_backend("急停", [{"role": "user", "content": "急停"}])
    assert picked.scenario == "device_control"
