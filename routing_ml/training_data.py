"""Extract training data from existing routing weight and score files.

Reads:
  - data/lima_routing_weights.json → backend success/failure history
  - data/coding_backend_scores_full_*.json → backend quality scores
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass

from routing_ml.feature_extractor import N_FEATURES


@dataclass
class TrainingSample:
    features: list[float]  # length N_FEATURES
    target: list[float]  # length N_BACKENDS — 1.0 for chosen+success, 0.0 otherwise
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
        entries.append(
            {
                "backend": entry.get("backend", ""),
                "scenario": entry.get("scenario", ""),
                "weight": entry.get("weight", 1.0),
                "successes": entry.get("successes", 0),
                "failures": entry.get("failures", 0),
                "last_updated": entry.get("last_updated", 0),
            }
        )
    return entries


def load_coding_scores(data_dir: str = "data") -> dict[str, float]:
    """Load coding quality scores from the most recent score file.

    Handles both formats:
      - dict: {backend: {avg_score: N, ...}}
      - list: [{backend: str, score: N, ok: bool, ...}, ...]
    """
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


def _valid_entry(entry: dict, backend_idx: dict[str, int]) -> bool:
    backend = entry["backend"]
    if backend not in backend_idx:
        return False
    successes = entry.get("successes", 0)
    failures = entry.get("failures", 0)
    return successes + failures > 0


def _scenario_features(scenario: str) -> list[float]:
    features = [0.0] * N_FEATURES
    if scenario == "coding":
        features[0] = 0.5
        features[1] = 0.7
        features[10] = 1.0
    elif scenario == "chat":
        features[0] = 0.3
        features[1] = 0.1
        features[11] = 1.0
    else:
        features[0] = 0.4
        features[1] = 0.3
    return features


def _build_target(n_backends: int, backend_index: int, weight: float) -> list[float]:
    target = [0.0] * n_backends
    target[backend_index] = min(max(weight / 2.0, 0.0), 1.0)
    return target


def _append_negative_sample(
    samples: list[TrainingSample],
    features: list[float],
    target: list[float],
    backend_index: int,
    backend: str,
    scenario: str,
) -> None:
    neg_target = list(target)
    neg_target[backend_index] *= 0.3
    samples.append(
        TrainingSample(
            features=list(features),
            target=neg_target,
            backend=backend,
            success=False,
            scenario=scenario,
        )
    )


def build_training_samples(
    weight_history: list[dict],
    backend_names: list[str],
    coding_scores: dict[str, float] | None = None,
) -> list[TrainingSample]:
    """Convert weight history into training samples."""
    samples = []
    backend_idx = {name: i for i, name in enumerate(backend_names)}
    coding_scores = coding_scores or {}

    for entry in weight_history:
        if not _valid_entry(entry, backend_idx):
            continue

        backend = entry["backend"]
        scenario = entry.get("scenario", "chat")
        successes = entry.get("successes", 0)
        failures = entry.get("failures", 0)
        weight = entry.get("weight", 1.0)

        features = _scenario_features(scenario)
        target = _build_target(len(backend_names), backend_idx[backend], weight)

        samples.append(
            TrainingSample(
                features=features,
                target=target,
                backend=backend,
                success=successes > failures,
                scenario=scenario,
            )
        )

        if failures > 0:
            _append_negative_sample(samples, features, target, backend_idx[backend], backend, scenario)

    return samples


def samples_to_arrays(samples: list[TrainingSample]) -> tuple[list[list[float]], list[list[float]]]:
    """Convert samples to feature/target lists for batch training."""
    if not samples:
        return [], []
    return [s.features for s in samples], [s.target for s in samples]
