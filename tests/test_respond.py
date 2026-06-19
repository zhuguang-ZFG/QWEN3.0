"""respond() formatting tests."""

from routing_engine import RouteResult, respond


def test_respond_for_openai_format():
    """测试 respond() 函数的 openai 格式

    验证 respond 函数正确处理 openai 格式的响应
    """
    result = RouteResult(
        backend="openai_backend",
        answer="test answer",
        request_type="chat",
        ms=100,
        skills_injected=["skill1"],
    )

    response = respond(result, fmt="openai")

    assert "id" in response
    assert response["choices"][0]["message"]["content"] == "test answer"
    assert response["model"] == "lima-1.3"
    assert "x_lima_meta" in response
    assert response["x_lima_meta"]["request_type"] == "chat"
    assert response["x_lima_meta"]["skills_injected"] == ["skill1"]


def test_respond_for_anthropic_format():
    """测试 respond() 函数的 anthropic 格式

    验证 respond 函数正确处理 anthropic 格式的响应
    """
    result = RouteResult(backend="anthropic_backend", answer="test answer", request_type="chat")

    response = respond(result, fmt="anthropic", model="anthropic-model")

    assert "id" in response
    assert response["content"][0]["text"] == "test answer"
    assert response["model"] == "anthropic-model"


def test_respond_with_empty_answer():
    """测试 respond() 函数空答案的情况

    验证 respond 函数可以正确处理空答案的情况
    """
    result = RouteResult(backend="test_backend", answer="", request_type="chat", ms=0, skills_injected=[])

    response = respond(result, fmt="openai")

    assert response["choices"][0]["message"]["content"] == ""


def test_respond_with_anthropic_empty_answer():
    """测试 respond() 函数 anthropic 格式空答案的情况

    验证 respond 函数在 anthropic 格式中可以正确处理空答案
    """
    result = RouteResult(backend="test_backend", answer="", request_type="chat")

    response = respond(result, fmt="anthropic")

    assert response["content"][0]["text"] == ""
