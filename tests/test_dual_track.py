"""
test_dual_track.py — 双轨路由 (classify_scenario) 测试
"""

import routing_engine


class TestClassifyScenario:
    """测试场景分类: coding vs chat"""

    def test_ide_request_type_forces_coding(self):
        assert routing_engine.classify_scenario(
            "hello", [], request_type="ide") == "coding"

    def test_ide_source_forces_coding(self):
        assert routing_engine.classify_scenario(
            "你好", [], ide_source="Claude Code") == "coding"
        assert routing_engine.classify_scenario(
            "hi", [], ide_source="Cursor") == "coding"

    def test_code_block_is_coding(self):
        msg = [{"role": "user", "content": "```python\nprint('hi')\n```"}]
        assert routing_engine.classify_scenario("", msg) == "coding"

    def test_traceback_is_coding(self):
        msg = [{"role": "user", "content": "Traceback (most recent call last):"}]
        assert routing_engine.classify_scenario("", msg) == "coding"

    def test_error_keyword_is_coding(self):
        msg = [{"role": "user", "content": "TypeError: cannot read property"}]
        assert routing_engine.classify_scenario("", msg) == "coding"

    def test_multiple_code_signals_is_coding(self):
        msg = [{"role": "user", "content": "import os\ndef main():\n    return 1"}]
        assert routing_engine.classify_scenario("", msg) == "coding"

    def test_single_code_signal_not_enough(self):
        msg = [{"role": "user", "content": "import 是什么意思？"}]
        assert routing_engine.classify_scenario("", msg) == "chat"

    def test_plain_chinese_is_chat(self):
        msg = [{"role": "user", "content": "今天天气怎么样"}]
        assert routing_engine.classify_scenario("", msg) == "chat"

    def test_general_question_is_chat(self):
        msg = [{"role": "user", "content": "帮我解释一下量子力学"}]
        assert routing_engine.classify_scenario("", msg) == "chat"

    def test_empty_messages_is_chat(self):
        assert routing_engine.classify_scenario("你好", []) == "chat"

    def test_query_fallback_when_no_messages(self):
        # query 含多个代码信号时应归为 coding
        assert routing_engine.classify_scenario(
            "def fibonacci(n):\n    return n", []) == "coding"
        # query 无代码信号时应归为 chat
        assert routing_engine.classify_scenario(
            "推荐一本好书", []) == "chat"
