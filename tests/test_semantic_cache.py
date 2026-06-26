"""Tests for semantic_cache."""

from __future__ import annotations

import os
import tempfile

import pytest

from semantic_cache.cache import SemanticCache, _cosine_similarity
from semantic_cache.embedder import FakeEmbedder
from semantic_cache.store import SemanticCacheStore


@pytest.fixture
def tmp_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    store = SemanticCacheStore(db_path=path)
    yield store
    os.unlink(path)


@pytest.fixture
def cache(tmp_store):
    return SemanticCache(embedder=FakeEmbedder(dimensions=64), store=tmp_store)


def test_cosine_similarity_identical_vectors():
    vec = [1.0, 2.0, 3.0]
    assert _cosine_similarity(vec, vec) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_fake_embedder_stable():
    emb = FakeEmbedder(dimensions=64)
    a = emb.embed(["hello"])[0]
    b = emb.embed(["hello"])[0]
    assert a == pytest.approx(b, abs=1e-9)
    assert _cosine_similarity(a, b) == pytest.approx(1.0)


def test_store_upsert_and_get_candidates(tmp_store):
    cache = SemanticCache(embedder=FakeEmbedder(dimensions=64), store=tmp_store)
    cache.store_response("hello", "hi there")
    result = cache.lookup("hello")
    assert result == "hi there"


def test_lookup_returns_none_when_empty(cache):
    assert cache.lookup("anything") is None


def test_lookup_respects_ttl(cache):
    cache.store_response("hello", "world")
    assert cache.lookup("hello", ttl_seconds=1) == "world"
    import time

    time.sleep(1.1)
    assert cache.lookup("hello", ttl_seconds=1) is None


def test_lookup_similar_but_not_identical(cache):
    cache.store_response("what is the weather today", "sunny")
    # Fake embedder is not semantic; identical strings hit, different strings miss.
    assert cache.lookup("what is the weather today") == "sunny"
    assert cache.lookup("weather today") is None


def test_clear(cache):
    cache.store_response("a", "1")
    cache.clear()
    assert cache.lookup("a") is None


def test_store_prunes_old_entries(tmp_store):
    cache = SemanticCache(embedder=FakeEmbedder(dimensions=64), store=tmp_store)
    cache.store_response("old", "response")
    import time

    time.sleep(1.1)
    deleted = tmp_store.prune(max_age_seconds=1.0)
    assert deleted == 1
    assert cache.lookup("old") is None


def test_store_bumps_hit_count(tmp_store):
    cache = SemanticCache(embedder=FakeEmbedder(dimensions=64), store=tmp_store)
    cache.store_response("q", "r")
    cache.lookup("q")
    cache.lookup("q")
    with tmp_store._connection() as conn:
        row = conn.execute("SELECT hit_count FROM semantic_cache").fetchone()
    assert row["hit_count"] == 2
