"""Tests for device_gateway.device_profile."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from device_gateway.device_profile import (
    COMPUTE_LEVELS,
    DeviceCapability,
    DeviceHistory,
    DevicePreferences,
    DeviceProfile,
    infer_profile_from_artifacts,
    profile_from_dict,
    profile_from_hello_frame,
    profile_to_dict,
    register_device_profile,
    get_device_profile,
    reset_device_profiles_for_tests,
)


def setup_function():
    reset_device_profiles_for_tests()


# ── Data structure tests ──────────────────────────────────────────────────


class TestDeviceCapability:
    def test_valid_compute_levels(self):
        for level in COMPUTE_LEVELS:
            cap = DeviceCapability(compute_level=level)
            assert cap.compute_level == level

    def test_invalid_compute_level_raises(self):
        try:
            DeviceCapability(compute_level="ultra")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass

    def test_is_compatible_passes_when_requirements_met(self):
        cap = DeviceCapability(compute_level="high", memory_mb=2048, supported_features=("text", "vector_path", "vision"))
        req = {
            "min_compute_level": "medium",
            "min_memory_mb": 512,
            "requires_features": ["text", "vector_path"],
        }
        assert cap.is_compatible(req) is True

    def test_is_compatible_fails_when_compute_too_low(self):
        cap = DeviceCapability(compute_level="low", memory_mb=512)
        req = {"min_compute_level": "high"}
        assert cap.is_compatible(req) is False

    def test_is_compatible_fails_when_memory_too_low(self):
        cap = DeviceCapability(compute_level="medium", memory_mb=128)
        req = {"min_compute_level": "low", "min_memory_mb": 256}
        assert cap.is_compatible(req) is False

    def test_is_compatible_fails_when_feature_missing(self):
        cap = DeviceCapability(compute_level="high", memory_mb=2048, supported_features=("text",))
        req = {"requires_features": ["text", "vision"]}
        assert cap.is_compatible(req) is False

    def test_is_compatible_empty_requirement(self):
        cap = DeviceCapability()
        assert cap.is_compatible({}) is True


class TestDevicePreferences:
    def test_valid_quality_priority(self):
        for v in ("speed", "quality", "balanced"):
            p = DevicePreferences(quality_priority=v)
            assert p.quality_priority == v

    def test_invalid_quality_priority_raises(self):
        try:
            DevicePreferences(quality_priority="fastest")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass

    def test_valid_cost_sensitivity(self):
        for v in ("low", "medium", "high"):
            p = DevicePreferences(cost_sensitivity=v)
            assert p.cost_sensitivity == v

    def test_invalid_cost_sensitivity_raises(self):
        try:
            DevicePreferences(cost_sensitivity="extreme")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


# ── Profile source: hello frame ───────────────────────────────────────────


class TestProfileFromHelloFrame:
    def test_minimal_hello(self):
        hello = {"device_id": "esp32_001"}
        profile = profile_from_hello_frame("esp32_001", hello)
        assert profile.device_id == "esp32_001"
        assert profile.capability.compute_level == "low"
        assert profile.capability.memory_mb == 512
        assert profile.capability.supported_features == ("vector_path", "text")
        assert profile.preferences.latency_sensitive is True
        assert profile.history.total_tasks == 0

    def test_full_hello(self):
        hello = {
            "capability": {
                "compute_level": "medium",
                "memory_mb": 1024,
                "supported_features": ["text", "vector_path", "vision"],
            },
            "preferences": {
                "latency_sensitive": False,
                "quality_priority": "quality",
                "cost_sensitivity": "high",
            },
            "history": {
                "preferred_models": ["scnet_large", "gemini_2p5_pro"],
                "failed_backends": ["github_gpt4o"],
                "avg_latency_ms": 1200.0,
                "success_rate": 0.88,
                "total_tasks": 45,
            },
        }
        profile = profile_from_hello_frame("dev-42", hello)
        assert profile.device_id == "dev-42"
        assert profile.capability.compute_level == "medium"
        assert profile.capability.memory_mb == 1024
        assert profile.preferences.latency_sensitive is False
        assert profile.preferences.quality_priority == "quality"
        assert profile.history.preferred_models == ("scnet_large", "gemini_2p5_pro")
        assert profile.history.failed_backends == ("github_gpt4o",)
        assert profile.history.avg_latency_ms == 1200.0
        assert profile.history.total_tasks == 45


# ── Profile serialisation round-trip ──────────────────────────────────────


class TestProfileSerialisation:
    def test_roundtrip(self):
        original = DeviceProfile(
            device_id="dev-roundtrip",
            capability=DeviceCapability(compute_level="high", memory_mb=4096, supported_features=("text", "vision")),
            preferences=DevicePreferences(latency_sensitive=False, quality_priority="quality"),
            history=DeviceHistory(
                preferred_models=("gemini_2p5_pro",),
                failed_backends=(),
                avg_latency_ms=900.0,
                success_rate=0.97,
                total_tasks=200,
            ),
        )
        d = profile_to_dict(original)
        restored = profile_from_dict(d)
        assert restored.device_id == original.device_id
        assert restored.capability.compute_level == original.capability.compute_level
        assert restored.capability.memory_mb == original.capability.memory_mb
        assert restored.capability.supported_features == original.capability.supported_features
        assert restored.preferences.latency_sensitive == original.preferences.latency_sensitive
        assert restored.preferences.quality_priority == original.preferences.quality_priority
        assert restored.history.preferred_models == original.history.preferred_models
        assert restored.history.failed_backends == original.history.failed_backends
        assert restored.history.total_tasks == original.history.total_tasks


# ── Profile registration ─────────────────────────────────────────────────


class TestProfileRegistration:
    def test_register_and_get(self):
        profile = DeviceProfile(
            device_id="dev-reg",
            capability=DeviceCapability(compute_level="low"),
        )
        register_device_profile(profile)
        fetched = get_device_profile("dev-reg")
        assert fetched is not None
        assert fetched.device_id == "dev-reg"
        assert fetched.capability.compute_level == "low"

    def test_get_unknown_returns_none(self):
        assert get_device_profile("nonexistent") is None

    def test_reset_clears_all(self):
        profile = DeviceProfile(device_id="dev-temp")
        register_device_profile(profile)
        reset_device_profiles_for_tests()
        assert get_device_profile("dev-temp") is None


# ── Profile inference from artifacts ──────────────────────────────────────


class TestInferFromArtifacts:
    def test_missing_log_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = infer_profile_from_artifacts("dev-missing", artifact_dir=tmp)
            assert result is None

    def test_infer_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "route_evidence_dev-artifact.log"
            lines = [
                json.dumps({"device_id": "dev-artifact", "selected_model": "scnet_ds_flash", "backend": "scnet_ds",
                             "route_policy": {"route_role": "device_draw"}, "reason": "success",
                             "timestamp": "2026-06-10T12:00:00+00:00"}),
                json.dumps({"device_id": "dev-artifact", "selected_model": "scnet_ds_flash", "backend": "scnet_ds",
                             "route_policy": {"route_role": "device_write"}, "reason": "success",
                             "timestamp": "2026-06-10T12:01:00+00:00"}),
                json.dumps({"device_id": "dev-artifact", "selected_model": "", "backend": "github_gpt4o",
                             "route_policy": {}, "reason": "backend failed",
                             "timestamp": "2026-06-10T12:02:00+00:00"}),
            ]
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = infer_profile_from_artifacts("dev-artifact", artifact_dir=tmp)
            assert result is not None
            assert result.device_id == "dev-artifact"
            assert "scnet_ds_flash" in result.history.preferred_models
            assert "github_gpt4o" in result.history.failed_backends
            assert result.history.total_tasks == 3

    def test_stale_evidence_skipped(self):
        """Evidence older than max_age_s should be excluded."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "route_evidence_dev-stale.log"
            lines = [
                json.dumps({"device_id": "dev-stale", "selected_model": "old_model", "backend": "old",
                             "route_policy": {"r": 1}, "reason": "success",
                             "timestamp": "2020-01-01T00:00:00+00:00"}),
            ]
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = infer_profile_from_artifacts("dev-stale", artifact_dir=tmp, max_age_s=3600)
            assert result is None  # all evidence too old
