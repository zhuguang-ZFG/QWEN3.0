"""Data models for reverse gateway provider state."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReverseProvider:
    name: str
    port: int
    backends: tuple[str, ...]
    status: str
    reason: str
    adapter: str = ""
    promotion_stage: str = "disabled"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["backends"] = list(self.backends)
        data["healthy"] = self.status == "healthy"
        return data


@dataclass(frozen=True)
class ProbeResult:
    provider: str
    healthy: bool
    status: str
    reason: str
    error_class: str = ""
    latency_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
