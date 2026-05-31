import routes.tool_forward as tool_forward


def test_pick_tool_backend_skips_unproven_web_adapter(monkeypatch):
    monkeypatch.setattr(
        tool_forward,
        "_tool_backend_selectable",
        lambda name: name == "scnet_large_ds_flash",
    )
    picked = tool_forward.pick_tool_backend(
        ["ddg_gpt4o_mini", "scnet_large_ds_flash"],
    )
    assert picked == "scnet_large_ds_flash"


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


def test_large_tool_payload_prefers_strong_coding_backend(monkeypatch):
    from backends import BACKENDS

    monkeypatch.setitem(
        BACKENDS,
        "mistral_small",
        {"key": "k1", "timeout": 10, "caps": ["tool_calls"]},
    )
    monkeypatch.setitem(
        BACKENDS,
        "github_gpt4o_code",
        {
            "key": "k2",
            "timeout": 30,
            "caps": ["tool_calls"],
            "admission": "code_medium_candidate",
            "private_code_allowed": True,
        },
    )

    ranked = tool_forward._rank_tool_tier(
        ["mistral_small", "github_gpt4o_code"],
        body_size=tool_forward.LARGE_TOOL_PAYLOAD_BYTES + 1,
    )

    assert ranked[0] == "github_gpt4o_code"


def test_small_tool_payload_keeps_fast_backend_first(monkeypatch):
    from backends import BACKENDS

    monkeypatch.setitem(
        BACKENDS,
        "mistral_small",
        {"key": "k1", "timeout": 10, "caps": ["tool_calls"]},
    )
    monkeypatch.setitem(
        BACKENDS,
        "github_gpt4o_code",
        {
            "key": "k2",
            "timeout": 30,
            "caps": ["tool_calls"],
            "admission": "code_medium_candidate",
            "private_code_allowed": True,
        },
    )

    ranked = tool_forward._rank_tool_tier(
        ["mistral_small", "github_gpt4o_code"],
        body_size=1000,
    )

    assert ranked[0] == "mistral_small"
