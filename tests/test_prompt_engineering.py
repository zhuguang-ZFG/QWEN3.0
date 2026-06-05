from prompt_engineering.layers import (
    build_role_layer,
    build_skill_layer,
    build_quality_gate,
    compose_system_prompt,
)


def test_build_role_layer_coding_without_ide():
    role = build_role_layer("", "coding")
    assert "编程助手" in role
    assert "理解需求" in role
    assert "IDE" not in role


def test_build_role_layer_coding_with_ide():
    role = build_role_layer("OpenCode", "coding")
    assert "编程助手" in role
    assert "OpenCode" in role
    assert "文件读写" in role
    assert "无法访问本地文件" in role


def test_build_role_layer_chat():
    role = build_role_layer("", "chat")
    assert "联网能力" in role


def test_build_role_layer_vision():
    role = build_role_layer("", "vision")
    assert "多模态" in role


def test_build_role_layer_unknown_scenario_falls_back_to_chat():
    role = build_role_layer("", "unknown_scenario")
    assert "联网能力" in role


def test_build_skill_layer_coding():
    skill = build_skill_layer("coding")
    assert "编码实现" in skill
    assert "触发条件" in skill
    assert "执行流程" in skill
    assert "验证方式" in skill


def test_build_skill_layer_chat():
    skill = build_skill_layer("chat")
    assert "技术问答" in skill
    assert "直接答案" in skill


def test_build_quality_gate_coding():
    gate = build_quality_gate("coding")
    assert "语法正确" in gate
    assert "类型注解" in gate
    assert "linter" in gate


def test_build_quality_gate_chat():
    gate = build_quality_gate("chat")
    assert "准确" in gate
    assert "不编造" in gate


def test_build_quality_gate_vision():
    gate = build_quality_gate("vision")
    assert "图像实际内容" in gate


def test_compose_system_prompt_coding_with_ide_and_context():
    prompt = compose_system_prompt(
        ide="OpenCode",
        scenario="coding",
        code_context="routing_engine.py | select, classify",
    )
    assert "编程助手" in prompt
    assert "OpenCode" in prompt
    assert "编码实现" in prompt
    assert "routing_engine.py" in prompt
    assert "质量门控" in prompt
    assert "linter" in prompt


def test_compose_system_prompt_chat_no_context():
    prompt = compose_system_prompt(ide="", scenario="chat", code_context="")
    assert "联网能力" in prompt
    assert "技术问答" in prompt
    assert "质量门控" in prompt
    assert "[上下文]" not in prompt


def test_compose_system_prompt_has_all_four_layers():
    prompt = compose_system_prompt(
        ide="OpenCode", scenario="coding", code_context="server.py | embeddings"
    )
    layers_found = 0
    if "编程助手" in prompt:
        layers_found += 1
    if "编码实现" in prompt:
        layers_found += 1
    if "[上下文]" in prompt:
        layers_found += 1
    if "[质量门控]" in prompt:
        layers_found += 1
    assert layers_found == 4
