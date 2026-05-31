import time


def test_operator_probe_records_timeout(monkeypatch):
    import backend_probe_loop

    def slow_probe(backend: str, *, ignore_cooldown: bool = False) -> dict:
        time.sleep(0.1)
        return {"backend": backend, "status": "healthy", "latency_ms": 100}

    recorded = []
    monkeypatch.setattr(backend_probe_loop, "probe_backend", slow_probe)
    monkeypatch.setattr(
        backend_probe_loop,
        "record_probe_result",
        lambda result: recorded.append(result) or True,
    )

    result = backend_probe_loop.probe_and_record_backend(
        "slow_backend",
        timeout_sec=0.01,
    )

    assert result["backend"] == "slow_backend"
    assert result["status"] == "failed"
    assert result["error_class"] == "timeout"
    assert result["timed_out"] is True
    assert result["recorded"] is True
    assert recorded and recorded[0]["error_class"] == "timeout"
