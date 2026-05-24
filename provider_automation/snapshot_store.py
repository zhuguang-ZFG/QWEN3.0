"""Snapshot store for local provider catalog snapshots.

Stores snapshots as JSON files in data/provider_snapshots/.
Retains the most recent N snapshots per provider.
"""

from __future__ import annotations

import json
import os
import re
import time

from provider_automation.catalog import ProviderModelSnapshot


_DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "provider_snapshots",
)
MAX_SNAPSHOTS_PER_PROVIDER = 30


def _store_dir() -> str:
    return os.environ.get("LIMA_SNAPSHOT_DIR", _DEFAULT_DIR)


def _provider_slug(provider: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(provider))
    slug = slug.strip("._-")
    return slug or "provider"


def _snapshot_path(provider: str, timestamp: float) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime(timestamp))
    return os.path.join(_store_dir(), f"{_provider_slug(provider)}-{ts}.json")


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    for index in range(1, 1000):
        candidate = f"{base}-{index:02d}{ext}"
        if not os.path.exists(candidate):
            return candidate
    raise RuntimeError("unable to allocate unique snapshot path")


def save_snapshot(snapshot: ProviderModelSnapshot) -> str:
    """Save a provider snapshot to local storage. Returns the file path."""
    data = snapshot.to_dict()
    store_dir = _store_dir()
    os.makedirs(store_dir, exist_ok=True)
    path = _unique_path(_snapshot_path(snapshot.provider, snapshot.fetched_at or time.time()))
    data["_meta"] = {"saved_at": time.time(), "version": 1}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _prune_old_snapshots(snapshot.provider)
    return path


def load_snapshot(file_path: str) -> ProviderModelSnapshot | None:
    """Load a previously saved snapshot. Returns None on error."""
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        data.pop("_meta", None)
        return ProviderModelSnapshot.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return None


def load_latest_snapshot(provider: str) -> ProviderModelSnapshot | None:
    """Load the most recent snapshot for a provider. Returns None if absent."""
    snapshots = list_snapshots(provider, limit=1)
    if not snapshots:
        return None
    return load_snapshot(snapshots[0])


def list_snapshots(provider: str, limit: int = 10) -> list[str]:
    """List snapshot file paths newest first.

    If provider is empty, all provider snapshots are returned.
    """
    store_dir = _store_dir()
    if not os.path.isdir(store_dir):
        return []
    prefix = f"{_provider_slug(provider)}-" if provider else ""
    candidates = []
    for fname in os.listdir(store_dir):
        if fname.endswith(".json") and (not prefix or fname.startswith(prefix)):
            candidates.append(os.path.join(store_dir, fname))
    candidates.sort(reverse=True)
    return candidates[:limit]


def _prune_old_snapshots(provider: str) -> None:
    all_snapshots = list_snapshots(provider, limit=MAX_SNAPSHOTS_PER_PROVIDER * 2)
    if len(all_snapshots) > MAX_SNAPSHOTS_PER_PROVIDER:
        for path in all_snapshots[MAX_SNAPSHOTS_PER_PROVIDER:]:
            try:
                os.remove(path)
            except OSError:
                pass


def count_snapshots(provider: str) -> int:
    return len(list_snapshots(provider, limit=1000))


def reset_snapshots(provider: str = "") -> None:
    """Remove snapshots for one provider, or all snapshots when provider is empty."""
    for path in list_snapshots(provider, limit=1000):
        try:
            os.remove(path)
        except OSError:
            pass
