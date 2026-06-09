"""In-memory profile store with SQLite-friendly boundaries."""

from __future__ import annotations

from copy import deepcopy
import threading

from .schemas import DeviceProfile

DEFAULT_PROFILE = DeviceProfile(
    profile_id="dlc-p1-default",
    model="draw-line-control-p1",
)


class DeviceProfileStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._profiles: dict[str, DeviceProfile] = {DEFAULT_PROFILE.profile_id: DEFAULT_PROFILE}
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._profiles = {DEFAULT_PROFILE.profile_id: DEFAULT_PROFILE}

    def upsert(self, profile: DeviceProfile) -> None:
        with self._lock:
            self._profiles[profile.profile_id] = deepcopy(profile)

    def get(self, profile_id: str) -> DeviceProfile | None:
        with self._lock:
            profile = self._profiles.get(profile_id)
            return deepcopy(profile) if profile else None

    def get_or_default(self, profile_id: str | None = None) -> DeviceProfile:
        with self._lock:
            if profile_id and profile_id in self._profiles:
                return deepcopy(self._profiles[profile_id])
            return deepcopy(self._profiles[DEFAULT_PROFILE.profile_id])


profile_store = DeviceProfileStore()
