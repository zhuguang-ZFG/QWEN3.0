"""Tests for GitHub webhook verify, format, and HTTP route."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import server
from github_webhook.format import format_github_event
from github_webhook.verify import verify_github_signature


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# --- format ---


def test_format_push_event():
    payload = {
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
        "ref": "refs/heads/main",
        "pusher": {"name": "owner"},
        "commits": [{"id": "abc1234567890"}],
    }
    text = format_github_event("push", payload)
    assert "QWEN3.0" in text
    assert "main" in text
    assert "abc1234" in text
    assert "owner" in text


def test_format_pull_request_opened():
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "title": "Fix routing",
            "head": {"ref": "feature/x"},
            "base": {"ref": "main"},
        },
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
    }
    text = format_github_event("pull_request", payload)
    assert "#42" in text
    assert "Fix routing" in text
    assert "opened" in text


def test_format_workflow_run_failed():
    payload = {
        "action": "completed",
        "workflow_run": {
            "name": "pytest",
            "conclusion": "failure",
            "head_branch": "main",
            "html_url": "https://github.com/o/r/actions/runs/1",
        },
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
    }
    text = format_github_event("check_run", payload)
    assert text is None  # unsupported event type at format layer uses event name


def test_format_workflow_run_event_name():
    payload = {
        "action": "completed",
        "workflow_run": {
            "name": "pytest",
            "conclusion": "failure",
            "head_branch": "main",
        },
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
    }
    text = format_github_event("workflow_run", payload)
    assert "pytest" in text
    assert "failure" in text
    assert "main" in text


def test_format_unknown_event_returns_none():
    assert format_github_event("ping", {"zen": "x"}) is None


# --- verify ---


def test_verify_valid_signature():
    body = b'{"hook":"test"}'
    secret = "my-secret"
    assert verify_github_signature(body, _sign(body, secret), secret) is True


def test_verify_invalid_signature():
    body = b'{"hook":"test"}'
    assert verify_github_signature(body, "sha256=deadbeef", "my-secret") is False


def test_verify_missing_header():
    assert verify_github_signature(b"{}", "", "secret") is False


# --- HTTP route ---


@pytest.fixture
def gh_env(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_ENABLED", "1")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "gh-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")


def test_github_webhook_disabled_returns_503(monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_ENABLED", raising=False)
    client = TestClient(server.app)
    response = client.post("/github/webhook", content=b"{}")
    assert response.status_code == 503


def test_github_webhook_rejects_bad_signature(gh_env):
    client = TestClient(server.app)
    body = json.dumps({"ref": "refs/heads/main"}).encode()
    response = client.post(
        "/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=bad",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403


def test_github_webhook_accepts_push_and_notifies(gh_env):
    client = TestClient(server.app)
    payload = {
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
        "ref": "refs/heads/main",
        "pusher": {"name": "owner"},
        "commits": [{"id": "abc1234567890"}],
    }
    body = json.dumps(payload).encode()
    with patch("telegram_notify.notify_github_event") as notify:
        response = client.post(
            "/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(body, "gh-secret"),
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    notify.assert_called_once()
    assert "QWEN3.0" in notify.call_args.args[0]


def test_github_webhook_repo_allowlist_ignores(gh_env, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_REPOS", "other/repo")
    client = TestClient(server.app)
    payload = {"repository": {"full_name": "zhuguang-ZFG/QWEN3.0"}, "ref": "refs/heads/main", "commits": []}
    body = json.dumps(payload).encode()
    with patch("telegram_notify.notify_github_event") as notify:
        response = client.post(
            "/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(body, "gh-secret"),
            },
        )
    assert response.status_code == 200
    assert response.json().get("ignored") is True
    notify.assert_not_called()
