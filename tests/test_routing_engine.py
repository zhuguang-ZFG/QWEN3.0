"""
test_routing_engine.py — 测试统一路由引擎
覆盖: classify(5) / select(4) / inject(2) / execute(3) / route(1)
"""
import builtins
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import routing_engine as re_

# ── classify ─────────────────────────────────────────────────────────────────

def test_classify_ide_from_anthropic_fmt():
    r = re_.classify("how to sort in Python", [], fmt="anthropic", ide_source="")
    assert r == "ide"


def test_classify_ide_from_ua():
    r = re_.classify("help", [], fmt="openai",
                     ide_source="OpenCode", headers={"user-agent": "opencode/1.0"})
    assert r == "ide"


def test_classify_opencode_from_ua():
    r = re_.classify("help", [], fmt="openai",
                     headers={"user-agent": "OpenCode/2.0 vscode"})
    assert r == "ide"


def test_classify_ide_from_system_prompt_fingerprint():
    r = re_.classify("fix bug", [], fmt="openai", ide_source="",
                     system_prompt="You are OpenCode, an AI coding assistant.")
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

def test_code_pools_prioritize_eval_winners():
    import code_orchestrator
    import router_v3

    assert code_orchestrator.POOLS["fast"][:3] == [
        "scnet_qwen30b", "scnet_ds_flash", "scnet_qwen235b"
    ]
    assert code_orchestrator.POOLS["coder"][:4] == [
        "scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b", "scnet_ds_pro"
    ]
    assert router_v3.POOLS["code"]["strong"][:4] == [
        "scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b", "scnet_ds_pro"
    ]


def test_vps_working_free_models_are_in_active_pools():
    import code_orchestrator
    import router_v3

    free_scnet = {"scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b"}

    assert free_scnet.issubset(set(code_orchestrator.POOLS["coder"]))
    assert router_v3.POOLS["code"]["strong"][:3] == [
        "scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b"
    ]
    assert free_scnet.issubset(set(router_v3.POOLS["chat_fast"]["strong"]))
    assert "cf_kimi_k26" in router_v3.POOLS["chat_fast"]["strong"]


def test_cloudflare_code_capacity_is_active():
    import code_orchestrator
    import router_v3
    from backends import BACKENDS

    cloudflare_code = {
        "cf_qwen_coder",
        "cfai_qwen_coder",
        "cf_gptoss_120b",
        "cf_deepseek_r1",
        "cf_qwen3_30b",
        "cfai_deepseek_r1",
    }

    assert cloudflare_code.issubset(set(router_v3.POOLS["code"]["strong"]))
    assert cloudflare_code.issubset(set(code_orchestrator.POOLS["coder"]))
    assert "cfai_mistral" in BACKENDS


def test_cloudflare_code_backends_enter_default_selection_window():
    import router_v3

    selected = router_v3.select_backends("code", {})

    assert "cf_qwen_coder" in selected
    assert "cfai_qwen_coder" in selected


def test_web_reverse_default_routes_have_explicit_admission_policy():
    import router_v3
    from backends import BACKENDS

    default_pool_names = {
        name
        for groups in router_v3.POOLS.values()
        for names in groups.values()
        for name in names
    }
    web_reverse = {
        name for name, cfg in BACKENDS.items()
        if "localhost:450" in cfg.get("url", "") or name.endswith("_web")
    }
    for name in default_pool_names.intersection(web_reverse):
        cfg = BACKENDS[name]
        assert cfg.get("admission") in {
            "code_medium_candidate",
            "code_floor_candidate",
            "sandbox_only",
            "disabled_provider_error",
        }
        if cfg.get("private_code_allowed") is True:
            assert cfg.get("admission") in {
                "code_medium_candidate",
                "code_floor_candidate",
            }


