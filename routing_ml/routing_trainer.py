"""Incremental training loop for the routing model (pure Python).

Trains on recent data, persists model to disk, and provides hot-reload.
Every N requests (default 1000), triggers a training round.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from routing_ml.routing_model import (
    RoutingModel,
    create_model,
    train_step,
)
from routing_ml.training_data import (
    build_training_samples,
    load_coding_scores,
    load_weight_history,
)

_log = logging.getLogger(__name__)

MODEL_PATH = os.environ.get("LIMA_ROUTING_MODEL_PATH", "data/routing_model.json")

TRAIN_INTERVAL = 1000
TRAIN_EPOCHS = 5
TRAIN_LR = 0.001
MIN_SAMPLES = 3


@dataclass
class TrainingState:
    request_count: int = 0
    last_train_time: float = 0.0
    last_loss: float = 0.0
    total_rounds: int = 0


_state = TrainingState()
_model: RoutingModel | None = None


def get_model() -> RoutingModel | None:
    """Get the current routing model (loads from disk if needed)."""
    global _model
    if _model is None:
        _model = RoutingModel.load(MODEL_PATH)
    return _model


def notify_request() -> None:
    """Call after each routing decision. Triggers training at threshold."""
    global _state
    _state.request_count += 1
    if _state.request_count >= TRAIN_INTERVAL:
        try_train()


def try_train() -> bool:
    """Attempt a training round. Returns True if training happened."""
    global _state, _model

    data_dir = os.path.dirname(MODEL_PATH) or "data"
    weight_history = load_weight_history(data_dir)
    coding_scores = load_coding_scores(data_dir)

    if not weight_history:
        _log.debug("routing_ml: no weight history, skipping training")
        return False

    all_backends = sorted(set(e["backend"] for e in weight_history))
    if len(all_backends) < 2:
        _log.debug("routing_ml: not enough backends (%d), skipping", len(all_backends))
        return False

    samples = build_training_samples(weight_history, all_backends, coding_scores)
    if len(samples) < MIN_SAMPLES:
        _log.debug("routing_ml: not enough samples (%d), skipping", len(samples))
        return False

    model = get_model()
    if model is None or set(model.backend_names) != set(all_backends):
        _log.info("routing_ml: creating new model for %d backends", len(all_backends))
        model = create_model(all_backends)
        _model = model

    # Train epochs
    import random

    losses = []
    for _ in range(TRAIN_EPOCHS):
        indices = list(range(len(samples)))
        random.shuffle(indices)
        for idx in indices:
            s = samples[idx]
            loss = train_step(model, s.features, s.target, lr=TRAIN_LR)
            losses.append(loss)

    avg_loss = sum(losses) / len(losses) if losses else 0.0
    _state.last_loss = avg_loss
    _state.last_train_time = time.time()
    _state.total_rounds += 1
    _state.request_count = 0

    try:
        model.save(MODEL_PATH)
        _log.info(
            "routing_ml: trained round=%d samples=%d loss=%.4f backends=%d",
            _state.total_rounds,
            len(samples),
            avg_loss,
            len(all_backends),
        )
    except OSError as exc:
        _log.warning("routing_ml: failed to save model: %s", exc)

    return True


def get_training_state() -> dict:
    """Return current training state for diagnostics."""
    return {
        "request_count": _state.request_count,
        "train_interval": TRAIN_INTERVAL,
        "last_loss": round(_state.last_loss, 4),
        "last_train_time": _state.last_train_time,
        "total_rounds": _state.total_rounds,
        "model_loaded": _model is not None,
        "model_path": MODEL_PATH,
    }


def force_train() -> dict:
    """Force an immediate training round."""
    _state.request_count = TRAIN_INTERVAL
    success = try_train()
    return {"trained": success, **get_training_state()}
