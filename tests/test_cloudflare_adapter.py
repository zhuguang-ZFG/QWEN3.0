"""Tests for Cloudflare provider adapter (CF-G-2)."""

import json
from pathlib import Path

from provider_automation.adapters.cloudflare import (
    infer_capabilities,
    is_chat_candidate,
    map_model_to_backend_key,
    parse_inventory,
    unregistered_chat_candidates,
)


def test_is_chat_candidate_filters_embeddings():
    assert is_chat_candidate("@cf/baai/bge-large-en-v1.5", "embedding model") is False
    assert is_chat_candidate("@cf/meta/llama-3-8b-instruct", "text generation") is True


def test_map_model_to_backend_key():
    key = map_model_to_backend_key("@cf/meta/llama-3-8b-instruct")
    assert key.startswith("cf_")
    assert "llama" in key


def test_infer_capabilities_marks_coder():
    caps = infer_capabilities("@cf/qwen/qwen2.5-coder-32b-instruct", "coding model")
    assert "code" in caps


def test_parse_inventory_from_fixture(tmp_path: Path):
    payload = {
        "provider": "cloudflare",
        "fetched_at": 1.0,
        "models": [
            {
                "model_id": "@cf/meta/llama-3-8b-instruct",
                "name": "@cf/meta/llama-3-8b-instruct",
                "description": "Llama instruct chat model",
            },
            {
                "model_id": "@cf/baai/bge-large-en-v1.5",
                "name": "@cf/baai/bge-large-en-v1.5",
                "description": "embedding",
            },
        ],
    }
    path = tmp_path / "cf.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = parse_inventory(path)
    assert len(snapshot.models) == 1
    assert snapshot.models[0].model_id.endswith("llama-3-8b-instruct")


def test_unregistered_chat_candidates_excludes_registered(tmp_path: Path, monkeypatch):
    payload = {
        "models": [
            {
                "model_id": "@cf/meta/llama-3-8b-instruct",
                "description": "instruct chat",
            },
            {
                "model_id": "@cf/google/gemma-3-12b-it",
                "description": "gemma instruct",
            },
        ]
    }
    path = tmp_path / "cf.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(
        "provider_inventory.compare.registered_model_ids",
        lambda prefixes: {"@cf/meta/llama-3.3-70b-instruct-fp8-fast"},
    )
    monkeypatch.setattr(
        "provider_automation.adapters.cloudflare._admitted_overlay_model_ids",
        lambda admission_path="": set(),
    )
    candidates = unregistered_chat_candidates(path)
    ids = {c.model_id for c in candidates}
    assert "@cf/meta/llama-3-8b-instruct" in ids
    assert "@cf/google/gemma-3-12b-it" in ids
