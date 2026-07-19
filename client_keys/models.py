"""Client key domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClientKey:
    """A distributable client API key with quota and URL restrictions."""

    key_id: str
    key_hash: str
    label: str
    # Raw key material; only populated in-memory right after create()/regenerate().
    key_value: str | None = None
    enabled: bool = True
    created_at: float = 0.0
    quota_daily: int = 1000
    quota_monthly: int = 30000
    rate_limit_rpm: int = 20
    allowed_urls: list[str] = field(default_factory=lambda: ["*"])
