"""Leann adapter tests for the local retrieval lab."""

from local_retrieval.leann_adapter import (
    LeannAdapterConfig,
    create_leann_index,
    is_leann_available,
    leann_status,
)


def test_is_leann_available_default_false(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert is_leann_available() is False


def test_leann_status_reports_unavailable(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    status = leann_status()

    assert status["available"] is False
    assert status["env_gate"] is False
    assert "note" in status


def test_create_leann_index_returns_none_when_unavailable(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert create_leann_index() is None


def test_leann_adapter_config_defaults_and_to_dict():
    config = LeannAdapterConfig()

    assert config.embedding_model == "all-MiniLM-L6-v2"
    assert config.dim == 384
    assert config.use_gpu is False
    assert config.metric == "cosine"
    assert config.to_dict()["batch_size"] == 32


def test_leann_not_importable_without_env(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert is_leann_available() is False
