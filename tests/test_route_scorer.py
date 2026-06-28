import route_scorer


def test_effective_score_prefers_healthy_fast_free_backend():
    ranked = route_scorer.rank_backends(
        ["slow_paid", "groq_gptoss_20b"],
        "chat",
        "chat",
        health_scores={"slow_paid": 45, "groq_gptoss_20b": 95},
        latency_map={"slow_paid": 4500, "groq_gptoss_20b": 400},
    )

    assert ranked[0] == "groq_gptoss_20b"


def test_terminal_state_is_not_selectable():
    assert not route_scorer.is_selectable("kimi", "chat", {"state": "manual_refresh_required"})


def test_ide_route_excludes_unproven_web_adapter():
    assert not route_scorer.is_selectable("ddg_gpt4o_mini", "ide", {"state": "ok"})
    assert route_scorer.is_selectable("scnet_ds_flash", "ide", {"state": "ok"})


def test_routing_select_skips_terminal_state(monkeypatch):
    import health_tracker
    import router_v3
    from routing_selector import select

    monkeypatch.setattr(
        router_v3,
        "select_backends",
        lambda req_type, health_map: ["kimi", "longcat_chat"],
    )
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "manual_refresh_required"} if b == "kimi" else {"state": "ok"},
    )
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})

    assert select("chat", {}) == ["longcat_chat"]


def test_routing_select_excludes_web_adapter_for_ide(monkeypatch):
    import health_tracker
    import router_v3
    from routing_selector import select

    monkeypatch.setattr(
        router_v3,
        "select_backends",
        lambda req_type, health_map: ["ddg_gpt4o_mini", "scnet_ds_flash"],
    )
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})

    assert select("ide", {}) == ["scnet_ds_flash"]


def test_routing_select_excludes_retired_backend(monkeypatch):
    import backend_retirement
    import health_tracker
    import router_v3
    from routing_selector import select

    backend_retirement._retired_backends.clear()
    backend_retirement._retired_backends.add("oldllm_gpt54")
    monkeypatch.setattr(
        router_v3,
        "select_backends",
        lambda req_type, health_map: ["oldllm_gpt54", "longcat_chat"],
    )
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})

    try:
        assert select("chat", {}) == ["longcat_chat"]
    finally:
        backend_retirement._retired_backends.clear()


def test_routing_selector_identifies_strong_coding_tool_backend():
    import routing_selector

    assert routing_selector._is_strong_coding_tool_backend(
        "github_gpt4o_code",
        {"caps": ["tool_calls"], "admission": "code_medium_candidate"},
    )
    assert not routing_selector._is_strong_coding_tool_backend(
        "mistral_small",
        {"caps": ["tool_calls"]},
    )


def test_routing_select_skips_recently_quarantined_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    from observability.backend_telemetry import record_backend_attempt

    assert record_backend_attempt(
        backend="flaky_backend",
        success=False,
        response_empty=True,
    )

    import health_tracker
    import router_v3
    from routing_selector import select

    monkeypatch.setattr(
        router_v3,
        "select_backends",
        lambda req_type, health_map: ["flaky_backend", "stable_backend"],
    )
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})

    assert select("chat", {}) == ["stable_backend"]


def test_routing_select_keeps_only_backend_even_if_quarantined(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    from observability.backend_telemetry import record_backend_attempt

    assert record_backend_attempt(
        backend="only_backend",
        success=False,
        response_empty=True,
    )

    import health_tracker
    import router_v3
    from routing_selector import select

    monkeypatch.setattr(
        router_v3,
        "select_backends",
        lambda req_type, health_map: ["only_backend"],
    )
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})

    assert select("chat", {}) == ["only_backend"]


def test_effective_score_logs_and_fallback_on_reputation_failure(monkeypatch, caplog):
    import backend_reputation

    monkeypatch.setattr(backend_reputation, "get_stats", lambda: (_ for _ in ()).throw(RuntimeError("rep boom")))
    with caplog.at_level("WARNING"):
        score = route_scorer.effective_score("some_backend", "chat")
    assert 0.0 <= score <= 1.0
    assert any("backend_reputation score failed" in rec.message for rec in caplog.records)


def test_effective_score_logs_and_fallback_on_routing_weights_failure(monkeypatch, caplog):
    import context_pipeline.routing_weights as routing_weights

    def _raise(*args, **kwargs):
        raise RuntimeError("weights boom")

    monkeypatch.setattr(routing_weights, "get_routing_weights", _raise)
    with caplog.at_level("WARNING"):
        score = route_scorer.effective_score("some_backend", "chat")
    assert 0.0 <= score <= 1.0
    assert any("routing_weights lookup failed" in rec.message for rec in caplog.records)


def test_effective_score_logs_and_fallback_on_backend_profile_failure(monkeypatch, caplog):
    import backend_profile

    def _raise(*args, **kwargs):
        raise RuntimeError("profile boom")

    monkeypatch.setattr(backend_profile, "get_profile", _raise)
    with caplog.at_level("WARNING"):
        score = route_scorer.effective_score("some_backend", "chat")
    assert 0.0 <= score <= 1.0
    assert any("backend_profile score failed" in rec.message for rec in caplog.records)
