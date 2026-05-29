"""Skill Crystallization — GenericAgent-inspired route caching as skills.

When a routing decision succeeds, crystallize it as a reusable "skill":
- Key: normalized request pattern (scenario + complexity + keywords)
- Value: proven backend + latency + success context
- On similar future requests, recall skill directly (skip re-decision)
- Skills decay over time if not reused (TTL-based expiry)
"""

import hashlib
import time
from dataclasses import dataclass, asdict


@dataclass
class RoutingSkill:
    """A crystallized successful routing decision."""

    skill_key: str
    backend: str
    scenario: str
    complexity_score: int
    latency_ms: int
    created_at: float
    last_used: float
    use_count: int = 0
    weight: float = 1.0  # Cognee EMA feedback weight
    alpha: float = 0.1

    @property
    def is_expired(self) -> bool:
        return self.weight < 0.1

    def on_success(self) -> None:
        """EMA weight growth on successful reuse."""
        self.weight = min(3.0, self.weight * (1 + self.alpha * 0.5))

    def on_failure(self) -> None:
        """EMA weight decay on failure."""
        self.weight *= (1 - self.alpha)


class SkillStore:
    """In-memory store for routing skills."""

    def __init__(self, max_skills: int = 200) -> None:
        self._skills: dict[str, RoutingSkill] = {}
        self._max = max_skills
        self._last_recalled: RoutingSkill | None = None

    def crystallize(
        self,
        messages: list[dict],
        scenario: str,
        backend: str,
        complexity_score: int,
        latency_ms: int,
    ) -> RoutingSkill:
        """Crystallize a successful routing decision into a skill."""
        key = self._compute_key(messages, scenario)
        now = time.time()

        skill = RoutingSkill(
            skill_key=key,
            backend=backend,
            scenario=scenario,
            complexity_score=complexity_score,
            latency_ms=latency_ms,
            created_at=now,
            last_used=now,
            use_count=1,
        )
        self._skills[key] = skill
        self._evict_if_needed()
        return skill

    def recall(self, messages: list[dict], scenario: str) -> RoutingSkill | None:
        """Try to recall a matching skill for this request.

        NOTE: on_success() is NOT called here — it's deferred until the
        backend actually succeeds. Call confirm_success() after execution.
        """
        key = self._compute_key(messages, scenario)
        skill = self._skills.get(key)
        if skill and not skill.is_expired:
            skill.last_used = time.time()
            skill.use_count += 1
            self._last_recalled = skill
            return skill
        if skill and skill.is_expired:
            del self._skills[key]
        return None

    def confirm_success(self) -> None:
        """Confirm the last recalled skill succeeded — now apply on_success."""
        if self._last_recalled:
            self._last_recalled.on_success()
            self._last_recalled = None

    def on_failure(self, scenario: str = "") -> None:
        """Penalize the last recalled skill on failure."""
        if self._last_recalled:
            self._last_recalled.on_failure()
            self._last_recalled = None

    def _compute_key(self, messages: list[dict], scenario: str) -> str:
        """Compute a normalized key from request pattern."""
        user_text = ""
        for msg in messages:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                user_text += msg["content"]

        keywords = sorted(set(user_text.lower().split()[:20]))
        raw = f"{scenario}:{' '.join(keywords)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _evict_if_needed(self) -> None:
        """Evict expired or least-used skills when over capacity."""
        if len(self._skills) <= self._max:
            return
        expired = [k for k, v in self._skills.items() if v.is_expired]
        for k in expired:
            del self._skills[k]
        if len(self._skills) > self._max:
            by_use = sorted(self._skills.items(), key=lambda x: x[1].use_count)
            for k, _ in by_use[: len(self._skills) - self._max]:
                del self._skills[k]

    @property
    def skill_count(self) -> int:
        return len(self._skills)


# Singleton
_instance: SkillStore | None = None


def get_skill_store() -> SkillStore:
    global _instance
    if _instance is None:
        _instance = SkillStore()
    return _instance
