"""WeChat mini-program configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class WechatConfig:
    """WeChat mini-program credentials and feature flags.

    Reuses LIMA_WX_APPID / LIMA_WX_SECRET so the same mini-program credentials
    power both subscription-message notifications and server-side login.
    """

    miniapp_appid: str = os.environ.get("LIMA_WX_APPID", "").strip()
    miniapp_secret: str = os.environ.get("LIMA_WX_SECRET", "").strip()