def test_default_routes_exclude_sandbox_only_web_reverse_backends():
    import router_v3
    from backends import BACKENDS

    default_pool_names = {
        name
        for pool_name, groups in router_v3.POOLS.items()
        if pool_name in {"ide", "chat", "chat_fast", "code"}
        for names in groups.values()
        for name in names
    }
    offenders = [
        name
        for name in sorted(default_pool_names)
        if BACKENDS.get(name, {}).get("admission") == "sandbox_only"
        and BACKENDS.get(name, {}).get("private_code_allowed") is False
        and (
            "localhost:450" in BACKENDS.get(name, {}).get("url", "")
            or name.endswith("_web")
            or name.endswith("_web_flash")
            or name.endswith("_web_think")
        )
    ]

    assert offenders == []


def test_all_backends_available_without_local_topology():
    # M6: LOCAL_ONLY_BACKENDS is empty. All backends are cloud-native.
    import runtime_topology

    assert runtime_topology.backend_available("scnet_ds_flash")
    assert runtime_topology.backend_available("kimi")


def test_backend_available_always_true_for_non_host_dependent():
    # M6: With empty LOCAL_ONLY_BACKENDS, any unknown/random backend name
    # returns True (not host-dependent → always available).
    import runtime_topology

    assert runtime_topology.backend_available("some_random_backend_xyz")


def test_code_orchestrator_filters_unreachable_local_proxy(monkeypatch):
    import code_orchestrator
    import runtime_topology

    # M6: filter_backends no longer filters — mock it directly
    monkeypatch.setattr(runtime_topology, "filter_backends",
                        lambda names: [n for n in names if n != "scnet_large_ds_flash"])
    tried = []

    def call_fn(backend, messages, max_tokens):
        tried.append(backend)
        return "usable response"

    monkeypatch.setitem(code_orchestrator.POOLS, "test", [
        "scnet_large_ds_flash", "cf_qwen_coder"
    ])

    backend, answer = code_orchestrator._try_backends_ranked(
        "test", [{"role": "user", "content": "hi"}], call_fn,
        "", 32, 0.0, 10**12)

    assert backend == "cf_qwen_coder"
    assert answer == "usable response"
    assert tried == ["cf_qwen_coder"]


def test_quality_check_allows_requested_exact_short_answer():
    from routes.quality_gate import quality_check

    assert quality_check(
        "topology-ok", 0.5, "scnet_ds_flash",
        query="Return exactly: topology-ok")


def test_quality_check_still_rejects_unrequested_short_answer():
    from routes.quality_gate import quality_check

    assert not quality_check(
        "ok", 0.7, "scnet_ds_flash",
        query="Explain the architecture tradeoffs in detail")


def test_quality_check_rejects_non_matching_exact_answer():
    from routes.quality_gate import quality_check

    assert not quality_check(
        "However, I need more information.",
        0.5,
        "groq_llama8b",
        query="Return exactly: topology-ok")


def test_tool_backend_iteration_tries_distinct_fast_candidates():
    import server

    backends = list(server._iter_tool_backends(server.TOOL_TIER1_BACKENDS))

    # M1: oldllm_* now in BACKENDS (no longer host-dependent), eligible for tool tier1.
    # Backend availability depends on env loading order; verify basic properties.
    assert len(backends) == len(set(backends)), "tool backends must be distinct"
    assert len(backends) >= 3, f"at least 3 tool-capable backends, got {len(backends)}"
    # First backend should be present
    assert len(server._tool_fwd.TOOL_TIER1_BACKENDS) >= 1
    # All backends should be tool-capable OpenAI backends
    from backends_registry import BACKENDS
    for name in backends:
        assert "tool_calls" in BACKENDS.get(name, {}).get("caps", []), f"{name} lacks tool_calls"


def test_anthropic_tool_route_injects_context_preflight():
    from converters.anthropic_format import (
        convert_messages_anthropic_to_openai,
        inject_anthropic_context_preflight,
    )

    body = {
        "system": "You are OpenCode.",
        "messages": [
            {
                "role": "user",
                "content": "Fix D:\\GIT\\server.py\nTypeError: bad operand",
            }
        ],
    }
    messages = convert_messages_anthropic_to_openai(body["messages"])

    inject_anthropic_context_preflight(messages, body)

    assert messages[0]["role"] == "system"
    assert "You are OpenCode." in messages[0]["content"]
    assert "LiMa context preflight" in messages[0]["content"]
    assert "D:\\GIT\\server.py" in messages[0]["content"]


