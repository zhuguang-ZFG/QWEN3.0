"""RouteResult dataclass tests."""

from routing_engine import RouteResult


def test_route_result_dataclass_creation_and_default_values():
    """测试 RouteResult 数据类创建和默认值

    验证 RouteResult 数据类的默认属性和默认值设置正确
    """
    result = RouteResult()
    assert result.backend == ""
    assert result.answer == ""
    assert result.request_type == "chat"
    assert result.scenario == ""
    assert result.ms == 0
    assert result.fallback_used is False
    assert result.skills_injected == []
    assert result.retrieval_context == ""


def test_route_result_custom_values():
    """测试 RouteResult 数据类自定义值

    验证 RouteResult 数据类可以接受自定义参数
    """
    result = RouteResult(
        backend="custom_backend",
        answer="custom answer",
        request_type="code",
        scenario="coding",
        ms=100,
        fallback_used=True,
        skills_injected=["skill1", "skill2"],
        retrieval_context="context text",
    )
    assert result.backend == "custom_backend"
    assert result.answer == "custom answer"
    assert result.request_type == "code"
    assert result.scenario == "coding"
    assert result.ms == 100
    assert result.fallback_used is True
    assert result.skills_injected == ["skill1", "skill2"]
    assert result.retrieval_context == "context text"


def test_route_result_with_none_values():
    """测试 RouteResult 数据类 None 值处理

    验证 RouteResult 数据类可以正确处理 None 值
    """
    result = RouteResult(
        backend=None,
        answer=None,
        request_type=None,
        scenario=None,
        ms=None,
        fallback_used=None,
        skills_injected=None,
        retrieval_context=None,
    )
    assert result.backend is None
    assert result.answer is None
    assert result.request_type is None
    assert result.scenario is None
    assert result.ms is None
    assert result.fallback_used is None
    assert result.skills_injected is None
    assert result.retrieval_context is None


def test_route_result_with_special_characters():
    """测试 RouteResult 数据类特殊字符处理

    验证 RouteResult 数据类可以正确处理包含特殊字符的字符串
    """
    result = RouteResult(
        backend="backend_with_special_chars",
        answer="answer with special chars: @#$%^&*()",
        request_type="chat",
        scenario="coding_with_special_chars",
        skills_injected=["skill@1", "skill#2"],
        retrieval_context="context with unicode: 你好世界",
    )
    assert result.backend == "backend_with_special_chars"
    assert result.answer == "answer with special chars: @#$%^&*()"
    assert result.scenario == "coding_with_special_chars"
    assert result.skills_injected == ["skill@1", "skill#2"]
    assert result.retrieval_context == "context with unicode: 你好世界"


def test_route_result_equality():
    """测试 RouteResult 数据类相等性

    验证 RouteResult 数据类可以正确比较相等性和不相等性
    """
    result1 = RouteResult(backend="test", answer="answer", request_type="chat")
    result2 = RouteResult(backend="test", answer="answer", request_type="chat")
    result3 = RouteResult(backend="different", answer="answer", request_type="chat")

    assert result1 == result2
    assert result1 != result3
