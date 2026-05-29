"""Tests for gitee_mirror (GI-G-0 / GI-G-1)."""

from __future__ import annotations

import subprocess

import gitee_mirror as gm


def test_redact_oauth_remote_url():
    url = "https://oauth2:secret-token@gitee.com/owner/repo.git"
    assert gm.redact_remote_url(url) == "https://oauth2:***@gitee.com/owner/repo.git"


def test_extract_gitee_oauth_token():
    url = "https://oauth2:my-private-token@gitee.com/owner/repo.git"
    assert gm.extract_gitee_oauth_token(url) == "my-private-token"
    assert gm.extract_gitee_oauth_token("https://gitee.com/owner/repo.git") == ""


def test_gitee_token_from_git_remotes():
    remote_v = (
        "origin\thttps://github.com/o/r.git (push)\n"
        "origin\thttps://oauth2:abc123@gitee.com/o/r.git (push)\n"
    )

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=remote_v, stderr="")

    assert gm.gitee_token_from_git_remotes(runner=runner) == "abc123"


def test_parse_git_remotes():
    output = """
origin\thttps://github.com/owner/repo.git (fetch)
origin\thttps://github.com/owner/repo.git (push)
gitee\thttps://gitee.com/owner/repo.git (fetch)
gitee\thttps://gitee.com/owner/repo.git (push)
""".strip()
    remotes = gm.parse_git_remotes(output)
    assert remotes["origin"]["fetch"].startswith("https://github.com")
    assert remotes["gitee"]["push"].startswith("https://gitee.com")


def test_mirror_status_from_output():
    output = (
        "origin\thttps://github.com/zhuguang-ZFG/QWEN3.0.git (fetch)\n"
        "origin\thttps://github.com/zhuguang-ZFG/QWEN3.0.git (push)\n"
        "gitee\thttps://gitee.com/zhuguang-cn/QWEN3.0.git (push)\n"
    )
    status = gm.mirror_status_from_output(output)
    assert status["has_github"] is True
    assert status["has_gitee"] is True
    assert "secret" not in str(status).lower()


def test_default_push_remotes_order():
    entries = gm.build_remote_entries(
        {
            "gitee": {"push": "https://gitee.com/x/y.git"},
            "origin": {"push": "https://github.com/x/y.git"},
        }
    )
    assert gm.default_push_remotes(entries) == ["origin", "gitee"]


def test_collect_mirror_status_uses_runner():
    def fake_run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, stdout="origin\thttps://github.com/a/b.git (push)\n", stderr="")

    status = gm.collect_mirror_status(runner=fake_run)
    assert status["ok"] is True
    assert status["has_github"] is True


def test_gitee_mirror_status_script_json():
    import json
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/gitee_mirror_status.py", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    assert "remotes" in data


def test_compare_mirror_heads_dual_push_origin():
    """origin fetch=GitHub + second push=Gitee must still find both hosts."""
    remote_v = (
        "origin\thttps://github.com/o/r.git (fetch)\n"
        "origin\thttps://github.com/o/r.git (push)\n"
        "origin\thttps://gitee.com/o/r.git (push)\n"
        "gitee\thttps://gitee.com/o/r.git (push)\n"
    )

    def runner(cmd, **kwargs):
        if len(cmd) >= 4 and cmd[0] == "git" and cmd[-2:] == ["remote", "-v"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=remote_v, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="abc123 refs/heads/main\n", stderr="")

    result = gm.compare_mirror_heads(".", "main", runner=runner)
    assert result["ok"] is True
    assert result["in_sync"] is True
