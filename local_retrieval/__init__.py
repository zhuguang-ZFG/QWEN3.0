"""Local retrieval lab without heavy runtime dependencies."""

from local_retrieval.chunking import Chunker, CodeAwareChunker, SimpleTextChunker, TextChunk
from local_retrieval.fts_index import FtsIndex
from local_retrieval.index import InMemoryTokenIndex, LocalRetrievalIndex, RetrievalHit
from local_retrieval.leann_adapter import (
    LeannAdapterConfig,
    create_leann_index,
    is_leann_available,
    leann_status,
)
from local_retrieval.manifest import (
    ChunkRecord,
    IndexBackendKind,
    IndexManifest,
    IndexedDocument,
)

__all__ = [
    "ChunkRecord",
    "Chunker",
    "CodeAwareChunker",
    "FtsIndex",
    "IndexBackendKind",
    "IndexManifest",
    "IndexedDocument",
    "InMemoryTokenIndex",
    "LeannAdapterConfig",
    "LocalRetrievalIndex",
    "RetrievalHit",
    "SimpleTextChunker",
    "TextChunk",
    "create_leann_index",
    "is_leann_available",
    "leann_status",
]
