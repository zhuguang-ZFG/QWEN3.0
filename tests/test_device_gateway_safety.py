"""Tests for device_gateway/safety.py — motion safety constraints."""

import pytest

from device_gateway.safety import (
    safe_point,
    validate_run_path_params,
    SafetyError,
    MAX_POINTS,
    MAX_FEED,
    DEFAULT_FEED,
)


class TestSafePoint:
    def test_valid_point(self):
        """Valid coordinates return clamped values."""
        result = safe_point(10.0, 20.0)
        assert result["x"] == 10.0
        assert result["y"] == 20.0
        assert result["z"] == 0.0

    def test_valid_point_with_z(self):
        """Z coordinate is preserved."""
        result = safe_point(10.0, 20.0, z=5.0)
        assert result["z"] == 5.0

    def test_negative_x_raises(self):
        """Negative x raises SafetyError."""
        with pytest.raises(SafetyError):
            safe_point(-1.0, 10.0)

    def test_negative_y_raises(self):
        """Negative y raises SafetyError."""
        with pytest.raises(SafetyError):
            safe_point(10.0, -1.0)

    def test_out_of_workspace_x_raises(self):
        """X beyond workspace raises SafetyError."""
        with pytest.raises(SafetyError):
            safe_point(200.0, 10.0)

    def test_out_of_workspace_y_raises(self):
        """Y beyond workspace raises SafetyError."""
        with pytest.raises(SafetyError):
            safe_point(10.0, 200.0)

    def test_out_of_workspace_z_raises(self):
        """Z beyond workspace raises SafetyError."""
        with pytest.raises(SafetyError):
            safe_point(10.0, 10.0, z=50.0)

    def test_boundary_is_safe(self):
        """Workspace boundary coordinates should be safe."""
        result = safe_point(100.0, 100.0, z=20.0)
        assert result["x"] == 100.0
        assert result["y"] == 100.0
        assert result["z"] == 20.0

    def test_zero_is_safe(self):
        """Origin is always safe."""
        result = safe_point(0.0, 0.0)
        assert result["x"] == 0.0
        assert result["y"] == 0.0


class TestValidateRunPathParams:
    def test_valid_path(self):
        """Valid path passes validation."""
        params = {
            "path": [{"x": 0, "y": 0}, {"x": 10, "y": 10}],
            "feed": 500,
        }
        result = validate_run_path_params(params)
        assert len(result["path"]) == 2
        assert result["feed"] == 500

    def test_missing_feed_gets_default(self):
        """Missing feed gets DEFAULT_FEED."""
        params = {
            "path": [{"x": 0, "y": 0}],
        }
        result = validate_run_path_params(params)
        assert result["feed"] == DEFAULT_FEED

    def test_feed_exceeds_max_raises(self):
        """Feed above MAX_FEED raises."""
        params = {
            "path": [{"x": 0, "y": 0}],
            "feed": 9999,
        }
        with pytest.raises(SafetyError):
            validate_run_path_params(params)

    def test_empty_path_raises(self):
        """Empty path raises."""
        params = {"path": [], "feed": 500}
        with pytest.raises(SafetyError):
            validate_run_path_params(params)

    def test_too_many_points_raises(self):
        """Path exceeding MAX_POINTS raises."""
        params = {
            "path": [{"x": i, "y": i} for i in range(MAX_POINTS + 10)],
            "feed": 500,
        }
        with pytest.raises(SafetyError):
            validate_run_path_params(params)

    def test_missing_path_raises(self):
        """Missing path key raises."""
        with pytest.raises(SafetyError):
            validate_run_path_params({"feed": 500})

    def test_invalid_point_format_uses_default_zero(self):
        """Point without x/y uses default zero and passes if origin is safe."""
        params = {
            "path": [{"invalid": "data"}],
            "feed": 500,
        }
        result = validate_run_path_params(params)
        assert len(result["path"]) == 1
        assert result["path"][0]["x"] == 0.0
        assert result["path"][0]["y"] == 0.0

    def test_negative_feed_raises(self):
        """Negative feed raises."""
        params = {
            "path": [{"x": 0, "y": 0}],
            "feed": -1,
        }
        with pytest.raises(SafetyError):
            validate_run_path_params(params)


def test_constants():
    """Safety constants have expected values."""
    assert MAX_POINTS == 128
    assert MAX_FEED == 1200
    assert DEFAULT_FEED == 900


def test_safety_error_exception():
    """SafetyError is a ValueError."""
    assert issubclass(SafetyError, ValueError)
    err = SafetyError("test error")
    assert str(err) == "test error"
