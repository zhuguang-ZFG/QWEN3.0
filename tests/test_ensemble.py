import asyncio

from context_pipeline.ensemble import (
    ensemble_race,
    select_ensemble_backends,
    should_use_ensemble,
)


def test_ensemble_race_returns_fastest_success():
    async def mock_call(backend: str) -> dict:
        delays = {"fast": 0.01, "medium": 0.05, "slow": 0.1}
        await asyncio.sleep(delays.get(backend, 0.05))
        return {"backend": backend, "content": f"response from {backend}"}

    result = asyncio.run(ensemble_race(["slow", "fast", "medium"], mock_call))

    assert result.winner_backend == "fast"
    assert result.response["backend"] == "fast"
    assert result.strategy == "race"
    assert result.candidates_tried == 3


def test_ensemble_race_skips_failed_backends():
    async def mock_call(backend: str) -> dict:
        if backend == "broken":
            raise ConnectionError("backend down")
        await asyncio.sleep(0.01)
        return {"content": "ok"}

    result = asyncio.run(ensemble_race(["broken", "working"], mock_call))

    assert result.winner_backend == "working"
    assert result.candidates_succeeded >= 1


def test_ensemble_race_all_fail():
    async def mock_call(backend: str) -> dict:
        raise ConnectionError("all down")

    result = asyncio.run(
        ensemble_race(["a", "b"], mock_call, timeout_ms=1000))

    assert result.winner_backend == ""
    assert "error" in result.response


def test_ensemble_race_empty_backends():
    async def noop(b):
        return {}

    result = asyncio.run(ensemble_race([], noop))
    assert result.winner_backend == ""
    assert result.candidates_tried == 0


def test_should_use_ensemble_true_for_ide_coding():
    assert should_use_ensemble("coding", "OpenCode") is True


def test_should_use_ensemble_false_for_chat():
    assert should_use_ensemble("chat", "") is False


def test_should_use_ensemble_false_for_coding_no_ide():
    assert should_use_ensemble("coding", "") is False


def test_select_ensemble_backends():
    candidates = select_ensemble_backends(
        primary="scnet_qwen72b",
        fallback_pool=["groq_llama70b", "cerebras_llama70b", "chat_ubi"],
        max_candidates=3,
    )
    assert candidates[0] == "scnet_qwen72b"
    assert len(candidates) == 3
    assert "chat_ubi" not in candidates or len(candidates) <= 3
