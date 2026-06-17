"""Lightweight routing MLP model (pure Python, zero dependencies).

Architecture: 12 → 32 → N_backends
Trained incrementally with online learning.
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import dataclass, field

from routing_ml.feature_extractor import N_FEATURES


@dataclass
class RoutingModel:
    """Two-layer MLP for backend score prediction. Pure Python, no numpy."""

    w1: list[list[float]]  # N_FEATURES x HIDDEN
    b1: list[float]  # HIDDEN
    w2: list[list[float]]  # HIDDEN x N_BACKENDS
    b2: list[float]  # N_BACKENDS
    backend_names: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    n_updates: int = 0
    hidden_size: int = 32

    def predict(self, features: list[float]) -> list[float]:
        """Forward pass. features: list of N_FEATURES floats.
        Returns: list of N_BACKENDS scores in [0,1]."""
        # Layer 1: ReLU
        h = []
        for j in range(self.hidden_size):
            s = self.b1[j]
            for i in range(N_FEATURES):
                s += features[i] * self.w1[i][j]
            h.append(max(0.0, s))

        # Layer 2: sigmoid
        out = []
        for k in range(len(self.backend_names)):
            s = self.b2[k]
            for j in range(self.hidden_size):
                s += h[j] * self.w2[j][k]
            out.append(1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, s)))))

        return out

    def predict_topk(self, features: list[float], k: int = 3) -> list[tuple[str, float]]:
        """Return top-K backends with scores."""
        scores = self.predict(features)
        indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
        return [(self.backend_names[i], s) for i, s in indexed if s > 0.05]

    def to_dict(self) -> dict:
        return {
            "w1": self.w1,
            "b1": self.b1,
            "w2": self.w2,
            "b2": self.b2,
            "backend_names": self.backend_names,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "n_updates": self.n_updates,
            "hidden_size": self.hidden_size,
            "n_features": N_FEATURES,
            "n_backends": len(self.backend_names),
        }

    @classmethod
    def from_dict(cls, data: dict) -> RoutingModel:
        return cls(
            w1=data["w1"],
            b1=data["b1"],
            w2=data["w2"],
            b2=data["b2"],
            backend_names=data.get("backend_names", []),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
            n_updates=data.get("n_updates", 0),
            hidden_size=data.get("hidden_size", 32),
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: str) -> RoutingModel | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None


def _rand(rng: random.Random, scale: float) -> float:
    return rng.gauss(0, scale)


def create_model(
    backend_names: list[str],
    hidden_size: int = 32,
    seed: int = 42,
) -> RoutingModel:
    """Create a new model with Xavier initialization."""
    rng = random.Random(seed)
    n_out = len(backend_names)
    s1 = math.sqrt(2.0 / (N_FEATURES + hidden_size))
    s2 = math.sqrt(2.0 / (hidden_size + n_out))

    w1 = [[_rand(rng, s1) for _ in range(hidden_size)] for _ in range(N_FEATURES)]
    b1 = [0.0] * hidden_size
    w2 = [[_rand(rng, s2) for _ in range(n_out)] for _ in range(hidden_size)]
    b2 = [0.0] * n_out

    return RoutingModel(w1=w1, b1=b1, w2=w2, b2=b2, backend_names=list(backend_names), hidden_size=hidden_size)


def _forward(model: RoutingModel, features: list[float]) -> tuple[list[float], list[float], list[float], list[float]]:
    """Forward pass returning all intermediates for backprop."""
    H, N, K = model.hidden_size, N_FEATURES, len(model.backend_names)
    h_pre = [model.b1[j] + sum(features[i] * model.w1[i][j] for i in range(N)) for j in range(H)]
    h = [max(0.0, v) for v in h_pre]
    out_pre = [model.b2[k] + sum(h[j] * model.w2[j][k] for j in range(H)) for k in range(K)]
    pred = [1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, v)))) for v in out_pre]
    return h_pre, h, out_pre, pred


def _backward(
    model: RoutingModel,
    features: list[float],
    h_pre: list[float],
    h: list[float],
    pred: list[float],
    target: list[float],
) -> tuple[float, list[list[float]], list[float], list[list[float]], list[float]]:
    """Compute gradients via backprop. Returns (loss, d_w1, d_b1, d_w2, d_b2)."""
    H, N, K = model.hidden_size, N_FEATURES, len(model.backend_names)
    eps = 1e-7
    loss = (
        -sum(
            target[k] * math.log(max(eps, min(1 - eps, pred[k])))
            + (1 - target[k]) * math.log(max(eps, min(1 - eps, 1 - pred[k])))
            for k in range(K)
        )
        / K
    )
    d_out = [pred[k] - target[k] for k in range(K)]
    d_w2 = [[h[j] * d_out[k] for k in range(K)] for j in range(H)]
    d_h = [sum(d_out[k] * model.w2[j][k] for k in range(K)) * (1.0 if h_pre[j] > 0 else 0.0) for j in range(H)]
    d_w1 = [[features[i] * d_h[j] for j in range(H)] for i in range(N)]
    return loss, d_w1, list(d_h), d_w2, list(d_out)


def _apply_gradients(model: RoutingModel, lr: float, d_w1: list, d_b1: list, d_w2: list, d_b2: list) -> None:
    """Apply gradient updates to model weights."""
    H, N, K = model.hidden_size, N_FEATURES, len(model.backend_names)
    for i in range(N):
        for j in range(H):
            model.w1[i][j] -= lr * d_w1[i][j]
    for j in range(H):
        model.b1[j] -= lr * d_b1[j]
    for j in range(H):
        for k in range(K):
            model.w2[j][k] -= lr * d_w2[j][k]
    for k in range(K):
        model.b2[k] -= lr * d_b2[k]


def train_step(
    model: RoutingModel,
    features: list[float],
    target: list[float],
    lr: float = 0.001,
) -> float:
    """Single training step with backprop. Returns loss."""
    h_pre, h, out_pre, pred = _forward(model, features)
    loss, d_w1, d_b1, d_w2, d_b2 = _backward(model, features, h_pre, h, pred, target)
    _apply_gradients(model, lr, d_w1, d_b1, d_w2, d_b2)
    model.n_updates += 1
    model.updated_at = time.time()
    return loss
