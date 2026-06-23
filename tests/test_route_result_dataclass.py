"""Tests for routing_engine RouteResult / PickResult dataclass construction (P2-11)."""

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


def test_route_result_stores_skills_injected(base_result):
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


def test_route_result_default_values(base_result):
    assert base_result.request_type == "chat"
    assert base_result.scenario == "general"
    assert base_result.skills_injected == []


def test_route_result_backend_and_latency(base_result):
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
