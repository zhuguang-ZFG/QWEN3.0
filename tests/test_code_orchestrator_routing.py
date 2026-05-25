import code_orchestrator


def test_try_backends_ranked_skips_terminal_state(monkeypatch):
    calls = []

    monkeypatch.setattr(
        code_orchestrator.runtime_topology,
        "filter_backends",
        lambda pool: pool,
    )
    monkeypatch.setattr(
        code_orchestrator.backend_reputation,
        "sort_by_reputation",
        lambda pool: list(pool),
    )
    monkeypatch.setattr(
        code_orchestrator,
        "_backend_selectable",
        lambda name: name == "scnet_ds_flash",
    )

    def call_fn(backend, msgs, max_tokens):
        calls.append(backend)
        return "valid answer here"

    backend, answer = code_orchestrator._try_backends_ranked(
        "fast",
        [{"role": "user", "content": "fix bug"}],
        call_fn,
        "",
        256,
        __import__("time").time(),
        30.0,
    )

    assert backend == "scnet_ds_flash"
    assert answer.startswith("valid")
    assert calls == ["scnet_ds_flash"]


def test_backend_selectable_respects_cooled_down(monkeypatch):
    import health_tracker

    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda b: b == "kimi")
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda b: {"state": "ok"},
    )
    assert not code_orchestrator._backend_selectable("kimi")
    assert code_orchestrator._backend_selectable("scnet_ds_flash")
