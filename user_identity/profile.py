"""User profile storage and management."""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROFILES_DIR = Path(os.environ.get("LIMA_PROFILES_DIR", "/tmp/lima_profiles"))


@dataclass
class UserProfile:
    """Persistent user identity."""

    session_id: str
    role: str = ""
    tech_level: str = "intermediate"  # beginner / intermediate / senior
    languages: list[str] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    ide_preference: str = ""
    request_count: int = 0
    last_seen: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _profile_path(session_id: str) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR / f"{session_id}.json"


def load_profile(session_id: str) -> UserProfile:
    """Load or create a user profile."""
    path = _profile_path(session_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return UserProfile.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass
    return UserProfile(session_id=session_id)


def save_profile(profile: UserProfile) -> None:
    """Persist user profile to disk."""
    profile.last_seen = time.time()
    path = _profile_path(profile.session_id)
    path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False), encoding="utf-8")
