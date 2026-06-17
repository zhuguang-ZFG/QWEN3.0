"""Prompt adapter — adjusts prompt injection based on user expertise level."""

from user_identity.profile import UserProfile


def adapt_prompt_for_user(system_prompt: str, profile: UserProfile) -> str:
    """Adapt system prompt based on user's tech level and preferences."""
    if not profile or not profile.tech_level:
        return system_prompt

    if profile.tech_level == "senior":
        system_prompt += (
            "\n\n[用户画像] 高级开发者。"
            "回答简洁直接，不解释基础概念。"
            "优先给出代码，减少文字说明。"
            "可以使用高级术语和设计模式名称。"
        )
    elif profile.tech_level == "beginner":
        system_prompt += (
            "\n\n[用户画像] 初学者。"
            "回答时解释关键术语和概念。"
            "代码附带注释说明每一步的作用。"
            "避免使用未解释的缩写或高级模式。"
        )

    if profile.languages:
        langs = ", ".join(profile.languages[:3])
        system_prompt += f"\n用户熟悉的语言: {langs}"

    if profile.ide_preference:
        system_prompt += f"\n用户偏好 IDE: {profile.ide_preference}"

    return system_prompt


def infer_tech_level(messages: list[dict]) -> str:
    """Infer user's tech level from message patterns."""
    if not messages:
        return "intermediate"

    user_text = ""
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            user_text += msg["content"] + " "

    if not user_text:
        return "intermediate"

    senior_signals = [
        "refactor",
        "architecture",
        "concurrency",
        "mutex",
        "async/await",
        "type annotation",
        "generics",
        "decorator",
        "middleware",
        "pipeline",
        "dependency injection",
    ]
    beginner_signals = [
        "what is",
        "how to",
        "explain",
        "tutorial",
        "什么是",
        "怎么",
        "如何",
        "教程",
        "入门",
    ]

    text_lower = user_text.lower()
    senior_count = sum(1 for s in senior_signals if s in text_lower)
    beginner_count = sum(1 for s in beginner_signals if s in text_lower)

    if senior_count >= 2:
        return "senior"
    if beginner_count >= 2:
        return "beginner"
    return "intermediate"
