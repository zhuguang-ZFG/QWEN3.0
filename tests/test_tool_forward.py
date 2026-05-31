import routes.tool_forward as tool_forward


def test_pick_tool_backend_skips_unproven_web_adapter(monkeypatch):
    monkeypatch.setattr(
        tool_forward,
        "_tool_backend_selectable",
        lambda name: name == "scnet_large_ds_flash",
    )
    # M6: ddg_* deleted. Use active backends.
    picked = tool_forward.pick_tool_backend(
        ["mimo_web", "scnet_large_ds_flash"],
    )
    assert picked == "scnet_large_ds_flash"


def test_tool_tier_discovery_excludes_host_dependent_backends():
    # M2/M3/M6: scnet_large/kimi now VPS → in TOOL_TIER1; ddg deleted; mimo still in DISABLED
    tool_forward._refresh_tool_tiers()

    assert "scnet_large_ds_flash" in tool_forward.TOOL_TIER1_BACKENDS
    assert "kimi" in tool_forward.TOOL_TIER1_BACKENDS
    # ddg deleted, not testable


def test_tool_backend_selectable_excludes_terminal_state(monkeypatch):
    import health_tracker
    from backends import BACKENDS

    monkeypatch.setitem(BACKENDS, "kimi", {"key": "k1"})
    monkeypatch.setitem(BACKENDS, "github_gpt4o_mini", {"key": "g1"})
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: False)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "manual_refresh_required"} if b == "kimi" else {"state": "ok"},
    )

    assert not tool_forward._tool_backend_selectable("kimi")
    assert tool_forward._tool_backend_selectable("github_gpt4o_mini")
