"""File operation tools — upload, download, and list files with safety constraints."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .registry import tool

# ── Safety: allowed base directories ──────────────────────────────────────────
# Only paths under these roots are permitted for file operations.
# Environment variable LIMA_FILE_TOOLS_ROOT can override (colon-separated).
_DEFAULT_ROOTS = [
    os.path.join(os.path.dirname(__file__), "..", "data"),
    os.path.join(os.path.dirname(__file__), "..", "workspace"),
]


def _allowed_roots() -> list[Path]:
    env = os.environ.get("LIMA_FILE_TOOLS_ROOT", "")
    if env:
        # On Windows, use ';' as separator; on Unix, use ':'
        sep = ";" if os.name == "nt" else ":"
        return [Path(p).resolve() for p in env.split(sep) if p]
    return [Path(r).resolve() for r in _DEFAULT_ROOTS]


def _is_safe_path(path: str) -> tuple[bool, str]:
    """Return ``(True, "")`` if *path* is within an allowed root, else error."""
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError) as exc:
        return False, f"Invalid path: {exc}"
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
            return True, ""
        except ValueError:
            continue
    return False, (
        f"Path {path} is outside allowed directories. "
        f"Allowed roots: {[str(r) for r in _allowed_roots()]}"
    )


@tool(
    "list_files",
    "List files and subdirectories in a directory.",
    {
        "properties": {
            "directory": {
                "description": "Directory path to list.",
                "type": "string",
            },
            "pattern": {
                "default": "*",
                "description": "Glob pattern to filter files (e.g. '*.py').",
                "type": "string",
            },
        },
        "required": ["directory"],
        "type": "object",
    },
)
async def _list_files(directory: str, pattern: str = "*") -> dict[str, Any]:
    """List files in *directory* matching *pattern*."""
    safe, err = _is_safe_path(directory)
    if not safe:
        return {"error": err}
    dirpath = Path(directory).resolve()
    if not dirpath.is_dir():
        return {"error": f"Not a directory: {directory}"}
    try:
        entries = []
        for entry in sorted(dirpath.glob(pattern)):
            stat = entry.stat()
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else 0,
            })
            if len(entries) >= 200:
                break
        return {"directory": str(dirpath), "count": len(entries), "entries": entries}
    except Exception as exc:
        return {"error": str(exc)}


@tool(
    "read_file_content",
    "Read text content from a file.",
    {
        "properties": {
            "file_path": {
                "description": "Path to the file to read.",
                "type": "string",
            },
            "max_length": {
                "default": 8000,
                "description": "Maximum characters to return.",
                "type": "integer",
            },
        },
        "required": ["file_path"],
        "type": "object",
    },
)
async def _read_file(file_path: str, max_length: int = 8000) -> dict[str, Any]:
    """Read a text file and return its content."""
    safe, err = _is_safe_path(file_path)
    if not safe:
        return {"error": err}
    path = Path(file_path).resolve()
    if not path.is_file():
        return {"error": f"Not a file: {file_path}"}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_length:
            content = content[:max_length] + f"\n... (truncated at {max_length} chars)"
        return {"file": str(path), "content": content, "length": len(content)}
    except Exception as exc:
        return {"error": str(exc)}


@tool(
    "write_file_content",
    "Write text content to a file. Creates parent directories if needed.",
    {
        "properties": {
            "file_path": {
                "description": "Path to the file to write.",
                "type": "string",
            },
            "content": {
                "description": "Text content to write.",
                "type": "string",
            },
        },
        "required": ["file_path", "content"],
        "type": "object",
    },
)
async def _write_file(file_path: str, content: str) -> dict[str, Any]:
    """Write *content* to *file_path*."""
    safe, err = _is_safe_path(file_path)
    if not safe:
        return {"error": err}
    path = Path(file_path).resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"file": str(path), "bytes_written": len(content.encode("utf-8"))}
    except Exception as exc:
        return {"error": str(exc)}
