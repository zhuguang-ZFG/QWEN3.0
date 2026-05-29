from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture
def telegram_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "hook-secret")


def test_webhook_rejects_missing_secret(telegram_env):
    client = TestClient(server.app)
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}})
    assert response.status_code == 403


def test_webhook_rejects_wrong_secret(telegram_env):
    client = TestClient(server.app)
    response = client.post(
        "/telegram/webhook",
        json={"message": {"text": "/start"}},
        headers={"x-telegram-bot-api-secret-token": "wrong"},
    )
    assert response.status_code == 403


def test_webhook_requires_secret_when_bot_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    client = TestClient(server.app)
    response = client.post(
        "/telegram/webhook",
        json={"message": {"text": "/start"}},
        headers={"x-telegram-bot-api-secret-token": "anything"},
    )
    assert response.status_code == 503


def test_webhook_accepts_valid_secret(telegram_env):
    client = TestClient(server.app)
    with patch("routes.telegram._dispatch_command_lines", new_callable=AsyncMock) as dispatch:
        response = client.post(
            "/telegram/webhook",
            json={
                "message": {
                    "text": "/status",
                    "chat": {"id": 987654321},
                }
            },
            headers={"x-telegram-bot-api-secret-token": "hook-secret"},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    dispatch.assert_awaited_once()


def test_webhook_multiline_commands(telegram_env):
    client = TestClient(server.app)
    with patch("routes.telegram._dispatch_command", new_callable=AsyncMock) as dispatch:
        response = client.post(
            "/telegram/webhook",
            json={
                "message": {
                    "text": "/github psf/requests README.md main\n/device status",
                    "chat": {"id": 987654321},
                }
            },
            headers={"x-telegram-bot-api-secret-token": "hook-secret"},
        )
    assert response.status_code == 200
    assert dispatch.await_count == 2
    dispatch.assert_any_await("987654321", "/github psf/requests README.md main")
    dispatch.assert_any_await("987654321", "/device status")


def test_parse_github_args_ignores_extra_lines():
    from telegram_operator_tools import parse_github_args

    assert parse_github_args("psf/requests README.md main\n/device status") == (
        "psf/requests",
        "README.md",
        "main",
    )


def test_review_callback_notice_maps_duplicate_review_to_friendly_text():
    from routes.telegram import _review_callback_notice

    assert _review_callback_notice(200, "abc123", "approved") == "Task abc123 approved"
    assert _review_callback_notice(409, "abc123", "approved") == (
        "Task abc123 已审批，无需重复操作"
    )
    assert _review_callback_notice(500, "abc123", "rejected") == "Review failed: 500"


def test_webhook_skips_auth_when_bot_not_configured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    client = TestClient(server.app)
    response = client.post("/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 200
