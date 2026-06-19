"""get_injected_ids helper tests."""

from routing_engine_post import get_injected_ids


def testget_injected_ids_helper_basic():
    """测试 get_injected_ids helper 的基本功能

    验证 get_injected_ids 函数正确处理基本的情况
    """
    original = [{"role": "user", "content": "test"}]
    modified = [
        {"role": "user", "content": "test"},
        {"role": "system", "content": "Available skills: skill1, skill2"},
        {"role": "assistant", "content": "test"},
    ]

    result = get_injected_ids(original, modified)

    assert result == ["dir:skill1", "dir:skill2"]


def testget_injected_ids_helper_no_skills():
    """测试 get_injected_ids helper 的无技能情况

    验证 get_injected_ids 函数当没有找到技能时返回空列表
    """
    original = [{"role": "user", "content": "test"}]
    modified = [{"role": "user", "content": "test"}]

    result = get_injected_ids(original, modified)

    assert result == []


def testget_injected_ids_helper_injected_skills():
    """测试 get_injected_ids helper 的注入技能情况

    验证 get_injected_ids 函数当有注入的技能时返回正确的ID
    """
    original = [{"role": "user", "content": "test"}]
    modified = [
        {"role": "user", "content": "test"},
        {"role": "system", "content": "Available skills: skill1"},
    ]

    result = get_injected_ids(original, modified)

    assert result == ["dir:skill1"]


def testget_injected_ids_helper_with_unicode_skills():
    """测试 get_injected_ids helper 的 Unicode 技能名称

    验证 get_injected_ids 函数可以正确处理 Unicode 编码的技能名称
    """
    original = [{"role": "user", "content": "test"}]
    modified = [
        {"role": "user", "content": "test"},
        {"role": "system", "content": "Available skills: skill_1, skill_2, skill_3"},
    ]

    result = get_injected_ids(original, modified)

    assert result == ["dir:skill_1", "dir:skill_2", "dir:skill_3"]


def testget_injected_ids_helper_mixed_roles():
    """测试 get_injected_ids helper 的混合角色消息

    验证 get_injected_ids 函数可以正确处理包含多种角色的消息
    """
    original = [
        {"role": "system", "content": "initial system"},
        {"role": "user", "content": "user message"},
    ]
    modified = [
        {"role": "system", "content": "initial system"},
        {"role": "user", "content": "user message"},
        {"role": "system", "content": "Available skills: tool_a, tool_b"},
        {"role": "assistant", "content": "assistant message"},
    ]

    result = get_injected_ids(original, modified)

    assert result == ["dir:tool_a", "dir:tool_b"]


def testget_injected_ids_helper_single_skill():
    """测试 get_injected_ids helper 单个技能的情况

    验证 get_injected_ids 函数可以正确处理只有单个技能的情况
    """
    original = [{"role": "user", "content": "test"}]
    modified = [
        {"role": "user", "content": "test"},
        {"role": "system", "content": "Available skills: single_skill"},
    ]

    result = get_injected_ids(original, modified)

    assert result == ["dir:single_skill"]
