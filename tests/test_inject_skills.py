"""inject_skills tests."""

from unittest.mock import MagicMock, patch

from routing_engine import inject_skills


def test_inject_skills_with_mock_skills_injector():
    """测试 inject_skills 与 mock skills_injector 的集成

    验证 inject_skills 函数正确地调用 skills_mod.apply_skills
    并处理传递的参数
    """
    with patch("routing_engine.skills_mod") as mock_skills_mod:
        mock_skills_mod.apply_skills.return_value = [
            {"role": "system", "content": "test system"},
            {"role": "user", "content": "test user"},
        ]

        result = inject_skills(
            messages=[{"role": "user", "content": "test"}],
            backend="test_backend",
            ide_source="test_ide",
            system_prompt="test system prompt",
        )

        mock_skills_mod.apply_skills.assert_called_once_with(
            backend="test_backend",
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test system prompt",
            ide_source="test_ide",
            intent="",
            route_role="",
            scenario="",
        )

        assert len(result) == 2
        assert result[0]["role"] == "system"


def test_inject_skills_empty_messages():
    """测试 inject_skills 空消息列表的情况

    验证 inject_skills 函数可以正确处理空消息列表
    """
    mock_skills_mod = MagicMock()
    mock_skills_mod.apply_skills.return_value = []

    with patch("routing_engine.skills_mod", mock_skills_mod):
        result = inject_skills(
            messages=[],
            backend="test_backend",
            ide_source="test_ide",
            system_prompt="test system prompt",
        )

    assert result == []
