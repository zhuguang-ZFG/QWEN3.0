"""Lightweight routing MLP model (pure NumPy, no PyTorch dependency).

Architecture: 12 → 32 → N_backends
Trained incrementally with online learning.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import numpy as np

from routing_ml.feature_extractor import N_FEATURES


@dataclass
class RoutingModel:
    """Two-layer MLP for backend score prediction."""
    weights1: np.ndarray  # shape (N_FEATURES, HIDDEN)
    bias1: np.ndarray     # shape (HIDDEN,)
    weights2: np.ndarray  # shape (HIDDEN, N_BACKENDS)
    bias2: np.ndarray     # shape (N_BACKENDS,)
    backend_names: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    n_updates: int = 0

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Forward pass. Features shape: (N_FEATURES,) or (BATCH, N_FEATURES).
        Returns backend scores shape: (N_BACKENDS,) or (BATCH, N_BACKENDS)."""
        x = features
        if x.ndim == 1:
            x = x[np.newaxis, :]

        h = np.maximum(0, x @ self.weights1 + self.bias1)  # ReLU
        out = h @ self.weights2 + self.bias2               # linear
        scores = 1.0 / (1.0 + np.exp(-np.clip(out, -10, 10)))  # sigmoid → [0,1]

        return scores[0] if features.ndim == 1 else scores

    def predict_topk(self, features: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        """Return top-K backends with scores."""
        scores = self.predict(features)
        if not self.backend_names:
            return []
        indices = np.argsort(-scores)[:k]
        return [(self.backend_names[i], float(scores[i])) for i in indices if scores[i] > 0.05]

    def to_dict(self) -> dict:
        return {
            "weights1": self.weights1.tolist(),
            "bias1": self.bias1.tolist(),
            "weights2": self.weights2.tolist(),
            "bias2": self.bias2.tolist(),
            "backend_names": self.backend_names,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "n_updates": self.n_updates,
            "n_features": N_FEATURES,
            "hidden_size": self.weights1.shape[1],
            "n_backends": len(self.backend_names),
        }

    @classmethod
    def from_dict(cls, data: dict) -> RoutingModel:
        return cls(
            weights1=np.array(data["weights1"], dtype=np.float32),
            bias1=np.array(data["bias1"], dtype=np.float32),
            weights2=np.array(data["weights2"], dtype=np.float32),
            bias2=np.array(data["bias2"], dtype=np.float32),
            backend_names=data.get("backend_names", []),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
            n_updates=data.get("n_updates", 0),
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> RoutingModel | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None


def create_model(
    backend_names: list[str],
    hidden_size: int = 32,
    seed: int = 42,
) -> RoutingModel:
    """Create a new model with Xavier initialization."""
    rng = np.random.RandomState(seed)
    n_out = len(backend_names)

    # Xavier init
    s1 = np.sqrt(2.0 / (N_FEATURES + hidden_size))
    s2 = np.sqrt(2.0 / (hidden_size + n_out))

    return RoutingModel(
        weights1=rng.randn(N_FEATURES, hidden_size).astype(np.float32) * s1,
        bias1=np.zeros(hidden_size, dtype=np.float32),
        weights2=rng.randn(hidden_size, n_out).astype(np.float32) * s2,
        bias2=np.zeros(n_out, dtype=np.float32),
        backend_names=list(backend_names),
    )


def cross_entropy_loss(pred: np.ndarray, target: np.ndarray) -> float:
    """Binary cross-entropy for multi-label prediction."""
    eps = 1e-7
    clipped = np.clip(pred, eps, 1 - eps)
    return -np.mean(
        target * np.log(clipped) + (1 - target) * np.log(1 - clipped)
    )


def train_step(
    model: RoutingModel,
    features: np.ndarray,
    targets: np.ndarray,
    lr: float = 0.001,
) -> float:
    """Single training step with backpropagation. Returns loss."""
    batch = features
    if batch.ndim == 1:
        batch = batch[np.newaxis, :]
    target = targets
    if target.ndim == 1:
        target = target[np.newaxis, :]

    batch_size = batch.shape[0]

    # Forward
    h_pre = batch @ model.weights1 + model.bias1
    h = np.maximum(0, h_pre)  # ReLU
    out_pre = h @ model.weights2 + model.bias2
    pred = 1.0 / (1.0 + np.exp(-np.clip(out_pre, -10, 10)))  # sigmoid

    # Loss
    loss = cross_entropy_loss(pred, target)

    # Backward
    d_out = (pred - target) / batch_size  # d(sigmoid)/d(out) simplified
    d_weights2 = h.T @ d_out
    d_bias2 = np.mean(d_out, axis=0)

    d_h = d_out @ model.weights2.T
    d_h[h_pre <= 0] = 0  # ReLU grad

    d_weights1 = batch.T @ d_h
    d_bias1 = np.mean(d_h, axis=0)

    # Update
    model.weights1 -= lr * d_weights1
    model.bias1 -= lr * d_bias1
    model.weights2 -= lr * d_weights2
    model.bias2 -= lr * d_bias2
    model.n_updates += 1
    model.updated_at = time.time()

    return float(loss)
