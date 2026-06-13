import server
from chat_models import ChatRequest, Message, extract_system_prompt


def test_server_reexports_chat_models_for_compatibility():
    assert server.Message is Message
    assert server.ChatRequest is ChatRequest


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
