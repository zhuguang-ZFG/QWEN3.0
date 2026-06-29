"""Unit tests for the promptfoo custom provider.

These mirror the promptfoo assertions in promptfooconfig.yaml so the same
regressions are caught by the normal pytest suite.
"""

from __future__ import annotations

import pytest

from tests.promptfoo.prompt_provider import call_api


@pytest.mark.parametrize(
    "scenario",
    ["chat", "coding", "vision", "device_draw", "device_write", "device_control"],
)
def test_compose_system_prompt_excludes_version_marker(scenario):
    result = call_api(f"scenario={scenario}\nide=", {}, {})
    assert f"<!-- lima-prompts-v2.0.{scenario} -->" not in result["output"]


def test_chat_prompt_contains_skill_and_safety():
    result = call_api("scenario=chat\nide=", {}, {})
    output = result["output"]
    assert "技术问答" in output
    assert "安全基线" in output


def test_coding_prompt_contains_coding_skill():
    result = call_api("scenario=coding\nide=", {}, {})
    assert "编码实现" in result["output"]


def test_device_control_prompt_contains_whitelist():
    result = call_api("scenario=device_control\nide=", {}, {})
    output = result["output"]
    assert "设备控制" in output
    assert "白名单" in output


def test_ide_suffix_includes_environment_note():
    result = call_api("scenario=chat\nide=vscode", {}, {})
    assert "用户正在 vscode 中使用你" in result["output"]
