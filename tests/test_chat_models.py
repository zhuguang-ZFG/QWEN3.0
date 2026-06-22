from chat_models import ChatRequest, Message, extract_system_prompt


def test_chat_models_exports_message_and_chat_request():
    assert Message is not None
    assert ChatRequest is not None


def test_extract_system_prompt_returns_first_non_empty_system_message():
    messages = [
        Message(role="user", content="hello"),
        Message(role="system", content="base system"),
        Message(role="system", content="later system"),
    ]

    assert extract_system_prompt(messages) == "base system"


def test_extract_system_prompt_returns_none_without_system_content():
    messages = [
        Message(role="system", content=""),
        Message(role="user", content="hello"),
    ]

    assert extract_system_prompt(messages) is None
