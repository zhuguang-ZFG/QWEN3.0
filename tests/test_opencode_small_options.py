"""Tests for SmallOptions in session_options.py."""


from session_options import is_subagent_request, resolve_small_options


class TestResolveSmallOptions:
    """resolve_small_options() tests."""

    def test_openai_store_false(self):
        result = resolve_small_options("openai_gpt5", "gpt-5", "openai")
        assert result.get("store") is False

    def test_copilot_store_false(self):
        result = resolve_small_options("github_copilot", "gpt-4o", "github_copilot")
        assert result.get("store") is False

    def test_openrouter_disable_reasoning(self):
        result = resolve_small_options("or_gpt5", "gpt-5", "openrouter")
        assert result.get("reasoning") == {"enabled": False}

    def test_google_disable_reasoning(self):
        result = resolve_small_options("google_flash", "gemini-2.5-flash", "google")
        assert result.get("reasoning") == {"enabled": False}

    def test_venice_disable_thinking(self):
        result = resolve_small_options("venice_llama", "llama-4", "venice")
        assert result.get("veniceParameters") == {"disableThinking": True}

    def test_anthropic_empty(self):
        result = resolve_small_options("anthropic_claude", "claude-sonnet-4", "anthropic")
        assert result == {}

    def test_deepseek_empty(self):
        result = resolve_small_options("scnet_ds_flash", "deepseek-v3", "deepseek")
        assert result == {}


class TestIsSubagentRequest:
    """is_subagent_request() tests."""

    def test_subagent_flag(self):
        assert is_subagent_request({"subagent": True}) is True

    def test_is_subagent_flag(self):
        assert is_subagent_request({"is_subagent": True}) is True

    def test_task_request_flag(self):
        assert is_subagent_request({"task_request": True}) is True

    def test_no_flags(self):
        assert is_subagent_request({"type": "normal"}) is False

    def test_none(self):
        assert is_subagent_request(None) is False

    def test_empty(self):
        assert is_subagent_request({}) is False
