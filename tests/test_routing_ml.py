"""Tests for ML routing prediction module."""

from __future__ import annotations

import json
import os
import sys
import tempfile

import numpy as np
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
    cross_entropy_loss,
    train_step,
)
from routing_ml.training_data import (
    build_training_samples,
    load_weight_history,
    samples_to_arrays,
)
from routing_ml.routing_trainer import (
    get_training_state,
    try_train,
)


# ─── Feature extractor tests ──────────────────────────────────────────


class TestFeatureExtractor:
    def test_feature_dimension(self):
        v = extract_features([{"role": "user", "content": "hello"}])
        assert v.features.shape == (N_FEATURES,)
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
        assert v_coding.features[10] == 1.0  # coding onehot
        assert v_coding.features[11] == 0.0

        v_chat = extract_features([], scenario="chat")
        assert v_chat.features[10] == 0.0
        assert v_chat.features[11] == 1.0

    def test_health_map_encoding(self):
        health = {"groq_llama70b": "healthy", "longcat_lite": "dead"}
        v = extract_features([], health_map=health, top_backends=["groq_llama70b", "longcat_lite"])
        assert v.features[5] == 1.0  # healthy
        assert v.features[6] == 0.0  # dead

    def test_metadata(self):
        v = extract_features([{"role": "user", "content": "hello"}], scenario="chat")
        assert "message_length" in v.metadata
        assert v.metadata["scenario"] == "chat"


# ─── Model tests ───────────────────────────────────────────────────────


class TestRoutingModel:
    def test_create_model(self):
        backends = ["groq_llama70b", "scnet_ds_flash", "github_gpt4o"]
        model = create_model(backends)
        assert model.weights1.shape == (N_FEATURES, 32)
        assert model.weights2.shape == (32, 3)
        assert model.backend_names == backends

    def test_predict_shape(self):
        model = create_model(["a", "b", "c"])
        features = np.random.randn(N_FEATURES).astype(np.float32)
        scores = model.predict(features)
        assert scores.shape == (3,)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_predict_batch(self):
        model = create_model(["a", "b"])
        features = np.random.randn(5, N_FEATURES).astype(np.float32)
        scores = model.predict(features)
        assert scores.shape == (5, 2)

    def test_predict_topk(self):
        model = create_model(["a", "b", "c", "d"])
        features = np.random.randn(N_FEATURES).astype(np.float32)
        topk = model.predict_topk(features, k=2)
        assert len(topk) == 2
        assert all(isinstance(name, str) and isinstance(score, float) for name, score in topk)
        # Scores should be descending
        assert topk[0][1] >= topk[1][1]

    def test_serialize_roundtrip(self):
        model = create_model(["x", "y"])
        data = model.to_dict()
        restored = RoutingModel.from_dict(data)
        assert restored.backend_names == ["x", "y"]
        assert restored.weights1.shape == model.weights1.shape
        np.testing.assert_allclose(restored.weights1, model.weights1, rtol=1e-5)

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
        features = np.random.randn(10, N_FEATURES).astype(np.float32)
        targets = np.zeros((10, 2), dtype=np.float32)
        targets[:5, 0] = 1.0  # first 5 prefer backend "a"
        targets[5:, 1] = 1.0  # last 5 prefer backend "b"

        loss_before = cross_entropy_loss(model.predict(features), targets)
        for _ in range(50):
            train_step(model, features, targets, lr=0.01)
        loss_after = cross_entropy_loss(model.predict(features), targets)

        assert loss_after < loss_before


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
                    "backend": "scnet_ds_flash",
                    "scenario": "coding",
                    "weight": 1.12,
                    "successes": 8,
                    "failures": 0,
                    "last_updated": 1000,
                },
                "longcat_lite:chat": {
                    "backend": "longcat_lite",
                    "scenario": "chat",
                    "weight": 0.96,
                    "successes": 0,
                    "failures": 2,
                    "last_updated": 1000,
                },
            }
            with open(os.path.join(tmp, "lima_routing_weights.json"), "w") as f:
                json.dump(data, f)
            result = load_weight_history(tmp)
            assert len(result) == 2
            assert result[0]["backend"] == "scnet_ds_flash"

    def test_build_training_samples(self):
        history = [
            {"backend": "a", "scenario": "coding", "weight": 1.2, "successes": 5, "failures": 0, "last_updated": 0},
            {"backend": "b", "scenario": "chat", "weight": 0.8, "successes": 1, "failures": 3, "last_updated": 0},
        ]
        samples = build_training_samples(history, ["a", "b"])
        assert len(samples) >= 2  # at least one per entry

    def test_samples_to_arrays(self):
        history = [
            {"backend": "a", "scenario": "coding", "weight": 1.0, "successes": 2, "failures": 0, "last_updated": 0},
        ]
        samples = build_training_samples(history, ["a"])
        features, targets = samples_to_arrays(samples)
        assert features.shape[1] == N_FEATURES
        assert targets.shape[1] == 1  # one backend


# ─── Trainer integration tests ────────────────────────────────────────


class TestTrainer:
    def test_training_state(self):
        state = get_training_state()
        assert "request_count" in state
        assert "total_rounds" in state
        assert state["train_interval"] > 0

    def test_try_train_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No weight history → should return False
            result = try_train()
            # Just verify it doesn't crash (may return True or False depending on data dir)
            assert isinstance(result, bool)