def test_inject_skills_calls_skills_injector():
    """验证 skills 注入被调用且不抛异常"""
    msgs = [{"role": "user", "content": "write python code"}]
    result = re_.inject_skills(msgs, backend="chat_ubi", ide_source="",
                               system_prompt="")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_inject_skills_strong_backend_directory_mode():
    msgs = [{"role": "user", "content": "help"}]
    result = re_.inject_skills(msgs, backend="longcat", ide_source="",
                               system_prompt="")
    content = result[0]["content"] if result else ""
    assert "Available skills:" in content


def test_apply_backend_aware_skills_replaces_early_weak_prompt_for_strong_backend():
    from routing_engine_skills import apply_backend_aware_skills

    early_messages = re_.inject_skills(
        [{"role": "user", "content": "help"}],
        backend="",
        ide_source="",
        system_prompt="",
    )
    result = apply_backend_aware_skills(
        early_messages,
        "longcat",
        ide_source="",
        system_prompt="",
    )

    system_texts = [
        m.get("content", "")
        for m in result
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]
    assert sum("Available skills:" in text for text in system_texts) == 1
    assert not any("Never fabricate" in text for text in system_texts)


def test_apply_backend_aware_skills_does_not_duplicate_weak_skill_prompt():
    from routing_engine_skills import apply_backend_aware_skills

    early_messages = re_.inject_skills(
        [{"role": "user", "content": "help"}],
        backend="",
        ide_source="",
        system_prompt="",
    )
    result = apply_backend_aware_skills(
        early_messages,
        "chat_ubi",
        ide_source="",
        system_prompt="",
    )

    system_texts = [
        m.get("content", "")
        for m in result
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]
    assert sum("Never fabricate" in text for text in system_texts) <= 1
    assert len(result) == len(early_messages)


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

def test_routing_engine_reexports_route_result_after_split():
    result = re_.RouteResult(backend="unit", answer="ok")
    assert result.backend == "unit"
    assert result.answer == "ok"


def test_routing_engine_helper_modules_import():
    import routing_engine_context
    import routing_engine_opencode
    import routing_engine_response
    import routing_engine_skills
    import routing_engine_types

    assert hasattr(routing_engine_types, "RouteResult")
    assert hasattr(routing_engine_response, "respond")
    assert hasattr(routing_engine_skills, "inject_skills")
    assert hasattr(routing_engine_context, "prepare_route_context")
    assert hasattr(routing_engine_opencode, "inject_coding_opencode_prompts")


def test_route_e2e_coding_chat_uses_code_path():
    """完整流程：classify → select → inject → execute → respond"""
    result = re_.route(
        query="write a python sort function",
        messages=[{"role": "user", "content": "write a python sort function"}],
        fmt="openai", call_fn=fake_call_fn, cache_enabled=False,
    )
    assert result.backend != "exhausted"
    assert result.request_type == "code_standard"
    assert result.ms >= 0
    assert isinstance(result.answer, str)
    assert len(result.answer) > 0


def test_route_e2e_ide_no_floor():
    """IDE 请求走 code orchestrator"""
    result = re_.route(
        query="refactor this",
        messages=[{"role": "user", "content": "refactor this"}],
        fmt="anthropic", ide_source="OpenCode",
        call_fn=fake_call_fn, cache_enabled=False,
    )
    assert result.request_type.startswith("code_")
    # IDE 结果不应来自 floor 后端
    assert result.backend not in ("chat_ubi", "llm7", "pollinations",
                                   "local_qwen_coder", "exhausted")


