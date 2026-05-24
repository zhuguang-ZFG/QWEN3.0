"""Split documents into stable, addressable chunks.

No external dependencies. The default chunker uses line-based windows with
configurable overlap. Code-aware chunking remains a future boundary.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    start_line: int
    end_line: int
    char_offset: int = 0
    char_length: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Chunker(ABC):
    """Abstract chunker interface."""

    @abstractmethod
    def chunk(self, text: str, source_path: str = "") -> list[TextChunk]:
        ...


class SimpleTextChunker(Chunker):
    """Line-based chunking with overlap and deterministic chunk IDs."""

    def __init__(self, max_chars: int = 2000, overlap_lines: int = 3) -> None:
        self.max_chars = max(1, int(max_chars))
        self.overlap_lines = max(0, int(overlap_lines))

    def chunk(self, text: str, source_path: str = "") -> list[TextChunk]:
        if not text or not text.strip():
            return []

        lines = text.split("\n")
        chunks: list[TextChunk] = []
        chunk_index = 0
        line_index = 0

        while line_index < len(lines):
            chunk_lines: list[str] = []
            char_count = 0
            end_index = line_index

            while end_index < len(lines):
                next_len = len(lines[end_index]) + 1
                if chunk_lines and char_count + next_len > self.max_chars:
                    break
                chunk_lines.append(lines[end_index])
                char_count += next_len
                end_index += 1

            chunk_text = "\n".join(chunk_lines)
            char_offset = sum(len(line) + 1 for line in lines[:line_index])
            chunks.append(TextChunk(
                chunk_id=_stable_id(source_path, chunk_index),
                text=chunk_text,
                start_line=line_index + 1,
                end_line=end_index,
                char_offset=char_offset,
                char_length=len(chunk_text),
                metadata={
                    "path": source_path,
                    "chunk_index": chunk_index,
                },
            ))

            chunk_index += 1
            step = max(1, len(chunk_lines) - self.overlap_lines)
            line_index += step

        return chunks


class CodeAwareChunker(Chunker):
    """Placeholder for future tree-sitter-backed chunking."""

    def __init__(self, max_chars: int = 2000) -> None:
        self._fallback = SimpleTextChunker(max_chars=max_chars)

    def chunk(self, text: str, source_path: str = "") -> list[TextChunk]:
        return self._fallback.chunk(text, source_path)


def _stable_id(source_path: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{source_path}:{chunk_index}".encode()).hexdigest()[:16]
    return f"chunk-{digest}"
