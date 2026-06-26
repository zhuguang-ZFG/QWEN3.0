"""Tests for models.structured_outputs schemas and validator."""

from __future__ import annotations

import pytest

from models.structured_outputs import (
    BackendScore,
    ClassifyResult,
    IntentResult,
    ScenarioResult,
)
from models.structured_outputs.validator import parse_json, validate_value


def test_classify_result_defaults():
    result = ClassifyResult()
    assert result.request_type == "chat"
    assert result.confidence == 1.0


def test_classify_result_invalid_type_falls_back():
    result = validate_value({"request_type": "invalid"}, ClassifyResult)
    assert result.request_type == "chat"  # pydantic uses default on validation error


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ide", "ide"),
        ("chat", "chat"),
        ("vision", "vision"),
        ("image", "image"),
    ],
)
def test_classify_result_valid_types(value, expected):
    result = ClassifyResult(request_type=value)
    assert result.request_type == expected


def test_scenario_result_always_chat():
    result = ScenarioResult()
    assert result.scenario == "chat"


def test_intent_result_lowercases():
    result = IntentResult(intent="DEVICE_DRAW")
    assert result.intent == "device_draw"


def test_intent_result_empty_intent_defaults_to_chat():
    result = IntentResult(intent="   ")
    assert result.intent == "chat"


def test_intent_result_extra_fields_round_trip():
    data = {
        "intent": "code_generation",
        "confidence": 0.9,
        "complexity": 0.7,
        "needs_code": True,
        "domain_keywords": ["python"],
        "cnc_subdomain": "grbl",
        "source": "rules",
    }
    result = IntentResult.model_validate(data)
    assert result.needs_code is True
    assert result.cnc_subdomain == "grbl"


def test_backend_score_validation():
    score = BackendScore(backend="groq", score=0.95, reason="fast")
    assert score.score == 0.95


def test_backend_score_out_of_range_raises():
    with pytest.raises(ValueError):
        BackendScore(backend="groq", score=1.5)


def test_parse_json_valid():
    result = parse_json('{"request_type": "ide"}', ClassifyResult)
    assert result.request_type == "ide"


def test_parse_json_invalid_uses_fallback():
    fallback = ClassifyResult(request_type="chat")
    result = parse_json("not json", ClassifyResult, fallback=fallback)
    assert result.request_type == "chat"


def test_validate_value_returns_default_on_error():
    result = validate_value({"confidence": -1}, IntentResult)
    assert result.intent == "chat"
    assert result.confidence == 1.0
