"""Tests for routing_difficulty.py — task difficulty estimation."""

import pytest

from routing_difficulty import estimate_difficulty


def test_trivial_query_returns_low_score():
    score = estimate_difficulty("hello", [], scenario="chat")
    assert score < 20


def test_simple_coding_returns_low_score():
    score = estimate_difficulty(
        "just add a print statement",
        [{"role": "user", "content": "just add a print statement"}],
        scenario="coding",
    )
    assert score < 30


def test_refactor_returns_high_score():
    score = estimate_difficulty(
        "refactor the entire authentication module",
        [{"role": "user", "content": "refactor the entire authentication module"}],
        scenario="coding",
    )
    assert score >= 25


def test_architecture_returns_high_score():
    score = estimate_difficulty(
        "design a microservice architecture for the payment system",
        [
            {
                "role": "user",
                "content": "design a microservice architecture for the payment system",
            }
        ],
        scenario="coding",
    )
    # "architecture" (+20) matches; short penalty skipped because score >= 10
    assert score >= 20


def test_multi_turn_refactor_boosts_score():
    # "refactor" (+25) + 3 user messages (+5) = 30; short penalty skipped (30 >= 10)
    score = estimate_difficulty(
        "refactor everything",
        [
            {"role": "user", "content": "help"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "code"},
            {"role": "assistant", "content": "yes"},
            {"role": "user", "content": "refactor everything"},
        ],
        scenario="coding",
    )
    assert score >= 25


def test_short_message_reduces_score():
    score = estimate_difficulty("hi", [], scenario="chat")
    assert score == 0


def test_optimize_query_returns_medium_score():
    # "optimize" (+15); short penalty skipped (15 >= 10)
    score = estimate_difficulty(
        "optimize the database queries in this module",
        [{"role": "user", "content": "optimize the database queries in this module"}],
        scenario="coding",
    )
    assert 15 <= score <= 40


def test_multi_file_query_returns_high_score():
    # "multiple files" (+15); short penalty skipped (15 >= 10)
    score = estimate_difficulty(
        "update multiple files to use the new API",
        [{"role": "user", "content": "update multiple files to use the new API"}],
        scenario="coding",
    )
    assert score >= 15
