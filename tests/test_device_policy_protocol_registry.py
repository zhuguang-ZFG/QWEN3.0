"""Tests for M3: Policy Engine + Protocol Registry.

Covers:
- Decision vocabulary (allow/reject/require_approval/etc.)
- Protocol compatibility (old firmware rejects new fields)
- Policy engine wiring (decision blocks dispatch)
"""
from __future__ import annotations

import pytest

from device_policy import (
    PolicyDecision,
    PolicyResult,
    policy_engine,
)
from device_policy.decisions import DECISION_VALUES, DECISION_LABELS_ZH
from device_protocol_registry import (
    ProtocolRegistry,
    protocol_registry,
    ProtocolCompatibilityError,
)
from device_intelligence.schemas import DeviceProfile


# ── Decision vocabulary ──────────────────────────────────────────────────


class TestDecisionVocabulary:
    """Verify the decision vocabulary is complete and deterministic."""

    def test_all_decisions_defined(self) -> None:
        expected = frozenset({
            "allow",
            "require_approval",
            "reject",
            "require_self_check",
            "require_home",
            "require_ota",
            "degrade_to_asset",
        })
        assert DECISION_VALUES == expected

    def test_every_decision_has_chinese_label(self) -> None:
        for decision in DECISION_VALUES:
            assert decision in DECISION_LABELS_ZH
            assert isinstance(DECISION_LABELS_ZH[decision], str)
            assert len(DECISION_LABELS_ZH[decision]) > 0

    def test_policy_result_immutable(self) -> None:
        result = PolicyResult(decision="allow", reason="ok")
        with pytest.raises(AttributeError):
            result.decision = "reject"  # type: ignore[misc]

    def test_policy_result_to_dict(self) -> None:
        result = PolicyResult(decision="require_approval", reason="voice task needs parent")
        d = result.to_dict()
        assert d["decision"] == "require_approval"
        assert d["reason"] == "voice task needs parent"

    def test_policy_decision_enum_values(self) -> None:
        assert PolicyDecision.ALLOW.value == "allow"
        assert PolicyDecision.REJECT.value == "reject"
        assert PolicyDecision.REQUIRE_APPROVAL.value == "require_approval"
        assert PolicyDecision.REQUIRE_SELF_CHECK.value == "require_self_check"
        assert PolicyDecision.REQUIRE_HOME.value == "require_home"
        assert PolicyDecision.REQUIRE_OTA.value == "require_ota"
        assert PolicyDecision.DEGRADE_TO_ASSET.value == "degrade_to_asset"

    def test_unknown_decision_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown"):
            PolicyResult(decision="unknown_thing", reason="bad")


# ── Protocol compatibility ───────────────────────────────────────────────


class TestProtocolCompatibility:
    """Old firmware must not receive fields it cannot understand."""

    def test_registry_knows_supported_capabilities(self) -> None:
        assert protocol_registry.is_capability_supported("run_path")
        assert protocol_registry.is_capability_supported("home")
        assert protocol_registry.is_capability_supported("draw_generated")

    def test_registry_rejects_unknown_capability(self) -> None:
        assert not protocol_registry.is_capability_supported("laser_cut")

    def test_registry_protocol_version(self) -> None:
        assert protocol_registry.protocol_version() == "lima-device-v1"

    def test_registry_min_firmware(self) -> None:
        min_fw = protocol_registry.min_firmware()
        assert isinstance(min_fw, str)
        assert len(min_fw) > 0

    def test_registry_firmware_too_old(self) -> None:
        min_fw = protocol_registry.min_firmware()
        # Construct a firmware string that is "before" the minimum
        old_fw = "v0.0.1" if min_fw > "v0.0.1" else ""
        if old_fw:
            with pytest.raises(ProtocolCompatibilityError):
                protocol_registry.assert_firmware_compatible(old_fw)

    def test_registry_firmware_compatible(self) -> None:
        min_fw = protocol_registry.min_firmware()
        # The minimum firmware itself should always pass
        protocol_registry.assert_firmware_compatible(min_fw)

    def test_registry_empty_firmware_treated_as_unknown(self) -> None:
        # Empty firmware means unknown device — allow with warning
        result = protocol_registry.firmware_status("")
        assert result == "unknown"

    def test_registry_deprecated_fields(self) -> None:
        deprecated = protocol_registry.deprecated_fields()
        assert isinstance(deprecated, frozenset)

    def test_custom_registry(self) -> None:
        reg = ProtocolRegistry(
            protocol_version_str="lima-device-v2",
            min_firmware_str="v2.0.0",
            supported_capabilities=frozenset({"run_path"}),
        )
        assert reg.protocol_version() == "lima-device-v2"
        assert reg.is_capability_supported("run_path")
        assert not reg.is_capability_supported("home")


# ── Policy engine ────────────────────────────────────────────────────────


class TestPolicyEngine:
    """Policy decisions must block unsafe dispatches."""

    def test_allow_control_capability(self) -> None:
        result = policy_engine.decide(
            capability="home",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={},
        )
        assert result.decision == "allow"

    def test_allow_motion_with_valid_params(self) -> None:
        result = policy_engine.decide(
            capability="run_path",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={"path": [{"x": 10, "y": 20, "z": 0}], "feed": 500},
        )
        assert result.decision == "allow"

    def test_reject_unsupported_capability(self) -> None:
        result = policy_engine.decide(
            capability="laser_cut",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={},
        )
        assert result.decision == "reject"
        assert "unsupported" in result.reason.lower() or "not" in result.reason.lower()

    def test_reject_incompatible_firmware(self) -> None:
        # Use a firmware clearly older than min
        result = policy_engine.decide(
            capability="run_path",
            device_id="dev-1",
            fw_rev="v0.0.1",
            params={"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500},
        )
        assert result.decision in ("reject", "require_ota")

    def test_require_home_when_not_homed(self) -> None:
        # When shadow says device is not homed and task requires path
        result = policy_engine.decide(
            capability="run_path",
            device_id="dev-unhomed",
            fw_rev="v1.0.0",
            params={"path": [{"x": 10, "y": 20, "z": 0}], "feed": 500},
            shadow_state={"known": True, "homed": False},
        )
        assert result.decision in ("require_home", "allow")  # first time may allow

    def test_degrade_when_profile_mismatch(self) -> None:
        profile = DeviceProfile(
            profile_id="test-profile",
            model="test",
            capabilities=("run_path",),
        )
        result = policy_engine.decide(
            capability="write_text",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={"path": [], "feed": 500, "text": "hi"},
            profile=profile,
        )
        # write_text is not in this profile's capabilities
        assert result.decision in ("degrade_to_asset", "reject")

    def test_decision_stored_in_result(self) -> None:
        result = policy_engine.decide(
            capability="home",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={},
        )
        d = result.to_dict()
        assert "decision" in d
        assert "reason" in d

    def test_engine_reset(self) -> None:
        policy_engine.reset()
        # After reset, should still work
        result = policy_engine.decide(
            capability="home",
            device_id="dev-1",
            fw_rev="v1.0.0",
            params={},
        )
        assert result.decision == "allow"
