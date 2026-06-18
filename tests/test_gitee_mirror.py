import os

import pytest

from gitee_mirror import (
    build_gitee_https_push_url,
    build_gitee_oauth_push_url,
    gitee_credential_store,
    gitee_env_token,
)


def test_gitee_env_token_prefers_gitee_token(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "abc")
    monkeypatch.setenv("GITEE_ACCESS_TOKEN", "def")
    assert gitee_env_token() == "abc"


def test_gitee_env_token_falls_back_to_access_token(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.setenv("GITEE_ACCESS_TOKEN", "def")
    assert gitee_env_token() == "def"


def test_gitee_env_token_whitespace_only_falls_back(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "   ")
    monkeypatch.setenv("GITEE_ACCESS_TOKEN", "def")
    assert gitee_env_token() == "def"


def test_gitee_env_token_empty_when_unset(monkeypatch):
    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    monkeypatch.delenv("GITEE_ACCESS_TOKEN", raising=False)
    assert gitee_env_token() == ""


def test_build_gitee_oauth_push_url_from_ssh():
    assert (
        build_gitee_oauth_push_url("git@gitee.com:zhuguang-ZFG/QWEN3.0.git", "tok123")
        == "https://oauth2:tok123@gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_build_gitee_oauth_push_url_urlencodes_token():
    assert (
        build_gitee_oauth_push_url("git@gitee.com:u/r.git", "tok@en")
        == "https://oauth2:tok%40en@gitee.com/u/r.git"
    )


def test_build_gitee_oauth_push_url_from_https():
    assert (
        build_gitee_oauth_push_url("https://gitee.com/zhuguang-ZFG/QWEN3.0.git", "tok")
        == "https://oauth2:tok@gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_build_gitee_oauth_push_url_from_https_with_credentials():
    assert (
        build_gitee_oauth_push_url(
            "https://user:oldpass@gitee.com/u/r.git",
            "tok",
        )
        == "https://oauth2:tok@gitee.com/u/r.git"
    )


def test_build_gitee_oauth_push_url_from_ssh_scheme():
    assert (
        build_gitee_oauth_push_url("ssh://git@gitee.com/u/r.git", "tok")
        == "https://oauth2:tok@gitee.com/u/r.git"
    )


def test_build_gitee_https_push_url_tokenless():
    assert (
        build_gitee_https_push_url("git@gitee.com:zhuguang-ZFG/QWEN3.0.git")
        == "https://gitee.com/zhuguang-ZFG/QWEN3.0.git"
    )


def test_build_gitee_https_push_url_rejects_non_gitee():
    with pytest.raises(ValueError):
        build_gitee_https_push_url("git@github.com:foo/bar.git")


def test_build_gitee_oauth_push_url_rejects_non_gitee():
    with pytest.raises(ValueError):
        build_gitee_oauth_push_url("git@github.com:foo/bar.git", "tok")


def test_gitee_credential_store_creates_and_removes_file():
    with gitee_credential_store("secret") as path:
        assert path.exists()
        assert "oauth2:secret@gitee.com" in path.read_text()
        if os.name != "nt":
            assert path.stat().st_mode & 0o777 == 0o600
    assert not path.exists()
