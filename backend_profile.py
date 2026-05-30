"""Backend Profile — performance intelligence for each backend.

Tracks latency, success rate, scenario suitability, and cost per backend.
Persists to SQLite for restart survival.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("LIMA_BACKEND_PROFILE_DB", "data/backend_profiles.db")
_lock = threading.Lock()


# ─── Data Model ───────────────────────────────────────────────────────────

@dataclass
class BackendProfile:
    name: str
    # Performance (sliding window)
    latencies: list[float] = field(default_factory=list)  # recent 50
    successes: int = 0
    failures: int = 0
    response_lengths: list[int] = field(default_factory=list)  # recent 20
    # Scenario fit
    scenario_successes: dict[str, int] = field(default_factory=dict)
    scenario_failures: dict[str, int] = field(default_factory=dict)
    # Metadata
    total_requests: int = 0
    last_updated: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total > 0 else 0.5

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    @property
    def avg_response_len(self) -> int:
        return int(sum(self.response_lengths) / len(self.response_lengths)) if self.response_lengths else 0

    @property
    def best_scenarios(self) -> list[str]:
        scored = []
        for s, ok in self.scenario_successes.items():
            fail = self.scenario_failures.get(s, 0)
            total = ok + fail
            if total >= 3:
                scored.append((s, ok / total))
        scored.sort(key=lambda x: -x[1])
        return [s for s, _ in scored[:3]]

    @property
    def worst_scenarios(self) -> list[str]:
        scored = []
        for s, ok in self.scenario_successes.items():
            fail = self.scenario_failures.get(s, 0)
            total = ok + fail
            if total >= 3:
                scored.append((s, ok / total))
        scored.sort(key=lambda x: x[1])
        return [s for s, _ in scored[:3] if _ < 0.5]

    def composite_score(self) -> float:
        """0-100 score combining success rate, latency, and response quality."""
        sr = self.success_rate * 40  # 0-40
        if self.latencies:
            avg = self.avg_latency_ms
            latency_score = max(0, 40 - (avg / 5000) * 40)  # 0-40, penalize slow
        else:
            latency_score = 20  # unknown = middle
        if self.response_lengths:
            avg_len = self.avg_response_len
            quality_score = min(20, avg_len / 50)  # 0-20, reward longer responses
        else:
            quality_score = 10
        return round(sr + latency_score + quality_score, 1)


# ─── In-Memory Store ──────────────────────────────────────────────────────

_profiles: dict[str, BackendProfile] = {}


def get_profile(backend: str) -> BackendProfile:
    """Get or create profile for a backend."""
    with _lock:
        return _get_profile(backend)


def _get_profile(backend: str) -> BackendProfile:
    """Internal: get or create profile (caller must hold _lock)."""
    if backend not in _profiles:
        _profiles[backend] = BackendProfile(name=backend)
    return _profiles[backend]


def record_request(
    backend: str,
    latency_ms: float,
    success: bool,
    scenario: str = "",
    response_len: int = 0,
) -> None:
    """Update profile after a request completes."""
    with _lock:
        profile = _get_profile(backend)
        profile.total_requests += 1
        profile.last_updated = time.time()

        # Latency (sliding window, max 50)
        profile.latencies.append(latency_ms)
        if len(profile.latencies) > 50:
            profile.latencies = profile.latencies[-50:]

        # Success/failure
        if success:
            profile.successes += 1
        else:
            profile.failures += 1

        # Response length (sliding window, max 20)
        if response_len > 0:
            profile.response_lengths.append(response_len)
            if len(profile.response_lengths) > 20:
                profile.response_lengths = profile.response_lengths[-20:]

        # Scenario tracking
        if scenario:
            if success:
                profile.scenario_successes[scenario] = profile.scenario_successes.get(scenario, 0) + 1
            else:
                profile.scenario_failures[scenario] = profile.scenario_failures.get(scenario, 0) + 1

        profile.last_updated = time.time()


def get_top_backends(scenario: str = "", n: int = 5) -> list[str]:
    """Get top N backends by composite score, optionally filtered by scenario."""
    with _lock:
        candidates = []
        for name, profile in _profiles.items():
            score = profile.composite_score()
            if scenario and profile.scenario_successes:
                scenario_total = profile.scenario_successes.get(scenario, 0) + profile.scenario_failures.get(scenario, 0)
                if scenario_total >= 3:
                    scenario_rate = profile.scenario_successes.get(scenario, 0) / scenario_total
                    score *= (0.5 + 0.5 * scenario_rate)
            candidates.append((name, score))
        candidates.sort(key=lambda x: -x[1])
        return [name for name, _ in candidates[:n]]


def get_backend_summary() -> dict[str, dict]:
    """Get summary stats for all backends."""
    with _lock:
        result = {}
        for name, profile in _profiles.items():
            result[name] = {
                "score": profile.composite_score(),
                "success_rate": round(profile.success_rate, 3),
                "avg_latency_ms": round(profile.avg_latency_ms, 0),
                "total_requests": profile.total_requests,
                "best_scenarios": profile.best_scenarios,
            }
        return result


# ─── Persistence ───────────────────────────────────────────────────────────

def save_profiles() -> None:
    """Persist all profiles to SQLite."""
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backend_profiles (
                    name TEXT PRIMARY KEY,
                    latencies TEXT,
                    successes INTEGER,
                    failures INTEGER,
                    response_lengths TEXT,
                    scenario_successes TEXT,
                    scenario_failures TEXT,
                    total_requests INTEGER,
                    last_updated REAL
                )
            """)
            for name, profile in _profiles.items():
                conn.execute("""
                    INSERT OR REPLACE INTO backend_profiles
                    (name, latencies, successes, failures, response_lengths,
                     scenario_successes, scenario_failures, total_requests, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    json.dumps(profile.latencies),
                    profile.successes,
                    profile.failures,
                    json.dumps(profile.response_lengths),
                    json.dumps(profile.scenario_successes),
                    json.dumps(profile.scenario_failures),
                    profile.total_requests,
                    profile.last_updated,
                ))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to save backend profiles: %s", exc)


def load_profiles() -> int:
    """Load profiles from SQLite. Returns count of loaded profiles."""
    global _profiles
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cursor = conn.execute("SELECT * FROM backend_profiles")
        count = 0
        for row in cursor:
            name = row[0]
            profile = BackendProfile(
                name=name,
                latencies=json.loads(row[1]) if row[1] else [],
                successes=row[2] or 0,
                failures=row[3] or 0,
                response_lengths=json.loads(row[4]) if row[4] else [],
                scenario_successes=json.loads(row[5]) if row[5] else {},
                scenario_failures=json.loads(row[6]) if row[6] else {},
                total_requests=row[7] or 0,
                last_updated=row[8] or 0.0,
            )
            _profiles[name] = profile
            count += 1
        conn.close()
        logger.info("Loaded %d backend profiles from %s", count, DB_PATH)
        return count
    except Exception as exc:
        logger.warning("Failed to load backend profiles: %s", exc)
        return 0


def save_on_interval(interval_sec: int = 300) -> None:
    """Background thread that saves profiles periodically."""
    import threading

    def _save_loop():
        while True:
            time.sleep(interval_sec)
            try:
                save_profiles()
            except Exception as exc:
                _log.debug("backend_profile.py: {}", type(exc).__name__)

    t = threading.Thread(target=_save_loop, daemon=True)
    t.start()
    logger.info("Backend profile auto-save started (interval=%ds)", interval_sec)

