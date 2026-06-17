"""M5: Unit tests for device_intelligence.recovery module."""

from __future__ import annotations

import pytest

from device_intelligence.recovery import recovery_action, should_retry


class TestRecoveryActionMapping:
    def test_e_missing_path_retry(self) -> None:
        a = recovery_action("E_MISSING_PATH")
        assert a.action == "retry"
        assert a.max_retries == 3
        assert a.cooldown_ms == 2000
        assert a.explanation_zh

    def test_e_limit_retry(self) -> None:
        a = recovery_action("E_LIMIT")
        assert a.action == "retry"
        assert a.max_retries == 1
        assert a.cooldown_ms == 500

    def test_e_not_homed_home(self) -> None:
        a = recovery_action("E_NOT_HOMED")
        assert a.action == "home"
        assert a.max_retries == 0

    def test_e_uart_timeout_retry(self) -> None:
        a = recovery_action("E_UART_TIMEOUT")
        assert a.action == "retry"
        assert a.max_retries == 2
        assert a.cooldown_ms == 1000

    def test_e_estop_stop(self) -> None:
        a = recovery_action("E_ESTOP")
        assert a.action == "stop"
        assert a.max_retries == 0

    def test_unknown_code_defaults_to_stop(self) -> None:
        a = recovery_action("E_BOGUS_ERROR")
        assert a.action == "stop"

    def test_empty_code_defaults_to_stop(self) -> None:
        a = recovery_action("")
        assert a.action == "stop"

    def test_none_code_defaults_to_stop(self) -> None:
        a = recovery_action(None)
        assert a.action == "stop"

    def test_case_insensitive_lookup(self) -> None:
        a = recovery_action("e_missing_path")
        assert a.action == "retry"
        assert a.max_retries == 3


class TestShouldRetry:
    def test_retry_within_limit(self) -> None:
        assert should_retry("E_MISSING_PATH", 0) is True
        assert should_retry("E_MISSING_PATH", 2) is True

    def test_retry_at_limit(self) -> None:
        assert should_retry("E_MISSING_PATH", 3) is False

    def test_retry_exceeds_limit(self) -> None:
        assert should_retry("E_MISSING_PATH", 5) is False

    def test_negative_attempt(self) -> None:
        assert should_retry("E_MISSING_PATH", -1) is False

    def test_non_retry_action_always_false(self) -> None:
        assert should_retry("E_NOT_HOMED", 0) is False
        assert should_retry("E_ESTOP", 0) is False

    def test_e_limit_only_one_retry(self) -> None:
        assert should_retry("E_LIMIT", 0) is True
        assert should_retry("E_LIMIT", 1) is False

    def test_e_uart_timeout_two_retries(self) -> None:
        assert should_retry("E_UART_TIMEOUT", 0) is True
        assert should_retry("E_UART_TIMEOUT", 1) is True
        assert should_retry("E_UART_TIMEOUT", 2) is False


class TestRecoveryActionDataclass:
    def test_dataclass_is_frozen(self) -> None:
        a = recovery_action("E_ESTOP")
        with pytest.raises(Exception):
            a.action = "retry"

    def test_all_explanations_are_non_empty(self) -> None:
        codes = ["E_MISSING_PATH", "E_LIMIT", "E_NOT_HOMED", "E_UART_TIMEOUT", "E_ESTOP"]
        for code in codes:
            a = recovery_action(code)
            assert a.explanation_zh, f"{code} explanation must not be empty"

    def test_unknown_explanation_is_non_empty(self) -> None:
        a = recovery_action("UNKNOWN_CODE_XYZ")
        assert a.explanation_zh
