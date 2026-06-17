"""Dynamic backend admission overlay (CF-G-2 / PA-D).

Overlays never edit ``backends_registry.py``. Routing merge requires
``LIMA_DYNAMIC_ADMISSION=1``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_PATH = ROOT / "data" / "backend_admission.json"

_CHAT_POOLS = {"chat", "ide", "chat_fast"}
_CODE_POOLS = {"code"}


@dataclass
class WatchlistEntry:
    backend_key: str
    reason: str
    action: str = "watch"


@dataclass
class AdmissionOverlay:
    backend_key: str
    provider: str
    model_id: str
    tier: str
    admission_status: str = "admitted_late_fallback"
    private_code_allowed: bool = False
    enabled: bool = True
    evidence_refs: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_key": self.backend_key,
            "provider": self.provider,
            "model_id": self.model_id,
            "tier": self.tier,
            "admission_status": self.admission_status,
            "private_code_allowed": self.private_code_allowed,
            "enabled": self.enabled,
            "expires_at": None,
            "evidence_refs": list(self.evidence_refs),
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdmissionOverlay":
        return cls(
            backend_key=str(data.get("backend_key", "")),
            provider=str(data.get("provider", "")),
            model_id=str(data.get("model_id", "")),
            tier=str(data.get("tier", "late_fallback")),
            admission_status=str(data.get("admission_status", "admitted_late_fallback")),
            private_code_allowed=bool(data.get("private_code_allowed", False)),
            enabled=bool(data.get("enabled", True)),
            evidence_refs=[str(x) for x in data.get("evidence_refs", []) if str(x)],
            latency_ms=float(data.get("latency_ms") or 0.0),
        )


def dynamic_admission_enabled() -> bool:
    return os.environ.get("LIMA_DYNAMIC_ADMISSION", "0") == "1"


def load_store(path: str | Path = "") -> dict[str, Any]:
    store_path = Path(path) if path else DEFAULT_PATH
    if not store_path.is_file():
        return {"watchlist": [], "overlays": []}
    data = json.loads(store_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"watchlist": [], "overlays": []}
    data.setdefault("watchlist", [])
    data.setdefault("overlays", [])
    return data


def save_store(data: dict[str, Any], path: str | Path = "") -> None:
    store_path = Path(path) if path else DEFAULT_PATH
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_watchlist(data: dict[str, Any]) -> list[WatchlistEntry]:
    entries: list[WatchlistEntry] = []
    for item in data.get("watchlist", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("backend_key") or "")
        if key:
            entries.append(
                WatchlistEntry(
                    backend_key=key,
                    reason=str(item.get("reason") or ""),
                    action=str(item.get("action") or "watch"),
                )
            )
    return entries


def parse_overlays(data: dict[str, Any]) -> list[AdmissionOverlay]:
    overlays: list[AdmissionOverlay] = []
    for item in data.get("overlays", []):
        if isinstance(item, dict) and item.get("backend_key"):
            overlays.append(AdmissionOverlay.from_dict(item))
    return overlays


def get_enabled_overlays(path: str | Path = "") -> list[AdmissionOverlay]:
    if not dynamic_admission_enabled():
        return []
    return [o for o in parse_overlays(load_store(path)) if o.enabled]


def get_routing_overlays_for_pool(pool_key: str, path: str | Path = "") -> list[str]:
    grouped = get_overlay_backends_by_tier(pool_key, path)
    ordered: list[str] = []
    for tier in ("medium", "floor", "late_fallback"):
        for key in grouped.get(tier, []):
            if key not in ordered:
                ordered.append(key)
    return ordered


def get_overlay_backends_by_tier(pool_key: str, path: str | Path = "") -> dict[str, list[str]]:
    if not dynamic_admission_enabled():
        return {"medium": [], "floor": [], "late_fallback": []}
    grouped: dict[str, list[str]] = {"medium": [], "floor": [], "late_fallback": []}
    for overlay in get_enabled_overlays(path):
        if overlay.admission_status != "admitted_late_fallback":
            continue
        tier = overlay.tier if overlay.tier in grouped else "late_fallback"
        if pool_key in _CODE_POOLS:
            if tier in ("floor", "late_fallback") or (tier == "medium" and overlay.private_code_allowed):
                grouped["floor" if tier == "late_fallback" else tier].append(overlay.backend_key)
        elif pool_key in _CHAT_POOLS or pool_key == "vision":
            if tier == "late_fallback":
                grouped["medium"].append(overlay.backend_key)
            elif tier in ("medium", "floor"):
                grouped[tier].append(overlay.backend_key)
    return grouped


def apply_startup(path: str | Path = "") -> int:
    """Register overlay backends and apply watchlist disable actions."""
    from provider_automation.adapters.cloudflare import build_backend_config

    data = load_store(path)
    applied = 0
    try:
        from backend_utils import set_enabled
        from backends_registry import BACKENDS
    except ImportError as exc:
        logger.warning("backend admission startup skipped: backends not importable: %s", exc)
        return 0

    for overlay in parse_overlays(data):
        if not overlay.enabled:
            continue
        if overlay.backend_key not in BACKENDS:
            if overlay.provider == "cloudflare":
                BACKENDS[overlay.backend_key] = build_backend_config(overlay.model_id)
                applied += 1
            elif overlay.provider == "gitee":
                from provider_automation.adapters.gitee_ai import build_backend_config as build_gitee

                BACKENDS[overlay.backend_key] = build_gitee(overlay.model_id)
                applied += 1

    for entry in parse_watchlist(data):
        if entry.action == "disable":
            set_enabled(entry.backend_key, False)
            logger.info("watchlist disabled backend %s: %s", entry.backend_key, entry.reason)

    if applied:
        logger.info("backend admission applied %s overlay backend(s)", applied)
    return applied


def upsert_overlay(overlay: AdmissionOverlay, path: str | Path = "") -> None:
    data = load_store(path)
    overlays = [o for o in parse_overlays(data) if o.backend_key != overlay.backend_key]
    overlays.append(overlay)
    data["overlays"] = [o.to_dict() for o in overlays]
    save_store(data, path)


def append_watchlist(entry: WatchlistEntry, path: str | Path = "") -> None:
    data = load_store(path)
    watchlist = [w for w in parse_watchlist(data) if w.backend_key != entry.backend_key]
    watchlist.append(entry)
    data["watchlist"] = [{"backend_key": w.backend_key, "reason": w.reason, "action": w.action} for w in watchlist]
    save_store(data, path)


def overlay_from_probe(entry, batch_result, *, latency_ms: float = 0.0) -> AdmissionOverlay | None:
    from provider_automation.adapters.cloudflare import map_model_to_backend_key, suggest_admission_tier
    from provider_automation.catalog import ModelAdmissionStatus

    if batch_result.final_status not in (
        ModelAdmissionStatus.CANDIDATE,
        ModelAdmissionStatus.SANDBOX_ONLY,
    ):
        return None
    tier = suggest_admission_tier(entry, batch_result)
    code_cap = "code" in entry.capabilities
    coding_passed = any(r.level.value == "coding_fixture" and r.passed for r in batch_result.results)
    return AdmissionOverlay(
        backend_key=map_model_to_backend_key(entry.model_id),
        provider="cloudflare",
        model_id=entry.model_id,
        tier="floor" if code_cap and coding_passed else tier,
        private_code_allowed=bool(code_cap and coding_passed),
        evidence_refs=[f"probe:{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"],
        latency_ms=latency_ms,
    )
