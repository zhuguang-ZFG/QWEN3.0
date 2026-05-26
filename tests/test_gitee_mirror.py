"""Tests for gitee_mirror (GI-G-0 / GI-G-1)."""

from __future__ import annotations

import subprocess

import gitee_mirror as gm


def test_redact_oauth_remote_url():
    url = "https://oauth2:secret-token@gitee.com/owner/repo.git"
    assert gm.redact_remote_url(url) == "https://oauth2:***@gitee.com/owner/repo.git"


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
