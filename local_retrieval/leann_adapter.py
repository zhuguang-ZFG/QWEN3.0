"""Safe LEANN adapter boundary without runtime dependency.

The module does not import torch, sentence-transformers, or LEANN at import
time. LEANN probing remains behind the LIMA_ENABLE_LEANN=1 environment gate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LeannAdapterConfig:
    embedding_model: str = "all-MiniLM-L6-v2"
    dim: int = 384
    index_path: str = ""
    metric: str = "cosine"
    batch_size: int = 32
    use_gpu: bool = False

    def to_dict(self) -> dict:
        return {
            "embedding_model": self.embedding_model,
            "dim": self.dim,
            "index_path": self.index_path,
            "metric": self.metric,
            "batch_size": self.batch_size,
            "use_gpu": self.use_gpu,
        }


def is_leann_available() -> bool:
    """Return True only when explicitly enabled and importable."""
    import importlib

    from config import settings

    if not settings.FLAGS.enable_leann:
        return False
    try:
        importlib.import_module("leann")
        return True
    except ImportError:
        return False


def create_leann_index(
    config: LeannAdapterConfig | None = None,
    documents: list[str] | None = None,
) -> object | None:
    """Create a LEANN index when the optional runtime exists.

    The current implementation is a boundary stub and returns None. Keeping the
    function explicit prevents accidental heavy dependency adoption.
    """
    _ = config or LeannAdapterConfig()
    _ = documents or []
    if not is_leann_available():
        return None
    return None


def leann_status() -> dict:
    """Return LEANN availability status for observability."""
    from config import settings

    return {
        "available": is_leann_available(),
        "env_gate": settings.FLAGS.enable_leann,
        "note": ("LEANN is not a runtime dependency. Set LIMA_ENABLE_LEANN=1 to enable probe."),
    }
