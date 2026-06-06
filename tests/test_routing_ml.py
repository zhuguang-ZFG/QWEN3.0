"""Tests for ML routing prediction module (pure Python, no numpy)."""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routing_ml.feature_extractor import (
    N_FEATURES,
    FeatureVector,
    extract_features,
)
from routing_ml.routing_model import (
    RoutingModel,
    create_model,
    train_step,
)
from routing_ml.routing_trainer import (
    get_training_state,
    try_train,
)
from routing_ml.training_data import (
    build_training_samples,
    load_weight_history,
    samples_to_arrays,
)

# ─── Feature extractor tests ──────────────────────────────────────────


class TestFeatureExtractor:
    def test_feature_dimension(self):
        v = extract_features([{"role": "user", "content": "hello"}])
        assert len(v.features) == N_FEATURES
        assert N_FEATURES == 12

    def test_code_detection(self):
        messages = [{"role": "user", "content": "```python\nprint('hi')\n```\nfix this bug"}]
        v = extract_features(messages, scenario="coding")
        assert v.features[1] > 0.0  # code block ratio
        assert v.features[3] == 1.0  # has debug keyword ("fix")

    def test_chinese_detection(self):
        messages = [{"role": "user", "content": "帮我修复这个Python代码的bug"}]
        v = extract_features(messages)
        assert v.features[4] > 0.0  # chinese ratio

    def test_scenario_encoding(self):
        v_coding = extract_features([], scenario="coding")
        assert v_coding.features[10] == 1.0
        assert v_coding.features[11] == 0.0

        v_chat = extract_features([], scenario="chat")
        assert v_chat.features[10] == 0.0
        assert v_chat.features[11] == 1.0

    def test_health_map_encoding(self):
        health = {"groq_llama70b": "healthy", "longcat_lite": "dead"}
        v = extract_features([], health_map=health, top_backends=["groq_llama70b", "longcat_lite"])
        assert v.features[5] == 1.0
        assert v.features[6] == 0.0

    def test_metadata(self):
        v = extract_features([{"role": "user", "content": "hello"}], scenario="chat")
        assert "message_length" in v.metadata
        assert v.metadata["scenario"] == "chat"


# ─── Model tests ───────────────────────────────────────────────────────


class TestRoutingModel:
    def test_create_model(self):
        backends = ["groq_llama70b", "scnet_ds_flash", "github_gpt4o"]
        model = create_model(backends)
        assert len(model.w1) == N_FEATURES
        assert len(model.w1[0]) == 32
        assert len(model.w2) == 32
        assert len(model.w2[0]) == 3
        assert model.backend_names == backends

    def test_predict_shape(self):
        model = create_model(["a", "b", "c"])
        features = [0.1] * N_FEATURES
        scores = model.predict(features)
        assert len(scores) == 3
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_predict_topk(self):
        model = create_model(["a", "b", "c", "d"])
        features = [0.5] * N_FEATURES
        topk = model.predict_topk(features, k=2)
        assert len(topk) == 2
        assert all(isinstance(name, str) and isinstance(score, float) for name, score in topk)
        assert topk[0][1] >= topk[1][1]

    def test_serialize_roundtrip(self):
        model = create_model(["x", "y"])
        data = model.to_dict()
        restored = RoutingModel.from_dict(data)
        assert restored.backend_names == ["x", "y"]
        assert len(restored.w1) == len(model.w1)
        for i in range(len(model.w1)):
            for j in range(len(model.w1[i])):
                assert abs(restored.w1[i][j] - model.w1[i][j]) < 1e-10

    def test_save_load(self):
        model = create_model(["a", "b"])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = RoutingModel.load(path)
            assert loaded is not None
            assert loaded.backend_names == ["a", "b"]
        finally:
            os.unlink(path)

    def test_load_nonexistent(self):
        assert RoutingModel.load("/nonexistent/path.json") is None

    def test_train_step_reduces_loss(self):
        model = create_model(["a", "b"], seed=0)
        features = [0.5] * N_FEATURES
        target_success = [1.0, 0.0]
        target_fail = [0.0, 1.0]

        # Get initial loss
        pred_before = model.predict(features)
        loss_before = -(
            target_success[0] * _logsafe(pred_before[0]) +
            (1 - target_success[0]) * _logsafe(1 - pred_before[0]) +
            target_success[1] * _logsafe(pred_before[1]) +
            (1 - target_success[1]) * _logsafe(1 - pred_before[1])
        ) / 2

        # Train
        for _ in range(50):
            train_step(model, features, target_success, lr=0.01)

        pred_after = model.predict(features)
        loss_after = -(
            target_success[0] * _logsafe(pred_after[0]) +
            (1 - target_success[0]) * _logsafe(1 - pred_after[0]) +
            target_success[1] * _logsafe(pred_after[1]) +
            (1 - target_success[1]) * _logsafe(1 - pred_after[1])
        ) / 2

        assert loss_after < loss_before


def _logsafe(x: float) -> float:
    import math
    return math.log(max(1e-7, min(1.0 - 1e-7, x)))


# ─── Training data tests ──────────────────────────────────────────────


class TestTrainingData:
    def test_load_weight_history_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_weight_history(tmp)
            assert result == []

    def test_load_weight_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "scnet_ds_flash:coding": {
                    "backend": "scnet_ds_flash", "scenario": "coding",
                    "weight": 1.12, "successes": 8, "failures": 0, "last_updated": 1000,
                },
                "longcat_lite:chat": {
                    "backend": "longcat_lite", "scenario": "chat",
                    "weight": 0.96, "successes": 0, "failures": 2, "last_updated": 1000,
                },
            }
            with open(os.path.join(tmp, "lima_routing_weights.json"), "w") as f:
                json.dump(data, f)
            result = load_weight_history(tmp)
            assert len(result) == 2

    def test_build_training_samples(self):
        history = [
            {"backend": "a", "scenario": "coding", "weight": 1.2, "successes": 5, "failures": 0, "last_updated": 0},
            {"backend": "b", "scenario": "chat", "weight": 0.8, "successes": 1, "failures": 3, "last_updated": 0},
        ]
        samples = build_training_samples(history, ["a", "b"])
        assert len(samples) >= 2

    def test_samples_to_arrays(self):
        history = [
            {"backend": "a", "scenario": "coding", "weight": 1.0, "successes": 2, "failures": 0, "last_updated": 0},
        ]
        samples = build_training_samples(history, ["a"])
        features, targets = samples_to_arrays(samples)
        assert len(features) > 0
        assert len(features[0]) == N_FEATURES
        assert len(targets[0]) == 1


# ─── Trainer integration tests ────────────────────────────────────────


class TestTrainer:
    def test_training_state(self):
        state = get_training_state()
        assert "request_count" in state
        assert "total_rounds" in state
        assert state["train_interval"] > 0

    def test_try_train_no_data(self):
        result = try_train()
        assert isinstance(result, bool)
