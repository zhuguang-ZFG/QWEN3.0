"""Tests for Gitee search gateway tools."""

from __future__ import annotations

from unittest.mock import patch

from search_gateway.gitee_tools import (
    credentials_configured,
    fetch_repo_file,
    search_gitee,
    search_repositories,
)


def test_credentials_configured_false(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.delenv("GITEE_ACCESS_TOKEN", raising=False)
    import search_gateway.gitee_tools as gt

    gt._git_remote_token = ""
    monkeypatch.setattr(gt, "gitee_token_from_git_remotes", lambda *a, **k: "")
    assert credentials_configured() is False


def test_credentials_configured_from_git_remote(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.delenv("GITEE_ACCESS_TOKEN", raising=False)
    import search_gateway.gitee_tools as gt

    gt._git_remote_token = None
    monkeypatch.setattr(gt, "gitee_token_from_git_remotes", lambda *a, **k: "remote-token")
    assert credentials_configured() is True


def test_search_gitee_skips_without_token(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.delenv("GITEE_ACCESS_TOKEN", raising=False)
    import search_gateway.gitee_tools as gt

    gt._git_remote_token = ""
    monkeypatch.setattr(gt, "gitee_token_from_git_remotes", lambda *a, **k: "")
    out = search_gitee("routing_engine")
    assert out["ok"] is False
    assert out.get("skipped") is True


def test_search_repositories_normalizes(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "test-token")

    def fake_request(path, params=None):
        assert path == "/search/repositories"
        return [{"full_name": "zhuguang-cn/QWEN3.0", "html_url": "https://gitee.com/x", "description": "LiMa"}]

    with patch("search_gateway.gitee_tools._request_json", side_effect=fake_request):
        out = search_repositories("lima")
    assert out["ok"] is True
    assert out["results"][0]["repo"] == "zhuguang-cn/QWEN3.0"


def test_search_gitee_merges_repo_and_issue(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "test-token")

    def fake_repo(q, max_results=5, owner=None):
        return {"ok": True, "results": [{"title": "repo", "url": "u", "snippet": "s", "source": "gitee_repo", "repo": "a/b"}]}

    def fake_issue(q, repo=None, max_results=5):
        return {"ok": True, "results": [{"title": "issue", "url": "u2", "snippet": "s2", "source": "gitee_issue", "repo": repo or ""}]}

    with patch("search_gateway.gitee_tools.search_repositories", side_effect=fake_repo):
        with patch("search_gateway.gitee_tools.search_issues", side_effect=fake_issue):
            out = search_gitee("routing")
    assert out["ok"] is True
    assert len(out["results"]) == 2


def test_fetch_repo_file_decodes_base64(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "test-token")
    import base64

    payload = {"content": base64.b64encode(b"hello gitee").decode("ascii")}

    with patch("search_gateway.gitee_tools._request_json", return_value=payload):
        out = fetch_repo_file("zhuguang-cn/QWEN3.0", "README.md")
    assert out["ok"] is True
    assert out["text"] == "hello gitee"
