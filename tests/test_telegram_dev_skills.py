"""Tests for Telegram developer skills bridge."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import routes.telegram_dev_skills as dev_mod


@pytest.fixture(autouse=True)
def _mock_send(monkeypatch):
    """Replace telegram_bot.send_message on the target module."""
    sent: list[str] = []
    monkeypatch.setattr(
        dev_mod.telegram_bot,
        "send_message",
        AsyncMock(side_effect=lambda text, **kw: sent.append(text)),
    )
    return sent


def _run(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── /investigate ──────────────────────────────────────────────────────────────

class TestCmdInvestigate:
    def test_no_args_shows_usage(self, _mock_send):
        _run(dev_mod.cmd_investigate("chat1", ""))
        assert any("Usage" in m for m in _mock_send)

    def test_with_target_calls_investigate(self, _mock_send):
        mock_result = MagicMock()
        mock_result.details = ["Found 5 symbols", "Related: foo.py"]
        mock_result.evidence = ["ast_symbols:5"]

        with patch("developer_skills.investigate.investigate", return_value=mock_result):
            _run(dev_mod.cmd_investigate("chat1", "routing_engine.py"))

        assert any("Investigation" in m or "routing_engine" in m for m in _mock_send)

    def test_investigate_failure_sends_error(self, _mock_send):
        with patch("developer_skills.investigate.investigate", side_effect=RuntimeError("boom")):
            _run(dev_mod.cmd_investigate("chat1", "file.py"))

        assert any("failed" in m.lower() or "RuntimeError" in m for m in _mock_send)


# ── /review ───────────────────────────────────────────────────────────────────

class TestCmdReview:
    def test_no_args_shows_usage(self, _mock_send):
        _run(dev_mod.cmd_review("chat1", ""))
        assert any("Usage" in m for m in _mock_send)

    def test_with_target_calls_review(self, _mock_send):
        mock_result = MagicMock()
        mock_result.summary = "Looks good"
        mock_result.details = ["No issues found"]
        mock_result.evidence = []

        with patch("developer_skills.review.review", return_value=mock_result):
            _run(dev_mod.cmd_review("chat1", "backends.py"))

        assert any("Review" in m for m in _mock_send)


# ── /ship ─────────────────────────────────────────────────────────────────────

class TestCmdShip:
    def test_ship_calls_with_message(self, _mock_send):
        mock_result = MagicMock()
        mock_result.summary = "Shipped"
        mock_result.details = ["Committed 3 files"]
        mock_result.evidence = ["commit_ok"]

        with patch("developer_skills.ship.ship", return_value=mock_result):
            _run(dev_mod.cmd_ship("chat1", "fix routing bug"))

        assert any("Ship" in m for m in _mock_send)

    def test_ship_empty_message(self, _mock_send):
        mock_result = MagicMock()
        mock_result.summary = "Nothing to ship"
        mock_result.details = []
        mock_result.evidence = []

        with patch("developer_skills.ship.ship", return_value=mock_result):
            _run(dev_mod.cmd_ship("chat1", ""))

        assert len(_mock_send) > 0


# ── /learn (via telegram_knowledge) ──────────────────────────────────────────

class TestCmdLearn:
    def test_learn_empty_shows_usage(self, _mock_send):
        """Empty /learn shows candidate list or usage."""
        import routes.telegram_knowledge as kn_mod
        monkeypatch_send = MagicMock()
        # telegram_knowledge uses its own telegram_bot import
        # patch send_message on the knowledge module
        kn_mod.telegram_bot.send_message = AsyncMock(
            side_effect=lambda text, **kw: _mock_send.append(text),
        )
        _run(kn_mod.cmd_learn("chat1", ""))
        assert len(_mock_send) > 0

    def test_learn_approve_candidate(self, _mock_send):
        """Approving a routing_weight candidate records success."""
        import routes.telegram_knowledge as kn_mod
        kn_mod.telegram_bot.send_message = AsyncMock(
            side_effect=lambda text, **kw: _mock_send.append(text),
        )

        mock_candidate = {
            "id": "test-candidate-123",
            "category": "routing_weight",
            "summary": "Boost scnet_ds_flash:coding: 5/5 ok",
            "status": "proposed",
        }

        with (
            patch("session_memory.shadow_mode.list_candidates", return_value=[mock_candidate]),
            patch("session_memory.shadow_mode.update_candidate"),
            patch("session_memory.outcome_ledger.mark_learned"),
            patch("session_memory.outcome_ledger.query", return_value=[]),
        ):
            _run(kn_mod.cmd_learn("chat1", "approve test-candidate-123"))

        assert any("Approved" in m or "Boosted" in m for m in _mock_send)


from unittest.mock import patch
