"""Tests for capability_matrix.classify_intent (M2)."""

from capability_matrix import classify_intent


def test_barcode_query_not_classified_as_code():
    assert classify_intent("What is the barcode format?") != "code"


def test_explicit_code_query_not_classified_as_code():
    assert classify_intent("Fix this Python code bug") != "code"
