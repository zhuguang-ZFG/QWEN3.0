"""Artifact Handle — large data reference pattern.

Based on Google ADK Artifact pattern:
- Large code files are stored as references (handles), not inlined
- Agents see lightweight metadata (path, size, symbols)
- Full content loaded on-demand only when needed
- Reduces token waste for context injection
"""

from dataclasses import dataclass


@dataclass
class ArtifactHandle:
    """Lightweight reference to a large artifact."""

    path: str
    size_bytes: int
    line_count: int
    summary: str
    symbols: list[str]

    def to_context_line(self) -> str:
        """Render as a single context line for prompt injection."""
        syms = ", ".join(self.symbols[:5])
        suffix = f" (+{len(self.symbols)-5})" if len(self.symbols) > 5 else ""
        return f"[{self.path}] {self.line_count}L | {syms}{suffix}"

    @property
    def is_large(self) -> bool:
        return self.line_count > 200 or self.size_bytes > 10000


def create_handle(
    path: str,
    content: str,
    symbols: list[str] | None = None,
) -> ArtifactHandle:
    """Create an artifact handle from file content."""
    lines = content.count("\n") + 1
    size = len(content.encode("utf-8"))
    summary = content[:200].replace("\n", " ")

    return ArtifactHandle(
        path=path,
        size_bytes=size,
        line_count=lines,
        summary=summary,
        symbols=symbols or [],
    )


def should_use_handle(content: str) -> bool:
    """Determine if content should be referenced by handle rather than inlined."""
    lines = content.count("\n") + 1
    size = len(content.encode("utf-8"))
    return lines > 200 or size > 10000


def render_handles_for_context(
    handles: list[ArtifactHandle], max_chars: int = 800
) -> str:
    """Render multiple handles as compact context block."""
    lines = ["[Artifact References]"]
    total = len(lines[0])
    for h in handles:
        line = h.to_context_line()
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
