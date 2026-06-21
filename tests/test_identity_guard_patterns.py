"""Tests for identity_guard_patterns."""

from identity_guard_patterns import matches_capability_question, matches_identity_question


def test_identity_keyword_match():
    assert matches_identity_question("你好，你是谁？")
    assert matches_identity_question("Who are you?")


def test_identity_complex_match():
    assert matches_identity_question("谁创造了你")
    assert matches_identity_question("Are you GPT or Claude?")


def test_capability_keyword_and_complex():
    assert matches_capability_question("你能做什么")
    assert matches_capability_question("What are your skills?")


def test_non_identity_question():
    assert not matches_identity_question("写一个 Python 快排")
    assert not matches_capability_question("今天天气怎么样")
