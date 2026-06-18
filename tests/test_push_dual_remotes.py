import pytest

from scripts.push_dual_remotes import _gitee_https_push_url, _gitee_token


def test_gitee_https_push_url_from_ssh():
    assert (
        _gitee_https_push_url("git@gitee.com:zhuguang-ZFG/QWEN3.0.git", "tok123")
        == "https://oauth2:tok123@gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_gitee_https_push_url_from_https_without_credentials():
    assert (
        _gitee_https_push_url("https://gitee.com/zhuguang-ZFG/QWEN3.0.git", "tok123")
        == "https://oauth2:tok123@gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_gitee_https_push_url_from_https_with_existing_credentials():
    assert (
        _gitee_https_push_url(
            "https://user:oldpass@gitee.com/zhuguang-ZFG/QWEN3.0.git",
            "tok123",
        )
        == "https://oauth2:tok123@gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_gitee_https_push_url_non_gitee_returns_empty():
    assert _gitee_https_push_url("git@github.com:foo/bar.git", "tok123") == ""


def test_gitee_token_prefers_gitee_token(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "abc")
    monkeypatch.setenv("GITEE_ACCESS_TOKEN", "def")
    assert _gitee_token() == "abc"


def test_gitee_token_falls_back_to_access_token(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.setenv("GITEE_ACCESS_TOKEN", "def")
    assert _gitee_token() == "def"


def test_gitee_token_empty_when_unset(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.delenv("GITEE_ACCESS_TOKEN", raising=False)
    assert _gitee_token() == ""
