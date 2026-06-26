from unittest.mock import MagicMock, patch

import pytest
from config import env
from models.structured_outputs.schemas import IntentResult


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True),
        ("true", True),
        ("True", True),
        ("on", True),
        ("yes", True),
        ("  true  ", True),
        ("0", False),
        ("false", False),
        ("", False),
        ("bad", False),
    ],
)
def test_instructor_intent_enabled(monkeypatch, raw, expected):
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raw)
    assert env.instructor_intent_enabled() is expected


def test_instructor_intent_config_defaults(monkeypatch):
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_PROVIDER", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_MODEL", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_TIMEOUT", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_MAX_RETRIES", raising=False)
    assert env.instructor_intent_enabled() is False
    assert env.instructor_intent_threshold() == 0.70
    assert env.instructor_intent_provider() == "groq"
    assert env.instructor_intent_model() == "llama-3.1-8b-instant"
    assert env.instructor_intent_timeout() == 10.0
    assert env.instructor_intent_max_retries() == 2


def test_instructor_intent_custom_values(monkeypatch):
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.85")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_PROVIDER", "openrouter")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_TIMEOUT", "5.5")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_MAX_RETRIES", "3")
    assert env.instructor_intent_threshold() == 0.85
    assert env.instructor_intent_provider() == "openrouter"
    assert env.instructor_intent_model() == "openai/gpt-4o-mini"
    assert env.instructor_intent_timeout() == 5.5
    assert env.instructor_intent_max_retries() == 3


@pytest.mark.parametrize(
    "env_var, getter, bad_value, default",
    [
        ("LIMA_INSTRUCTOR_INTENT_THRESHOLD", env.instructor_intent_threshold, "bad", 0.70),
        ("LIMA_INSTRUCTOR_INTENT_TIMEOUT", env.instructor_intent_timeout, "abc", 10.0),
        ("LIMA_INSTRUCTOR_INTENT_MAX_RETRIES", env.instructor_intent_max_retries, "x", 2),
    ],
)
def test_instructor_intent_parse_fallback(monkeypatch, env_var, getter, bad_value, default):
    monkeypatch.setenv(env_var, bad_value)
    assert getter() == default


def test_create_structured_completion_success_returns_model():
    from models.structured_outputs import instructor_client

    fake_result = IntentResult(intent="chat", confidence=0.95, source="instructor")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_result

    with patch.dict(
        "sys.modules",
        {"instructor": MagicMock(), "openai": MagicMock()},
    ):
        with patch.object(instructor_client, "key_pool") as mock_key_pool:
            mock_key_pool.get_key.return_value = "gsk-test"
            with patch("instructor.from_openai", return_value=mock_client):
                with patch("openai.OpenAI"):
                    result = instructor_client.create_structured_completion(
                        [{"role": "user", "content": "hello"}],
                        IntentResult,
                        provider="groq",
                        model="llama-3.1-8b-instant",
                    )
                    assert result is fake_result


def test_create_structured_completion_no_key_returns_none():
    from models.structured_outputs import instructor_client

    with patch.object(instructor_client, "key_pool") as mock_key_pool:
        mock_key_pool.get_key.return_value = None
        result = instructor_client.create_structured_completion(
            [{"role": "user", "content": "hello"}],
            IntentResult,
            provider="groq",
        )
        assert result is None


def test_create_structured_completion_unknown_provider_returns_none():
    from models.structured_outputs import instructor_client

    with patch.object(instructor_client, "key_pool") as mock_key_pool:
        mock_key_pool.get_key.return_value = "some-key"
        result = instructor_client.create_structured_completion(
            [{"role": "user", "content": "hello"}],
            IntentResult,
            provider="unknown_provider",
        )
        assert result is None


def test_create_structured_completion_api_error_returns_none():
    from models.structured_outputs import instructor_client

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("api down")

    with patch.dict(
        "sys.modules",
        {"instructor": MagicMock(), "openai": MagicMock()},
    ):
        with patch.object(instructor_client, "key_pool") as mock_key_pool:
            mock_key_pool.get_key.return_value = "gsk-test"
            with patch("instructor.from_openai", return_value=mock_client):
                with patch("openai.OpenAI"):
                    result = instructor_client.create_structured_completion(
                        [{"role": "user", "content": "hello"}],
                        IntentResult,
                        provider="groq",
                    )
                    assert result is None


def test_instructor_intent_event_success():
    from observability.events import instructor_intent_event

    event = instructor_intent_event("groq", "llama-3.1-8b-instant", True)
    assert event.event_type == "instructor_intent_success"
    assert event.backend == "groq/llama-3.1-8b-instant"


def test_instructor_intent_event_failure():
    from observability.events import instructor_intent_event

    event = instructor_intent_event("groq", "llama-3.1-8b-instant", False, reason="timeout")
    assert event.event_type == "instructor_intent_failure"
    assert event.route_reason == "timeout"


def test_analyze_intent_disabled_does_not_call_instructor(monkeypatch):
    from routing_intent import analyze_intent

    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raising=False)
    with patch("routing_intent.instructor_client.create_structured_completion") as mock_create:
        result = analyze_intent("hello")
        assert result["intent"] == "trivial"
        mock_create.assert_not_called()


def test_analyze_intent_low_confidence_uses_instructor(monkeypatch):
    from routing_intent import analyze_intent

    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_ENABLED", "1")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.70")
    fake = IntentResult(
        intent="architecture",
        confidence=0.85,
        source="instructor",
        complexity=0.7,
        needs_code=False,
    )
    with patch("routing_intent.instructor_client.create_structured_completion", return_value=fake):
        result = analyze_intent("explain quantum mechanics to me")
        assert result["intent"] == "architecture"
        assert result["source"] == "instructor"


def test_analyze_intent_instructor_failure_keeps_rule_result(monkeypatch):
    from routing_intent import analyze_intent

    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_ENABLED", "1")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.70")
    with patch("routing_intent.instructor_client.create_structured_completion", return_value=None):
        result = analyze_intent("explain quantum mechanics to me")
        # Should keep the rule/default result rather than crash.
        assert "confidence" in result
        assert result["intent"] == "chat"
