"""Tests for routes/quality_gate.py quality checks, typed results, and fallback."""

from routes.quality_gate import (
    BACKEND_TIERS,
    EXACT_OUTPUT_MARKERS,
    QualityGateResult,
    allows_short_direct_answer,
    default_route,
    expected_direct_answer,
    get_same_tier_backends,
    get_upgrade_chain,
    honest_failure_response,
    quality_check,
    quality_check_typed,
)


def test_quality_check_empty():
    assert quality_check("", 0.5, "test") is False
    assert quality_check(None, 0.5, "test") is False  # type: ignore[arg-type]


def test_quality_check_err_prefix():
    assert quality_check("[ERR] something failed", 0.5, "test") is False


def test_quality_check_valid_response():
    assert quality_check(
        "This is a perfectly valid and reasonably long response.",
        0.5,
        "test",
    ) is True


def test_quality_check_short_for_complex():
    assert quality_check("short", 0.8, "test") is False


def test_quality_check_short_for_simple_ok():
    assert quality_check("short", 0.2, "test") is True


def test_typed_check_empty():
    result = quality_check_typed("", 0.5, "test")
    assert result.passed is False
    assert result.severity == "error"
    assert "empty" in result.reasons[0]


def test_typed_check_err_prefix():
    result = quality_check_typed("[ERR] timeout", 0.5, "test")
    assert result.passed is False


def test_typed_check_valid():
    result = quality_check_typed("A comprehensive response with enough detail.", 0.5, "test")
    assert result.passed is True
    assert result.score >= 0.5


def test_typed_check_to_dict():
    result = quality_check_typed("Good answer here.", 0.5, "test")
    data = result.to_dict()
    assert "passed" in data
    assert "score" in data
    assert "reasons" in data
    assert "severity" in data


def test_typed_check_refusal():
    result = quality_check_typed("I cannot help with that request.", 0.5, "test")
    assert result.passed is False
    assert any("refusal" in reason for reason in result.reasons)


def test_typed_check_allows_safety_refusal_for_harmful_request():
    result = quality_check_typed(
        "I cannot help hack into a bank account.",
        0.5,
        "test",
        query="Tell me how to hack into a bank account.",
    )
    assert result.passed is True
    assert result.reasons == []


def test_typed_check_too_short_is_repairable():
    result = quality_check_typed("short", 0.8, "test")
    assert result.passed is False
    assert result.repairable is True


def test_typed_check_truncation_detection():
    result = quality_check_typed(
        "This is a long answer that goes on and on about the topic in great detail without proper ending",
        0.5,
        "test",
    )
    assert isinstance(result.score, float)


def test_quality_gate_result_defaults():
    result = QualityGateResult(passed=True, score=0.95)
    assert result.reasons == []
    assert result.repairable is False
    assert result.severity == "info"


def test_allows_short_with_marker():
    assert allows_short_direct_answer("Return exactly: ok", "ok") is True


def test_allows_short_without_marker():
    assert allows_short_direct_answer("tell me about ai", "ok") is False


def test_allows_short_long_response():
    assert allows_short_direct_answer("Return exactly: " + "x" * 150, "x" * 150) is False


def test_expected_direct_answer_english():
    assert expected_direct_answer("Return exactly: hello_world") == "hello_world"


def test_expected_direct_answer_chinese():
    assert expected_direct_answer("\u53ea\u8fd4\u56de\uff1a\u4f60\u597d") == "\u4f60\u597d"


def test_expected_direct_answer_no_match():
    assert expected_direct_answer("explain routing to me") == ""


def test_tiers_non_empty():
    assert len(BACKEND_TIERS) >= 2


def test_default_route_short():
    backend = default_route("hi")
    assert backend in ("longcat_lite", "longcat_chat", "nvidia_qwen_coder", "longcat")


def test_default_route_code():
    backend = default_route("fix bug in function def foo(): pass")
    assert backend is not None


def test_default_route_long():
    backend = default_route("explain " + "x " * 100)
    assert backend is not None


def test_honest_failure_openai():
    response = honest_failure_response("chatcmpl-test123", "openai")
    assert "choices" in response
    assert "\u6682\u65f6\u4e0d\u53ef\u7528" in response["choices"][0]["message"]["content"]


def test_honest_failure_anthropic():
    response = honest_failure_response("msg-test123", "anthropic")
    assert response["stop_reason"] == "end_turn"


def test_get_same_tier_backends():
    same = get_same_tier_backends("longcat_lite")
    assert isinstance(same, list)
    assert "longcat_lite" not in same


def test_get_upgrade_chain():
    chain = get_upgrade_chain("longcat_lite")
    assert isinstance(chain, list)


def test_exact_markers_exist():
    assert len(EXACT_OUTPUT_MARKERS) >= 4
    assert "return exactly" in EXACT_OUTPUT_MARKERS
