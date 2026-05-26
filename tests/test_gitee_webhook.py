"""Tests for Gitee webhook verify, format, dedupe, and HTTP route."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import server
from gitee_webhook.dedupe import record_push_shas, reset_dedupe_for_tests, should_skip_gitee_push
from gitee_webhook.format import extract_push_shas, format_gitee_event
from gitee_webhook.verify import verify_gitee_request, verify_gitee_sign, verify_gitee_token


@pytest.fixture(autouse=True)
def _clean_dedupe(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    reset_dedupe_for_tests()
    yield
    reset_dedupe_for_tests()


def test_format_push_event():
    payload = {
        "hook_name": "push_hooks",
        "repository": {"path_with_namespace": "zhuguang-cn/QWEN3.0"},
        "ref": "refs/heads/main",
        "commits": [{"id": "abc1234567890abcdef1234567890abcdef1234"}],
        "sender": {"username": "owner"},
    }
    text = format_gitee_event("Push Hook", payload)
    assert "Gitee push" in text
    assert "QWEN3.0" in text
    assert "abc1234" in text


def test_format_merge_request():
    payload = {
        "hook_name": "merge_request_hooks",
        "repository": {"path_with_namespace": "zhuguang-cn/QWEN3.0"},
        "pull_request": {
            "number": 3,
            "title": "Fix mirror",
            "state": "open",
            "head": {"ref": "dev"},
            "base": {"ref": "main"},
        },
    }
    text = format_gitee_event("Merge Request Hook", payload)
    assert "#3" in text
    assert "Fix mirror" in text


def test_verify_password_token():
    payload = {"password": "gitee-secret"}
    assert verify_gitee_request(token_header="gitee-secret", payload=payload, secret="gitee-secret")


def test_verify_sign_timestamp():
    secret = "gitee-secret"
    timestamp = "1576754827988"
    digest = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).digest()
    sign = base64.b64encode(digest).decode()
    assert verify_gitee_sign(timestamp, sign, secret)


def test_dedupe_skips_gitee_after_github():
    sha = "abc1234567890abcdef1234567890abcdef1234"
    record_push_shas([sha], source="github")
    assert should_skip_gitee_push([sha]) is True
    assert should_skip_gitee_push(["def4567890abcdef1234567890abcdef12345678"]) is False


@pytest.fixture
def gitee_env(monkeypatch):
    monkeypatch.setenv("GITEE_WEBHOOK_ENABLED", "1")
    monkeypatch.setenv("GITEE_WEBHOOK_SECRET", "gitee-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")


def test_gitee_webhook_disabled_returns_503(monkeypatch):
    monkeypatch.delenv("GITEE_WEBHOOK_ENABLED", raising=False)
    client = TestClient(server.app)
    response = client.post("/gitee/webhook", content=b"{}")
    assert response.status_code == 503


def test_gitee_webhook_rejects_bad_token(gitee_env):
    client = TestClient(server.app)
    body = json.dumps({"hook_name": "push_hooks", "password": "wrong"}).encode()
    response = client.post(
        "/gitee/webhook",
        content=body,
        headers={
            "X-Gitee-Token": "wrong",
            "X-Gitee-Event": "Push Hook",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403


def test_gitee_webhook_accepts_push_and_notifies(gitee_env):
    client = TestClient(server.app)
    payload = {
        "hook_name": "push_hooks",
        "password": "gitee-secret",
        "repository": {"path_with_namespace": "zhuguang-cn/QWEN3.0"},
        "ref": "refs/heads/main",
        "commits": [{"id": "abc1234567890abcdef1234567890abcdef1234"}],
        "sender": {"username": "owner"},
    }
    body = json.dumps(payload).encode()
    with patch("telegram_notify.notify_gitee_event") as notify:
        response = client.post(
            "/gitee/webhook",
            content=body,
            headers={
                "X-Gitee-Token": "gitee-secret",
                "X-Gitee-Event": "Push Hook",
            },
        )
    assert response.status_code == 200
    notify.assert_called_once()
    assert "QWEN3.0" in notify.call_args.args[0]


def test_gitee_webhook_dedupes_github_push(gitee_env):
    sha = "deadbeef1234567890deadbeef1234567890dead"
    record_push_shas([sha], source="github")
    client = TestClient(server.app)
    payload = {
        "hook_name": "push_hooks",
        "password": "gitee-secret",
        "repository": {"path_with_namespace": "zhuguang-cn/QWEN3.0"},
        "ref": "refs/heads/main",
        "after": sha,
        "commits": [{"id": sha}],
        "sender": {"username": "owner"},
    }
    body = json.dumps(payload).encode()
    with patch("telegram_notify.notify_gitee_event") as notify:
        response = client.post(
            "/gitee/webhook",
            content=body,
            headers={"X-Gitee-Token": "gitee-secret", "X-Gitee-Event": "Push Hook"},
        )
    assert response.json().get("deduped") is True
    notify.assert_not_called()


def test_extract_push_shas():
    shas = extract_push_shas({"after": "abc123", "commits": [{"id": "def456"}]})
    assert shas == ["abc123", "def456"]
