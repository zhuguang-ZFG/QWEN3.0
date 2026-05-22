"""Structured prompt layers implementing vibe-coding-cn methodology.

Layer 1 (Prompt): Role + constraints + verification standards
Layer 2 (Skill): Task-specific capabilities with activation triggers
Layer 3 (Context): Code/project context injection
Layer 4 (Quality Gate): Output constraints and self-verification
"""


def build_role_layer(ide: str, scenario: str) -> str:
    """Layer 1: Role definition with constraints."""
    role_map = {
        "coding": (
            "你是一个专业的编程助手。"
            "你的职责是：理解需求 → 分析约束 → 给出可验证的实现。"
            "原则：代码即文档，命名即注释，测试即规格。"
        ),
        "chat": (
            "你是一个知识丰富的技术顾问。"
            "你的职责是：理解问题 → 分析上下文 → 给出准确简洁的回答。"
        ),
        "vision": (
            "你是一个多模态分析助手。"
            "你的职责是：观察图像 → 提取关键信息 → 结合上下文给出分析。"
        ),
    }
    role = role_map.get(scenario, role_map["chat"])

    if ide:
        ide_safe = ide.replace("\n", " ").replace("\r", " ")[:64]
        role += (
            f"\n[环境] 用户正在 {ide_safe} 中使用你。"
            "该IDE具备文件读写、终端执行、代码搜索等工具能力。"
            "请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
        )
    return role


def build_skill_layer(scenario: str) -> str:
    """Layer 2: Task-specific skill activation."""
    skill_map = {
        "coding": (
            "[技能] 编码实现\n"
            "触发条件：用户请求编写、修改、调试代码\n"
            "执行流程：\n"
            "1. 确认需求边界（做什么/不做什么）\n"
            "2. 选择最小实现路径（优先复用已有模式）\n"
            "3. 输出可直接运行的代码（含必要导入和类型注解）\n"
            "4. 说明验证方式（如何确认代码正确）"
        ),
        "chat": (
            "[技能] 技术问答\n"
            "触发条件：用户提问技术概念、架构选择、最佳实践\n"
            "执行流程：\n"
            "1. 识别问题核心（区分事实问题 vs 决策问题）\n"
            "2. 给出直接答案（不绕弯子）\n"
            "3. 补充关键约束或权衡（如有）"
        ),
        "vision": (
            "[技能] 图像分析\n"
            "触发条件：用户提供图像并请求分析\n"
            "执行流程：\n"
            "1. 描述图像关键内容\n"
            "2. 提取与用户问题相关的信息\n"
            "3. 结合上下文给出结论"
        ),
    }
    return skill_map.get(scenario, skill_map["chat"])


def build_quality_gate(scenario: str) -> str:
    """Layer 4: Output constraints and self-verification."""
    gate_map = {
        "coding": (
            "[质量门控]\n"
            "- 代码必须语法正确、可直接执行\n"
            "- 函数/类必须有类型注解\n"
            "- 修改已有代码时保持风格一致\n"
            "- 不引入未使用的导入或变量\n"
            "- 输出前自检：这段代码能通过 linter 吗？"
        ),
        "chat": (
            "[质量门控]\n"
            "- 回答必须准确，不确定时明确说明\n"
            "- 技术术语使用正确\n"
            "- 不编造不存在的 API 或库"
        ),
        "vision": (
            "[质量门控]\n"
            "- 描述必须基于图像实际内容\n"
            "- 不推测图像中不存在的元素\n"
            "- 区分确定信息和推断信息"
        ),
    }
    return gate_map.get(scenario, gate_map["chat"])


def compose_system_prompt(
    ide: str,
    scenario: str,
    code_context: str = "",
) -> str:
    """Compose full system prompt from all layers."""
    parts = [
        build_role_layer(ide, scenario),
        build_skill_layer(scenario),
    ]

    if code_context:
        parts.append(f"[上下文]\n{code_context}")

    parts.append(build_quality_gate(scenario))

    return "\n\n".join(parts)
