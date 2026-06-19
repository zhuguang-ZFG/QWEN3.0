"""Independent per-device approval gates for protocol families.

The global ACTIVE_FAMILIES set in protocol_families.py still controls whether a
family is available at all. For gated families, this module adds a per-device
approval check so that display/audio/speech/ocr/camera/perception capabilities
can be enabled independently from motion.
"""

from __future__ import annotations

from device_gateway.family_approval_store import (
    approve_family,
    get_family_approval,
    is_family_approved,
    list_family_approvals,
    revoke_family,
)
from device_gateway.protocol_families import (
    FAMILY_ALLOWLISTS,
    GATED_FAMILIES,
    ProtocolFamily,
    family_is_active,
)


GATE_HARDCODED_APPROVAL_FAMILIES: frozenset[str] = frozenset()


def _family_value(family: str | ProtocolFamily) -> str:
    return family.value if isinstance(family, ProtocolFamily) else family


def family_requires_approval(family: str | ProtocolFamily) -> bool:
    """Return True if the family is gated and requires per-device approval."""
    return _family_value(family) in GATED_FAMILIES


def validate_family_capability(
    device_id: str,
    family: str | ProtocolFamily,
    capability: str,
) -> tuple[bool, str | None]:
    """Validate that a capability is allowed for a device.

    Returns (allowed, error).
    - Gated families (display/audio/speech/ocr/camera/perception) are enabled
      per-device by explicit approval, independent of the global ACTIVE_FAMILIES.
    - Non-gated active families (e.g. motion) use the global allowlist.
    """
    value = _family_value(family)
    allowed = FAMILY_ALLOWLISTS.get(value)
    if allowed is None or capability not in allowed:
        return False, f"Capability '{capability}' not in family '{value}'"

    if value in GATED_FAMILIES:
        if value in GATE_HARDCODED_APPROVAL_FAMILIES:
            return True, None
        if not is_family_approved(device_id, value):
            return False, f"Family '{value}' is not approved for device '{device_id}'"
        return True, None

    if not family_is_active(value):
        return False, f"Family '{value}' is not active"

    return True, None


__all__ = [
    "approve_family",
    "family_requires_approval",
    "get_family_approval",
    "is_family_approved",
    "list_family_approvals",
    "revoke_family",
    "validate_family_capability",
]
