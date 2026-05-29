"""Tests for enhance_context eval pool filtering."""

from __future__ import annotations

import json
from pathlib import Path

import code_orchestrator_context as ctx


def test_enhance_context_filters_demoted_backends(tmp_path: Path, monkeypatch):
    path = tmp_path / "coding_backend_scores_full_test.json"
    path.write_text(
        json.dumps([{"backend": "scnet_large_ds_pro", "score": 0, "ok": False}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "eval_pool_gate.latest_scores_path",
        lambda data_dir, full=False: path if full else None,
    )
    monkeypatch.setattr(
        ctx.backend_reputation,
        "sort_by_reputation",
        lambda pool: list(pool),
    )

    result = ctx.enhance_context(
        "refactor this module with tests",
        [{"role": "user", "content": "refactor this module with tests"}],
        scenario="coding",
    )
    pool = result["backend_pool"]
    assert "scnet_large_ds_pro" not in pool
    assert pool
