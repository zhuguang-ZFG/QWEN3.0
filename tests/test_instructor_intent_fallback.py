def test_instructor_intent_config_defaults(monkeypatch):
    from config import env

    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", raising=False)
    assert env.instructor_intent_enabled() is False
    assert env.instructor_intent_threshold() == 0.70
    assert env.instructor_intent_provider() == "groq"
    assert env.instructor_intent_model() == "llama-3.1-8b-instant"
    assert env.instructor_intent_timeout() == 10.0
    assert env.instructor_intent_max_retries() == 2
