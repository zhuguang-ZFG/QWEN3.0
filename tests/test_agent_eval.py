"""Tests for agent_eval harness."""

import sys
sys.path.insert(0, "D:/GIT")

from agent_eval import (
    TaskScore,
    can_auto_promote,
    RegressionEntry,
    RegressionSuite,
)


def _score(**overrides) -> TaskScore:
    defaults = dict(
        tests_passed=True,
        diff_minimal=True,
        security_ok=True,
        docs_updated=True,
        rollback_ready=True,
        human_review_required=False,
    )
    defaults.update(overrides)
    return TaskScore(**defaults)


def test_failed_tests_prevent_auto_promotion():
    score = _score(tests_passed=False)
    assert can_auto_promote(score) is False


def test_security_risk_prevents_auto_promotion():
    score = _score(security_ok=False)
    assert can_auto_promote(score) is False


def test_human_review_prevents_auto_promotion():
    score = _score(human_review_required=True)
    assert can_auto_promote(score) is False


def test_all_passing_allows_auto_promotion():
    score = _score()
    assert can_auto_promote(score) is True


def test_regression_suite_tracks_entries():
    suite = RegressionSuite()
    suite.add(RegressionEntry("test_a", "pytest -k a", True))
    suite.add(RegressionEntry("test_b", "pytest -k b", False))

    results = suite.run_all()
    assert results == [("test_a", True), ("test_b", False)]
    assert suite.all_passed() is False


def test_regression_suite_all_passed():
    suite = RegressionSuite()
    suite.add(RegressionEntry("ok1", "pytest ok1", True))
    suite.add(RegressionEntry("ok2", "pytest ok2", True))
    assert suite.all_passed() is True
