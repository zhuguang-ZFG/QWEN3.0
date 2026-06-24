from context_pipeline.complexity import (
    assess_complexity,
    dynamic_ensemble_decision,
)


def test_simple_chat_low_complexity():
    messages = [{"role": "user", "content": "what is Python?"}]
    result = assess_complexity(messages)
    assert result.score <= 3
    assert result.recommended_parallelism == 1
    assert result.recommended_tier == "weak"


def test_medium_coding_request():
    # After the coding-capability retirement, IDE-only code vocabulary no longer
    # boosts complexity; the request is treated as a simple chat query.
    messages = [{"role": "user", "content": "fix the bug in server.py where the routing fails"}]
    result = assess_complexity(messages, ide="Cursor")
    assert result.score <= 2
    assert result.recommended_parallelism == 1
    assert result.recommended_tier == "weak"


def test_complex_multi_file_refactor():
    # Coding signals were retired in Phase 0, so this no longer scores as strong.
    # It still registers a moderate complexity factor from length/file mentions.
    messages = [
        {
            "role": "user",
            "content": (
                "refactor the architecture of routing_engine.py and server.py "
                "to use the new pipeline pattern. Also update http_caller.py "
                "and add concurrent handling with proper mutex locks. "
                "The performance optimization should cover all .ts and .go files. "
                "```python\nimport asyncio\nclass Pipeline:\n    def __init__(self):\n        pass\n"
                "    def process(self):\n        pass\n```"
            ),
        }
    ]
    result = assess_complexity(messages, ide="Claude Code")
    assert result.score >= 2
    assert result.recommended_parallelism == 1
    assert result.recommended_tier in ("weak", "medium")


def test_long_code_input_high_complexity():
    code = "def func():\n    pass\n" * 300
    messages = [{"role": "user", "content": f"```python\n{code}\n```\nfix this"}]
    result = assess_complexity(messages)
    assert result.score >= 3
    assert "long_input" in result.factors or "heavy_code" in result.factors


def test_dynamic_ensemble_decision_simple():
    messages = [{"role": "user", "content": "hello"}]
    decision = dynamic_ensemble_decision(messages)
    assert decision["strategy"] == "direct"
    assert decision["parallelism"] == 1


def test_dynamic_ensemble_decision_complex():
    code = "def process():\n    pass\n" * 100
    messages = [
        {
            "role": "user",
            "content": (
                "refactor the distributed architecture in server.py and routing_engine.py "
                "with concurrent optimization for the .go and .rs services. "
                f"```python\n{code}\n```"
            ),
        }
    ]
    decision = dynamic_ensemble_decision(messages, ide="Cursor")
    assert decision["strategy"] in ("ensemble_race", "single_strong")
    assert decision["complexity_score"] >= 4
