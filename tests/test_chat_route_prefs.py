from chat_models import ChatRequest
from routes.chat_handler_dispatch import resolve_route_prefs


def _request(model: str) -> ChatRequest:
    return ChatRequest(model=model, messages=[{"role": "user", "content": "write code"}])


def test_code_model_uses_coding_route_preference():
    prefs = resolve_route_prefs(_request("code"), ide_source="", query="write code")

    assert prefs.ide_source == "chat_code_mode"
    assert prefs.prefer == "scnet_qwen235b"


def test_retired_lima_code_alias_no_longer_uses_coding_preference():
    prefs = resolve_route_prefs(_request("lima-code"), ide_source="", query="write code")

    assert prefs.ide_source == ""
    assert prefs.prefer is None
