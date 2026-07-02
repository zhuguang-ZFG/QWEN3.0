"""RouteResult / PickResult dataclass tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from routing_engine import PickResult, RouteResult


@pytest.fixture
def base_result():
    return RouteResult(
        backend="test_backend",
        answer="test answer",
        request_type="chat",
        scenario="general",
        ms=100,
        skills_injected=[],
    )


def test_route_result_default_values():
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
    result1 = RouteResult(backend="test", answer="answer", request_type="chat")
    result2 = RouteResult(backend="test", answer="answer", request_type="chat")
    result3 = RouteResult(backend="different", answer="answer", request_type="chat")

    assert result1 == result2
    assert result1 != result3


def test_route_result_stores_retrieval_context():
    retrieval_context = "This is the retrieved context"
    skills = ["skill1", "skill2"]
    result = RouteResult(
        backend="test_backend",
        answer="test answer",
        request_type="chat",
        scenario="general",
        ms=100,
        skills_injected=skills,
        retrieval_context=retrieval_context,
    )
    assert result.retrieval_context == retrieval_context
    assert result.skills_injected == skills
    assert result.backend == "test_backend"


def test_route_result_handles_code_context():
    code_context = "# Generated code\nimport os\nimport sys"
    result = RouteResult(
        backend="test_backend",
        answer="test answer",
        request_type="code",
        scenario="coding",
        ms=100,
        retrieval_context=code_context,
    )
    assert result.scenario == "coding"
    assert "import os" in result.retrieval_context
    assert "import sys" in result.retrieval_context


def test_route_result_stores_skills_injected():
    result = RouteResult(
        backend="test_backend",
        answer="test answer",
        request_type="chat",
        scenario="coding",
        ms=100,
        skills_injected=["code_fact", "routing_lesson"],
    )
    assert result.scenario == "coding"
    assert len(result.skills_injected) == 2


def test_route_result_base_fixture(base_result):
    assert base_result.request_type == "chat"
    assert base_result.scenario == "general"
    assert base_result.skills_injected == []
    assert base_result.backend == "test_backend"
    assert base_result.ms == 100


def test_pick_result_dataclass():
    result = PickResult(
        backend="groq",
        backends=["groq", "nvidia"],
        messages=[{"role": "user", "content": "hi"}],
        scenario="coding",
        request_type="code",
    )
    assert result.backend == "groq"
    assert result.scenario == "coding"
    assert result.request_type == "code"


def test_route_result_with_validation_mock(base_result):
    validation = MagicMock()
    validation.passed = True
    validation.score = 0.9
    validation.issues = []
    assert validation.passed is True
    assert base_result.request_type == "chat"
