"""Additional tests for health_state.py — save/load/on_change."""

import os
import tempfile
from unittest.mock import patch

from health_state import reset_all_state, _health_map, _cooldown_states
from health_state import save_health_state, load_health_state, save_on_change


class TestSaveLoad:
    def setup_method(self):
        reset_all_state()

    def test_save_and_load_empty(self):
        count = load_health_state()
        assert count >= 0

    def test_save_and_load_with_data(self):
        _health_map["test_be"] = "healthy"
        save_health_state()
        reset_all_state()
        assert _health_map.get("test_be") is None
        load_health_state()
        assert _health_map.get("test_be") == "healthy"

    def test_save_on_change(self):
        _health_map["test_be2"] = "degraded"
        save_on_change()
        reset_all_state()
        load_health_state()
        assert _health_map.get("test_be2") == "degraded"

    def test_load_returns_count(self):
        _health_map["a"] = "healthy"
        _health_map["b"] = "dead"
        save_health_state()
        reset_all_state()
        count = load_health_state()
        assert count >= 2
