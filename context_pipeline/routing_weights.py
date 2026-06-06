"""Routing weights — Solvita-inspired experience-driven weight learning.

Backend routing weights that learn from success/failure history:
- Each backend has a weight per scenario (coding/chat/vision)
- Success → weight increases
- Failure → weight decreases
- Weights influence backend selection priority
- No LLM retraining needed — pure statistical learning
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_runtime_data_dir = os.environ.get("LIMA_DATA_DIR", ".lima-data")
_default_path = os.path.join(_runtime_data_dir, "lima_routing_weights.json")
WEIGHTS_PATH = Path(os.environ.get("LIMA_WEIGHTS_PATH", _default_path))
SEED_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "data" / "lima_routing_weights.json"


@dataclass
class BackendWeight:
    """Weight record for a single backend+scenario combination."""

    backend: str
    scenario: str
    weight: float = 1.0
    successes: int = 0
    failures: int = 0
    last_updated: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        if total == 0:
            return 0.5
        return self.successes / total


class RoutingWeights:
    """Experience-driven routing weight manager."""

    def __init__(self) -> None:
        self._weights: dict[str, BackendWeight] = {}
        self._load()

    def _key(self, backend: str, scenario: str) -> str:
        return f"{backend}:{scenario}"

    def get_weight(self, backend: str, scenario: str) -> float:
        key = self._key(backend, scenario)
        if key in self._weights:
            return self._weights[key].weight
        return 1.0

    def record_success(self, backend: str, scenario: str) -> None:
        key = self._key(backend, scenario)
        w = self._weights.setdefault(
            key, BackendWeight(backend=backend, scenario=scenario)
        )
        # GRPO: calculate baseline BEFORE recording this event
        baseline = self._scenario_baseline(scenario)
        w.successes += 1
        advantage = 1.0 - baseline
        lr = 0.08
        delta = max(-0.15, min(0.15, advantage * lr))
        w.weight = min(2.0, max(0.1, w.weight + delta))
        w.last_updated = time.time()
        self._save()

    def record_failure(self, backend: str, scenario: str) -> None:
        key = self._key(backend, scenario)
        w = self._weights.setdefault(
            key, BackendWeight(backend=backend, scenario=scenario)
        )
        # GRPO: calculate baseline BEFORE recording this event
        baseline = self._scenario_baseline(scenario)
        w.failures += 1
        advantage = 0.0 - baseline
        lr = 0.08
        delta = max(-0.15, min(0.15, advantage * lr))
        w.weight = min(2.0, max(0.1, w.weight + delta))
        w.last_updated = time.time()
        self._save()

    def _scenario_baseline(self, scenario: str) -> float:
        """Average success rate across all backends for this scenario."""
        rates = []
        for key, w in self._weights.items():
            if key.endswith(f":{scenario}"):
                rates.append(w.success_rate)
        return sum(rates) / len(rates) if rates else 0.5

    def rank_backends(self, backends: list[str], scenario: str) -> list[str]:
        """Rank backends by learned weight for a given scenario."""
        scored = []
        for b in backends:
            w = self.get_weight(b, scenario)
            scored.append((w, b))
        scored.sort(key=lambda x: -x[0])
        return [b for _, b in scored]

    def get_stats(self, backend: str, scenario: str) -> dict:
        """Get stats for a backend+scenario combination."""
        key = self._key(backend, scenario)
        if key not in self._weights:
            return {"weight": 1.0, "successes": 0, "failures": 0, "success_rate": 0.5}
        w = self._weights[key]
        return {
            "weight": w.weight,
            "successes": w.successes,
            "failures": w.failures,
            "success_rate": w.success_rate,
        }

    def _load(self) -> None:
        load_path = WEIGHTS_PATH if WEIGHTS_PATH.exists() else SEED_WEIGHTS_PATH
        if load_path.exists():
            try:
                data = json.loads(load_path.read_text(encoding="utf-8"))
                for key, d in data.items():
                    self._weights[key] = BackendWeight(**d)
            except (json.JSONDecodeError, TypeError):
                pass

    def _save(self) -> None:
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {k: asdict(v) for k, v in self._weights.items()}
        WEIGHTS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# Singleton instance
_instance: RoutingWeights | None = None


def get_routing_weights() -> RoutingWeights:
    global _instance
    if _instance is None:
        _instance = RoutingWeights()
    return _instance
