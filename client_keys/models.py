"""Client key domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClientKey:
    """A distributable client API key with quota and URL restrictions."""

    key_id: str
    key_value: str
    label: str
    enabled: bool = True
    created_at: float = 0.0
    quota_daily: int = 1000
    quota_monthly: int = 30000
    rate_limit_rpm: int = 20
    allowed_urls: list[str] = field(default_factory=lambda: ["*"])
