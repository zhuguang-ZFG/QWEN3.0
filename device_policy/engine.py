"""Policy engine — centralizes permission, safety, and approval decisions."""

from __future__ import annotations

from typing import Any

from device_intelligence.safety import profile_limit_error, validate_profile_compatibility
from device_intelligence.schemas import DeviceProfile
from device_protocol_registry import protocol_registry, ProtocolCompatibilityError

from .decisions import PolicyResult


class PolicyEngine:
    """Evaluate whether a task may proceed to dispatch.

    Decisions flow through three gates in order:
    1. Protocol gate  — capability + firmware compatibility
    2. Safety gate    — profile-aware workspace/feed/point limits
    3. Capability gate — does the device profile support this?
    """

    def reset(self) -> None:
        pass  # Stateless for now; future: clear cached decisions

    def _protocol_gate(self, capability: str, fw_rev: str) -> PolicyResult | None:
        """Return a non-allow PolicyResult or None if the gate passes."""
        if not protocol_registry.is_capability_supported(capability):
            return PolicyResult(
                decision="reject",
                reason=f"capability not supported: {capability}",
            )
        if fw_rev:
            try:
                protocol_registry.assert_firmware_compatible(fw_rev)
            except ProtocolCompatibilityError as exc:
                return PolicyResult(decision="require_ota", reason=str(exc))
        return None

    def _profile_safety_gate(
        self,
        capability: str,
        params: dict[str, Any],
        profile: DeviceProfile,
        fw_rev: str,
    ) -> PolicyResult | None:
        """Return a non-allow PolicyResult or None if profile/safety checks pass."""
        profile_err = validate_profile_compatibility(profile, fw_rev)
        if profile_err:
            return PolicyResult(
                decision="reject",
                reason=f"profile incompatible: {profile_err}",
            )
        limit_err = profile_limit_error(params, profile)
        if limit_err:
            if capability not in profile.capabilities:
                return PolicyResult(
                    decision="degrade_to_asset",
                    reason=f"capability {capability} not in profile",
                )
            return PolicyResult(
                decision="reject",
                reason=f"safety limit exceeded: {limit_err}",
            )
        if capability not in profile.capabilities:
            return PolicyResult(
                decision="degrade_to_asset",
                reason=f"capability {capability} not in profile capabilities",
            )
        return None

    def decide(
        self,
        *,
        capability: str,
        device_id: str,
        fw_rev: str,
        params: dict[str, Any],
        profile: DeviceProfile | None = None,
        shadow_state: dict[str, Any] | None = None,
    ) -> PolicyResult:
        result = self._protocol_gate(capability, fw_rev)
        if result is not None:
            return result
        if profile is not None:
            result = self._profile_safety_gate(capability, params, profile, fw_rev)
            if result is not None:
                return result
        return PolicyResult(decision="allow", reason="policy passed")


policy_engine = PolicyEngine()
