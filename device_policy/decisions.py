"""Policy decision vocabulary for device task dispatch.

Defines all possible decisions the policy engine can return,
with Chinese labels for operator-facing diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DECISION_VALUES: frozenset[str] = frozenset({
    "allow",
    "require_approval",
    "reject",
    "require_self_check",
    "require_home",
    "require_ota",
    "degrade_to_asset",
})

DECISION_LABELS_ZH: dict[str, str] = {
    "allow": "允许执行",
    "require_approval": "需要家长/管理员审批",
    "reject": "拒绝执行",
    "require_self_check": "需要先执行自检",
    "require_home": "需要先回零校准",
    "require_ota": "需要先升级固件",
    "degrade_to_asset": "降级为预制资源",
}


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    REJECT = "reject"
    REQUIRE_SELF_CHECK = "require_self_check"
    REQUIRE_HOME = "require_home"
    REQUIRE_OTA = "require_ota"
    DEGRADE_TO_ASSET = "degrade_to_asset"


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in DECISION_VALUES:
            raise ValueError(f"unknown policy decision: {self.decision}")
        object.__setattr__(self, "reason", str(self.reason or ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "label_zh": DECISION_LABELS_ZH.get(self.decision, ""),
        }
