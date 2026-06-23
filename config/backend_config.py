"""Backend credential centralization (P1-2 phase 2).

Provider-specific credentials are grouped here so backend definitions and
automation code do not repeat ``os.environ.get()`` calls. All values are read
once at module import time; tests should patch the module-level singletons.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudflareCredentials:
    """Cloudflare Workers AI account credentials."""

    account_id: str = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token: str = os.environ.get("CLOUDFLARE_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.token)

    def chat_url(self) -> str:
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            "/ai/v1/chat/completions"
        )

    def search_url(self) -> str:
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            "/ai/models/search"
        )


CLOUDFLARE = CloudflareCredentials()
