"""Incremental training loop for the routing model.

Trains on recent data, persists model to disk, and provides hot-reload.
Every N requests (default 1000), triggers a training round.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

import numpy as np

from routing_ml.feature_extractor import N_FEATURES
from routing_ml.routing_model import (
    RoutingModel,
    create_model,
    train_step,
)
from routing_ml.training_data import (
    build_training_samples,
    load_coding_scores,
    load_weight_history,
    samples_to_arrays,
)

_log = logging.getLogger(__name__)

MODEL_PATH = os.environ.get(
    "LIMA_ROUTING_MODEL_PATH", "data/routing_model.json"
)

# Training config
TRAIN_INTERVAL = 1000      # requests between training rounds
TRAIN_EPOCHS = 5           # epochs per round
TRAIN_LR = 0.001           # learning rate
MIN_SAMPLES = 3            # minimum samples to train


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
    """Call after each routing decision to increment the counter.
    Triggers training when threshold is reached."""
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

    # Determine backend list from weight history
    all_backends = sorted(set(e["backend"] for e in weight_history))
    if len(all_backends) < 2:
        _log.debug("routing_ml: not enough backends (%d), skipping", len(all_backends))
        return False

    # Build training data
    samples = build_training_samples(weight_history, all_backends, coding_scores)
    if len(samples) < MIN_SAMPLES:
        _log.debug("routing_ml: not enough samples (%d), skipping", len(samples))
        return False

    features, targets = samples_to_arrays(samples)

    # Load or create model
    model = get_model()
    if model is None or set(model.backend_names) != set(all_backends):
        _log.info("routing_ml: creating new model for %d backends", len(all_backends))
        model = create_model(all_backends)
        _model = model

    # Train
    losses = []
    for epoch in range(TRAIN_EPOCHS):
        # Shuffle
        perm = np.random.permutation(len(features))
        feat_shuffled = features[perm]
        target_shuffled = targets[perm]

        # Mini-batch training
        batch_size = min(32, len(features))
        for i in range(0, len(features), batch_size):
            batch_f = feat_shuffled[i:i + batch_size]
            batch_t = target_shuffled[i:i + batch_size]
            loss = train_step(model, batch_f, batch_t, lr=TRAIN_LR)
            losses.append(loss)

    avg_loss = float(np.mean(losses)) if losses else 0.0
    _state.last_loss = avg_loss
    _state.last_train_time = time.time()
    _state.total_rounds += 1
    _state.request_count = 0

    # Save
    try:
        model.save(MODEL_PATH)
        _log.info(
            "routing_ml: trained round=%d samples=%d loss=%.4f backends=%d",
            _state.total_rounds, len(samples), avg_loss, len(all_backends),
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
    """Force an immediate training round. Returns training result."""
    _state.request_count = TRAIN_INTERVAL
    success = try_train()
    return {
        "trained": success,
        **get_training_state(),
    }
