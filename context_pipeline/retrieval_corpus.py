"""Shared production retrieval corpus paths (aligned with lima_routing_prod fixture)."""

from __future__ import annotations

from pathlib import Path

PRODUCTION_CORPUS_FILES: tuple[str, ...] = (
    "routing_engine.py",
    "routing_classifier.py",
    "routing_selector.py",
    "routing_executor.py",
    "http_caller.py",
    "health_tracker.py",
    "router_v3.py",
    "routes/chat_handler.py",
    "context_pipeline/retrieval_injection.py",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_production_corpus_paths(
    files: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    """Resolve corpus file paths relative to repo root."""
    rel_paths = list(files or PRODUCTION_CORPUS_FILES)
    root = repo_root()
    resolved: list[str] = []
    for rel in rel_paths:
        path = (root / rel).resolve()
        if path.is_file():
            resolved.append(str(path))
    return sorted(resolved)
