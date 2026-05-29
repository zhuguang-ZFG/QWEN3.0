"""Extract training data from existing routing weight and score files.

Reads:
  - data/lima_routing_weights.json → backend success/failure history
  - data/coding_backend_scores_full_*.json → backend quality scores
  - data/lima_routing_weights.json → learned weight history
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import numpy as np

from routing_ml.feature_extractor import N_FEATURES


@dataclass
class TrainingSample:
    features: np.ndarray  # shape (N_FEATURES,)
    target: np.ndarray   # shape (N_BACKENDS,) — 1.0 for chosen+success, 0.0 otherwise
    backend: str
    success: bool
    scenario: str


def load_weight_history(data_dir: str = "data") -> list[dict]:
    """Load all weight history entries from routing weights file."""
    path = os.path.join(data_dir, "lima_routing_weights.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    entries = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        entries.append({
            "backend": entry.get("backend", ""),
            "scenario": entry.get("scenario", ""),
            "weight": entry.get("weight", 1.0),
            "successes": entry.get("successes", 0),
            "failures": entry.get("failures", 0),
            "last_updated": entry.get("last_updated", 0),
        })
    return entries


def load_coding_scores(data_dir: str = "data") -> dict[str, float]:
    """Load coding quality scores from the most recent score file.

    Handles both formats:
      - dict: {backend: {avg_score: N, ...}}
      - list: [{backend: str, score: N, ok: bool, ...}, ...]
    """
    import glob
    pattern = os.path.join(data_dir, "coding_backend_scores_full_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return {}
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    scores: dict[str, list[float]] = {}
    if isinstance(data, dict):
        for backend, info in data.items():
            if isinstance(info, dict):
                avg = info.get("avg_score", info.get("avg", 0))
                scores.setdefault(backend, []).append(float(avg) / 100.0)
    elif isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            backend = entry.get("backend", "")
            score = entry.get("score", 0)
            if backend:
                scores.setdefault(backend, []).append(float(score) / 100.0)

    return {b: sum(v) / len(v) for b, v in scores.items() if v}


def build_training_samples(
    weight_history: list[dict],
    backend_names: list[str],
    coding_scores: dict[str, float] | None = None,
) -> list[TrainingSample]:
    """Convert weight history into training samples.

    Each entry becomes a sample with synthetic features based on scenario.
    Success entries get positive targets, failure entries get negative.
    """
    samples = []
    backend_idx = {name: i for i, name in enumerate(backend_names)}
    coding_scores = coding_scores or {}

    for entry in weight_history:
        backend = entry["backend"]
        if backend not in backend_idx:
            continue

        scenario = entry.get("scenario", "chat")
        successes = entry.get("successes", 0)
        failures = entry.get("failures", 0)
        total = successes + failures

        if total == 0:
            continue

        # Create synthetic features based on scenario
        features = np.zeros(N_FEATURES, dtype=np.float32)
        if scenario == "coding":
            features[0] = 0.5   # medium message length
            features[1] = 0.7   # high code ratio
            features[3] = 0.0   # no debug keyword
            features[10] = 1.0  # coding scenario
        elif scenario == "chat":
            features[0] = 0.3
            features[1] = 0.1
            features[11] = 1.0  # chat scenario
        else:
            features[0] = 0.4
            features[1] = 0.3

        # Target: weight-based success probability
        weight = entry.get("weight", 1.0)
        target = np.zeros(len(backend_names), dtype=np.float32)
        target[backend_idx[backend]] = min(max(weight / 2.0, 0.0), 1.0)

        samples.append(TrainingSample(
            features=features,
            target=target,
            backend=backend,
            success=successes > failures,
            scenario=scenario,
        ))

        # Augment: create a negative sample for each failure
        if failures > 0:
            neg_target = target.copy()
            neg_target[backend_idx[backend]] *= 0.3  # reduce score for failures
            samples.append(TrainingSample(
                features=features,
                target=neg_target,
                backend=backend,
                success=False,
                scenario=scenario,
            ))

    return samples


def samples_to_arrays(samples: list[TrainingSample]) -> tuple[np.ndarray, np.ndarray]:
    """Convert samples to feature/target arrays for batch training."""
    if not samples:
        return np.zeros((0, N_FEATURES), dtype=np.float32), np.zeros((0, 0), dtype=np.float32)
    features = np.stack([s.features for s in samples])
    targets = np.stack([s.target for s in samples])
    return features, targets
