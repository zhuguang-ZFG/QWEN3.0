"""OpenRouter parser/fetch tests."""

import pytest

from provider_automation.catalog import ModelAdmissionStatus
from provider_automation.openrouter import (
    OpenRouterModel,
    create_empty_fixture,
    fetch_live,
    parse_fixture,
)


def test_openrouter_fixture_parser_marks_elephant_watchlist(tmp_path):
    fixture_path = create_empty_fixture(str(tmp_path / "openrouter.json"))

    snapshot = parse_fixture(fixture_path)
    elephant = snapshot.get("elephant/alpha-experimental")

    assert snapshot.provider == "openrouter"
    assert elephant is not None
    assert elephant.pricing == "free"
    assert elephant.endpoint_count == 0
    assert elephant.admission_status is ModelAdmissionStatus.WATCHLIST
    assert "endpoint" in elephant.privacy_note


def test_openrouter_parser_does_not_assume_endpoints():
    entry = OpenRouterModel(
        id="openrouter/no-endpoints",
        name="No Endpoints",
        pricing={"prompt": "0", "completion": "0"},
    ).to_entry()

    assert entry.endpoint_count == 0
    assert entry.admission_status is ModelAdmissionStatus.WATCHLIST
    assert entry.is_routeable is False


def test_openrouter_live_fetch_gate_is_runtime(monkeypatch):
    monkeypatch.delenv("LIMA_OPENROUTER_LIVE_FETCH", raising=False)

    with pytest.raises(RuntimeError, match="LIMA_OPENROUTER_LIVE_FETCH=1"):
        import asyncio

        asyncio.run(fetch_live())
