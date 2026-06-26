import pytest
from config import env


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
