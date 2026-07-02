"""Weekly inventory diff for CF / Google (CF-G-6)."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    from config.db_config import get_lima_data_dir

    return Path(get_lima_data_dir()) if get_lima_data_dir() else Path("data")


def extract_model_ids(inventory: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in inventory.get("models") or []:
        if isinstance(item, dict):
            mid = str(item.get("model_id") or "").strip()
            if mid:
                ids.add(mid)
    return ids


def diff_model_sets(old_ids: set[str], new_ids: set[str]) -> dict[str, Any]:
    return {
        "added": sorted(new_ids - old_ids),
        "removed": sorted(old_ids - new_ids),
        "old_count": len(old_ids),
        "new_count": len(new_ids),
    }


def diff_inventories(
    old_inventory: dict[str, Any] | None,
    new_inventory: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not new_inventory:
        return None
    provider = str(new_inventory.get("provider") or "unknown")
    if not old_inventory:
        return {
            "provider": provider,
            "baseline_date": None,
            "added": [],
            "removed": [],
            "old_count": 0,
            "new_count": len(extract_model_ids(new_inventory)),
            "status": "no_baseline",
        }
    old_ids = extract_model_ids(old_inventory)
    new_ids = extract_model_ids(new_inventory)
    result = diff_model_sets(old_ids, new_ids)
    result["provider"] = provider
    result["baseline_date"] = old_inventory.get("snapshot_date")
    result["status"] = "ok"
    return result


def _snapshot_dir() -> Path:
    return data_dir() / "inventory_snapshots"


def snapshot_path(provider: str, day: date) -> Path:
    safe = provider.replace("/", "_").replace("\\", "_")
    return _snapshot_dir() / f"{safe}_{day:%Y%m%d}.json"


def save_daily_snapshot(inventory: dict[str, Any], *, day: date | None = None) -> Path:
    """Persist one snapshot per provider per calendar day."""
    when = day or date.today()
    provider = str(inventory.get("provider") or "unknown")
    payload = dict(inventory)
    payload["snapshot_date"] = when.isoformat()
    path = snapshot_path(provider, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse_snapshot_date(path: Path) -> date | None:
    stem = path.stem
    if len(stem) < 9 or "_" not in stem:
        return None
    suffix = stem.rsplit("_", 1)[-1]
    try:
        return datetime.strptime(suffix, "%Y%m%d").date()
    except ValueError:
        return None


def find_week_baseline_inventory(
    provider: str,
    *,
    min_age_days: int = 7,
    today: date | None = None,
) -> dict[str, Any] | None:
    """Load inventory snapshot from at least ``min_age_days`` ago (closest match)."""
    snap_dir = _snapshot_dir()
    if not snap_dir.is_dir():
        return None
    safe = provider.replace("/", "_").replace("\\", "_")
    paths = sorted(snap_dir.glob(f"{safe}_*.json"))
    if not paths:
        return None

    now = today or date.today()
    target = now - timedelta(days=min_age_days)
    candidates: list[tuple[date, Path]] = []
    for path in paths:
        snap_day = _parse_snapshot_date(path)
        if snap_day is not None:
            candidates.append((snap_day, path))
    if not candidates:
        return None

    older = [(d, p) for d, p in candidates if d <= target]
    chosen = max(older, key=lambda x: x[0]) if older else min(candidates, key=lambda x: x[0])
    if not older and (now - chosen[0]).days < 1:
        return None
    return json.loads(chosen[1].read_text(encoding="utf-8"))


def compute_weekly_diff(
    cf_inventory: dict[str, Any] | None,
    google_inventory: dict[str, Any] | None,
    *,
    min_age_days: int = 7,
    today: date | None = None,
) -> dict[str, Any]:
    """Compare current inventories to week-old snapshots; persist summary JSON."""
    now = today or date.today()
    cf_diff = None
    google_diff = None
    if cf_inventory:
        save_daily_snapshot(cf_inventory, day=now)
        cf_base = find_week_baseline_inventory("cloudflare", min_age_days=min_age_days, today=now)
        cf_diff = diff_inventories(cf_base, cf_inventory)
    if google_inventory:
        save_daily_snapshot(google_inventory, day=now)
        google_base = find_week_baseline_inventory("google", min_age_days=min_age_days, today=now)
        google_diff = diff_inventories(google_base, google_inventory)

    payload = {
        "computed_at": time.time(),
        "computed_date": now.isoformat(),
        "min_age_days": min_age_days,
        "cloudflare": cf_diff,
        "google": google_diff,
    }
    out_path = data_dir() / "inventory_weekly_diff.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def format_weekly_diff_digest(
    diff_data: dict[str, Any] | None,
    *,
    max_items: int = 5,
) -> str:
    """One-line excerpt for daily operator reports."""
    if not diff_data:
        return "Inventory 7d: (unavailable)"

    parts: list[str] = []
    for key, label in (("cloudflare", "CF"), ("google", "Google")):
        block = diff_data.get(key)
        if not block:
            continue
        status = block.get("status")
        if status == "no_baseline":
            parts.append(f"{label}: collecting baseline")
            continue
        added = block.get("added") or []
        removed = block.get("removed") or []
        if not added and not removed:
            parts.append(f"{label}: no changes")
            continue
        snippet = ", ".join(f"`{m}`" for m in added[:max_items])
        if len(added) > max_items:
            snippet += f" +{len(added) - max_items} more"
        tail = f" +{len(added)}" if added else ""
        if removed:
            tail += f" -{len(removed)}"
        if added:
            parts.append(f"{label}{tail}: {snippet}")
        else:
            parts.append(f"{label}{tail}")

    return "Inventory 7d: " + ("; ".join(parts) if parts else "(none)")


def load_weekly_diff() -> dict[str, Any] | None:
    path = data_dir() / "inventory_weekly_diff.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
