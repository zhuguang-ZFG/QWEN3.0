"""Tests for context_pipeline/token_budget.py — token estimation and budgeting."""

from context_pipeline.token_budget import (
    estimate_tokens,
    estimate_request_tokens,
    get_budget_for_scenario,
    check_budget,
    TokenTracker,
    TokenBudget,
)


class TestEstimateTokens:
    def test_ascii_text(self):
        tokens = estimate_tokens("hello world")
        assert tokens > 0

    def test_english_sentence(self):
        text = "The quick brown fox jumps over the lazy dog"
        assert estimate_tokens(text) >= 2

    def test_cjk_text(self):
        text = "你好世界"
        assert estimate_tokens(text) >= 2

    def test_mixed_text(self):
        tokens = estimate_tokens("hello 你好 world 世界")
        assert tokens > 0

    def test_empty_string(self):
        assert estimate_tokens("") == 1


class TestEstimateRequestTokens:
    def test_simple_message(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert estimate_request_tokens(msgs) > 0

    def test_multiple_messages(self):
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response"},
        ]
        total = estimate_request_tokens(msgs)
        assert total > estimate_request_tokens([msgs[0]])

    def test_system_prompt_added(self):
        msgs = [{"role": "user", "content": "hi"}]
        without_sys = estimate_request_tokens(msgs)
        with_sys = estimate_request_tokens(msgs, system_prompt="You are a helpful assistant.")
        assert with_sys > without_sys

    def test_image_part_adds_tokens(self):
        msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:..."}}]}]
        total = estimate_request_tokens(msgs)
        assert total > 500

    def test_list_content_without_text(self):
        msgs = [{"role": "user", "content": []}]
        assert estimate_request_tokens(msgs) >= 0


class TestGetBudgetForScenario:
    def test_chat_budget(self):
        budget = get_budget_for_scenario("chat")
        assert budget.max_input_tokens == 4000
        assert budget.max_output_tokens == 2000

    def test_coding_budget(self):
        budget = get_budget_for_scenario("coding")
        assert budget.max_input_tokens == 16000

    def test_unknown_scenario_falls_back_to_chat(self):
        budget = get_budget_for_scenario("unknown_scenario")
        assert budget.max_input_tokens == 4000

    def test_budget_is_copy_not_reference(self):
        b1 = get_budget_for_scenario("chat")
        b2 = get_budget_for_scenario("chat")
        b1.max_input_tokens = 9999
        assert b2.max_input_tokens == 4000


class TestCheckBudget:
    def test_within_budget(self):
        msgs = [{"role": "user", "content": "short query"}]
        result = check_budget(msgs, "", "chat")
        assert result["within_budget"] is True
        assert result["action"] == "proceed"

    def test_over_budget_truncates(self):
        long_text = "hello " * 5000
        msgs = [{"role": "user", "content": long_text}]
        result = check_budget(msgs, "", "chat")
        assert result["within_budget"] is False
        assert "action" in result

    def test_large_system_prompt(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = check_budget(msgs, "x" * 20000, "chat")
        assert result["within_budget"] is False


class TestTokenBudget:
    def test_is_over_budget(self):
        budget = TokenBudget(max_input_tokens=100)
        budget.estimated_input = 200
        assert budget.is_over_budget is True

    def test_is_not_over_budget(self):
        budget = TokenBudget(max_input_tokens=100)
        budget.estimated_input = 50
        assert budget.is_over_budget is False

    def test_utilization(self):
        budget = TokenBudget(max_input_tokens=100)
        budget.estimated_input = 75
        assert budget.utilization == 0.75

    def test_utilization_zero_when_max_zero(self):
        budget = TokenBudget(max_input_tokens=0)
        assert budget.utilization == 0.0


class TestTokenTracker:
    def test_record_increases_counters(self):
        tracker = TokenTracker()
        tracker.record(100, 50)
        assert tracker.total_input == 100
        assert tracker.total_output == 50
        assert tracker.request_count == 1

    def test_total_tokens(self):
        tracker = TokenTracker()
        tracker.record(200, 100)
        assert tracker.total_tokens == 300

    def test_avg_per_request(self):
        tracker = TokenTracker()
        tracker.record(100, 50)
        tracker.record(200, 100)
        assert tracker.avg_per_request == 225

    def test_avg_per_request_zero_when_no_requests(self):
        tracker = TokenTracker()
        assert tracker.avg_per_request == 0

    def test_summary(self):
        tracker = TokenTracker()
        tracker.record(100, 50)
        summary = tracker.summary()
        assert summary["total_input"] == 100
        assert summary["total_output"] == 50
        assert summary["requests"] == 1
