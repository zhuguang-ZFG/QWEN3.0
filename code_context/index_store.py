import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    kind: str
    line: int


@dataclass
class FileRecord:
    path: str
    symbols: list[CodeSymbol] = field(default_factory=list)
    imports: list[tuple[str, int]] = field(default_factory=list)
    mtime: float = 0.0
    embedding: list[float] = field(default_factory=list)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryCodeIndex:
    def __init__(self) -> None:
        self._files: dict[str, FileRecord] = {}

    def upsert_file(
        self,
        path: str,
        symbols: list[CodeSymbol],
        imports: list[tuple[str, int]],
        mtime: float,
        embedding: list[float] | None = None,
    ) -> None:
        self._files[path] = FileRecord(
            path=path,
            symbols=symbols,
            imports=imports,
            mtime=mtime,
            embedding=embedding or [],
        )

    def semantic_search(
        self, query_embedding: list[float], limit: int = 5
    ) -> list[FileRecord]:
        """Search by cosine similarity against stored embeddings."""
        scored: list[tuple[float, FileRecord]] = []
        for record in self._files.values():
            if not record.embedding:
                continue
            sim = _cosine_similarity(query_embedding, record.embedding)
            if sim > 0.1:
                scored.append((sim, record))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [record for _score, record in scored[:limit]]

    def search(self, query: str, limit: int = 5) -> list[FileRecord]:
        """Keyword fallback search (used when embeddings unavailable)."""
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, FileRecord]] = []
        for record in self._files.values():
            haystack = " ".join(
                [record.path]
                + [symbol.name for symbol in record.symbols]
                + [name for name, _line in record.imports]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [record for _score, record in scored[:limit]]


def build_code_index(**kwargs) -> InMemoryCodeIndex:
    """Factory: returns the best available code index.

    Prefers ChromaCodeIndex when chromadb is available and LIMA_DATA_DIR is set.
    Falls back to InMemoryCodeIndex.
    """
    import os

    data_dir = os.environ.get("LIMA_DATA_DIR", "")
    if data_dir:
        try:
            from code_context.chroma_vector_store import ChromaCodeIndex
            return ChromaCodeIndex(persist_directory=data_dir, **kwargs)  # type: ignore[return-value]
        except Exception as exc:
            _log.debug("code_context/index_store.py: {}", type(exc).__name__)
    return InMemoryCodeIndex()
