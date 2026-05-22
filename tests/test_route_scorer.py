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
    assert not route_scorer.is_selectable(
        "kimi", "chat", {"state": "manual_refresh_required"})


def test_ide_route_excludes_unproven_web_adapter():
    assert not route_scorer.is_selectable(
        "ddg_gpt4o_mini", "ide", {"state": "ok"})
    assert route_scorer.is_selectable("scnet_ds_flash", "ide", {"state": "ok"})


def test_routing_select_skips_terminal_state(monkeypatch):
    import routing_engine

    monkeypatch.setattr(
        routing_engine.router_v3,
        "select_backends",
        lambda req_type, health_map: ["kimi", "longcat_chat"],
    )
    monkeypatch.setattr(routing_engine.health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        routing_engine.health_tracker,
        "get_backend_state",
        lambda b: {"state": "manual_refresh_required"} if b == "kimi" else {"state": "ok"},
    )
    monkeypatch.setattr(routing_engine.health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(routing_engine.health_tracker, "get_latency_map", lambda: {})

    assert routing_engine.select("chat", {}) == ["longcat_chat"]


def test_routing_select_excludes_web_adapter_for_ide(monkeypatch):
    import routing_engine

    monkeypatch.setattr(
        routing_engine.router_v3,
        "select_backends",
        lambda req_type, health_map: ["ddg_gpt4o_mini", "scnet_ds_flash"],
    )
    monkeypatch.setattr(routing_engine.health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        routing_engine.health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    monkeypatch.setattr(routing_engine.health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(routing_engine.health_tracker, "get_latency_map", lambda: {})

    assert routing_engine.select("ide", {}) == ["scnet_ds_flash"]