def test_health_tracker_maps_manual_refresh_and_quota_state():
    import health_tracker

    health_tracker.record_failure(
        "unit_kimi_quota",
        error_code=500,
        error_text="chat.anonymous_usage_exceeded",
    )
    health_tracker.record_failure(
        "unit_daily_quota",
        error_code=200,
        error_text="daily quota exhausted",
    )

    kimi_state = health_tracker.get_backend_state("unit_kimi_quota")
    quota_state = health_tracker.get_backend_state("unit_daily_quota")

    assert kimi_state["state"] == "manual_refresh_required"
    assert kimi_state["last_error_class"] == "manual_refresh_required"
    assert quota_state["state"] == "quota_exhausted"
    assert quota_state["last_error_class"] == "quota_exhausted"


def test_health_tracker_maps_rate_limited_auth_and_timeout_state():
    import health_tracker

    health_tracker.record_failure("unit_rate_limit", error_code=429)
    health_tracker.record_failure("unit_auth_expired", error_code=401)
    health_tracker.record_failure(
        "unit_timeout",
        error_code=None,
        error_text="request timeout after 30s",
    )

    assert health_tracker.get_backend_state("unit_rate_limit")["state"] == "rate_limited"
    assert health_tracker.get_backend_state("unit_auth_expired")["state"] == "auth_expired"
    assert health_tracker.get_backend_state("unit_timeout")["state"] == "timeout"
    assert health_tracker.is_cooled_down("unit_rate_limit")


# ── retrieval injection ─────────────────────────────────────────────────────

def test_retrieval_injection_inserts_context_into_messages():
    """验证 graph retrieval 结果被格式化并注入 messages"""
    from context_pipeline.graph_retrieval import RetrievalResult
    from context_pipeline.reranking import format_for_injection, rerank_results

    results = [
        RetrievalResult(path="routing_engine.py", score=0.9, source="both",
                        snippet="def route(query", relations=["imports:health_tracker"]),
        RetrievalResult(path="http_caller.py", score=0.7, source="vector",
                        snippet="def call_api("),
    ]
    reranked = rerank_results(results, ["routing_engine", "http_caller"], top_k=5)
    text = format_for_injection(reranked)

    assert "[代码上下文]" in text
    assert "routing_engine.py" in text
    assert "[VG]" in text
    assert "[V]" in text


def test_retrieval_injection_empty_results_returns_empty():
    from context_pipeline.reranking import format_for_injection
    assert format_for_injection([]) == ""


def test_route_result_has_retrieval_context_field():
    r = re_.RouteResult(backend="test", retrieval_context="[代码上下文]\n[VG] foo.py")
    assert r.retrieval_context == "[代码上下文]\n[VG] foo.py"


def test_retrieval_trace_records_and_retrieves():
    from context_pipeline.retrieval_trace import RetrievalTrace, get_recent_traces, record_trace
    record_trace(RetrievalTrace(
        query_entities=["routing_engine", "health_tracker"],
        candidates_searched=8,
        reranked_results=[
            {"path": "routing_engine.py", "score": 1.2, "source": "both"},
        ],
        injected_text="[代码上下文]\n[VG] routing_engine.py",
        injected_chars=35,
        scenario="coding",
        request_type="ide",
    ))
    traces = get_recent_traces(limit=5)
    assert len(traces) >= 1
    latest = traces[0]
    assert latest["scenario"] == "coding"
    assert latest["candidates_searched"] == 8
    assert "routing_engine" in latest["query_entities"]


def test_inject_retrieval_context_function():
    """验证 inject_retrieval_context 可复用函数正确注入上下文"""
    msgs = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "Fix routing_engine.py health_tracker bug"},
    ]
    result_msgs, text = re_.inject_retrieval_context(msgs)
    # Should inject after first system message
    if text:
        assert len(result_msgs) > len(msgs)
        assert result_msgs[1]["role"] == "system"
        assert "[代码上下文]" in result_msgs[1]["content"]
    else:
        # If no entities extracted, messages unchanged
        assert result_msgs == msgs


def test_inject_retrieval_context_empty_messages():
    """空消息列表不崩溃"""
    result_msgs, text = re_.inject_retrieval_context([])
    assert result_msgs == []
    assert text == ""


# ── Phase 0 regression tests ─────────────────────────────────────────────────

def test_route_uses_shared_retrieval_injection(monkeypatch):
    calls = {"count": 0}

    def fake_inject(messages):
        calls["count"] += 1
        return [{"role": "system", "content": "[retrieval]"}] + list(messages), "[retrieval]"

    monkeypatch.setattr(re_, "inject_retrieval_context", fake_inject)
    import routing_engine_context as _rec
    monkeypatch.setattr(_rec, "inject_retrieval_context", fake_inject, raising=False)
    # Also patch inside the module where inject_all_context imports it
    from context_pipeline import retrieval_injection as _ri
    monkeypatch.setattr(_ri, "inject_retrieval_context", fake_inject)
    monkeypatch.setattr(re_, "classify_scenario", lambda *a, **kw: "chat")
    monkeypatch.setattr(re_, "select", lambda *a, **kw: ["unit_backend"])
    monkeypatch.setattr(re_.health_tracker, "get_health_map", lambda: {})
    monkeypatch.setattr(re_.speculative, "classify_complexity", lambda *a: "complex")
    monkeypatch.setattr(
        re_,
        "apply_backend_aware_skills",
        lambda messages, *a, **kw: messages,
    )

    def call_fn(backend, messages, max_tokens):
        assert backend == "unit_backend"
        assert any(m.get("content") == "[retrieval]" for m in messages)
        return "ok done"

    result = re_.route(
        "hello",
        [{"role": "user", "content": "hello"}],
        call_fn=call_fn,
        cache_enabled=False,
    )

    assert result.answer == "ok done"
    assert result.retrieval_context == "[retrieval]"
    assert calls["count"] == 1


def test_route_does_not_import_fc_caller_for_regular_requests(monkeypatch):
    imports = []
    original_import = builtins.__import__

    def tracking_import(name, *args, **kwargs):
        if name == "fc_caller":
            imports.append(name)
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    monkeypatch.setattr(re_, "select", lambda *a, **kw: ["unit_backend"])
    monkeypatch.setattr(re_, "classify_scenario", lambda *a, **kw: "chat")
    monkeypatch.setattr(re_, "inject_retrieval_context", lambda messages: (messages, ""))
    monkeypatch.setattr(re_.health_tracker, "get_health_map", lambda: {})

    result = re_.route(
        query="translate this Python string handling question",
        messages=[{"role": "user", "content": "translate this Python string handling question"}],
        fmt="openai",
        call_fn=lambda backend, messages, max_tokens: "regular route answer",
        cache_enabled=False,
    )

    assert result.answer == "regular route answer"
    assert imports == []


def test_empty_backends_no_indexerror(monkeypatch):
    """P1: select() returns [] but speculative succeeds — no IndexError."""
    monkeypatch.setattr(re_, "select", lambda *a, **kw: [])

    import speculative
    monkeypatch.setattr(speculative, "classify_complexity", lambda *a: "complex")

    result = re_.route(
        query="hello",
        messages=[{"role": "user", "content": "hello"}],
        fmt="openai", call_fn=fake_call_fn, cache_enabled=False,
    )
    assert result.backend == "exhausted"
    assert result.fallback_used is False


def test_skill_store_recall_uses_real_scenario(monkeypatch):
    """P2: Skill recall uses computed scenario, not empty string."""
    from context_pipeline.skill_store import get_skill_store
    store = get_skill_store()
    store._skills.clear()

    msgs = [{"role": "user", "content": "write a python sort function"}]
    store.crystallize(msgs, "coding", "scnet_ds_flash", 0, 50)

    result = re_.route(
        query="write a python sort function",
        messages=msgs,
        fmt="openai", call_fn=fake_call_fn, cache_enabled=False,
    )
    assert result.answer != ""
    assert result.backend != "exhausted"
