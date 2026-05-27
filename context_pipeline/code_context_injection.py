"""Direct code context injection for coding scenarios.

Scans files mentioned in the query, extracts symbols via tree-sitter,
finds related files via graph traversal, and builds concise context
for injection into the system prompt.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_log = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 2000
_MAX_FILES = 5

def _detect_project_root() -> str:
    env_root = os.environ.get("LIMA_PROJECT_ROOT", "")
    if env_root and os.path.isdir(env_root):
        return env_root
    cwd = os.getcwd()
    candidates = [cwd, "/opt/lima-router", "D:/GIT"]
    for p in candidates:
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "routing_engine.py")):
            return p
    return cwd

_PROJECT_ROOT = _detect_project_root()


def extract_file_mentions(query: str, messages: list[dict] | None = None) -> list[str]:
    """Extract file paths and code identifiers from query and recent messages."""
    text = query
    if messages:
        for msg in messages[-3:]:
            if isinstance(msg, dict):
                text += " " + str(msg.get("content", ""))[:500]

    file_patterns = re.findall(
        r'[\w/\\.-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp|h|hpp)\b',
        text,
    )
    identifiers = re.findall(r'\b([A-Z][a-zA-Z]+(?:Error|Exception|Config|Result|Store|Index))\b', text)
    identifiers += re.findall(r'\b([a-z_]{3,25})\b', text)
    identifiers = [i for i in identifiers if len(i) > 3][:10]

    return file_patterns, identifiers


def scan_and_build_context(
    query: str,
    messages: list[dict] | None = None,
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> str:
    """Build code context string for a coding query.

    1. Extract file mentions and identifiers from query
    2. Scan mentioned files with tree-sitter
    3. Find related files via graph
    4. Build concise context string
    """
    file_mentions, identifiers = extract_file_mentions(query, messages)
    parts: list[str] = []
    total = 0

    scanned_files: set[str] = set()

    for fname in file_mentions[:_MAX_FILES]:
        path = _resolve_file(fname)
        if not path or str(path) in scanned_files:
            continue
        scanned_files.add(str(path))
        ctx = _scan_single_file(path)
        if ctx and total + len(ctx) < max_chars:
            parts.append(ctx)
            total += len(ctx)

    for ident in identifiers[:3]:
        if total >= max_chars:
            break
        related = _find_identifier_files(ident)
        for rpath in related[:2]:
            if str(rpath) in scanned_files:
                continue
            scanned_files.add(str(rpath))
            ctx = _scan_single_file(rpath)
            if ctx and total + len(ctx) < max_chars:
                parts.append(ctx)
                total += len(ctx)

    if not parts:
        return ""

    header = f"[Code Context — {len(scanned_files)} files, {total} chars]"
    return header + "\n\n" + "\n---\n".join(parts)


def _resolve_file(fname: str) -> Path | None:
    candidates = [
        Path(_PROJECT_ROOT) / fname,
        Path(fname),
        Path(_PROJECT_ROOT) / "D:/GIT" / fname,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def _scan_single_file(path: Path) -> str:
    try:
        from code_context.ast_adapter import get_extractor
        suffix = path.suffix.lower()
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".jsx": "javascript",
            ".go": "go", ".rs": "rust", ".java": "java",
        }
        lang = lang_map.get(suffix, "python")
        extractor = get_extractor(lang)
        if not extractor:
            return ""

        ast = extractor.scan_file(path)
        lines = [f"## {path.name} ({ast.language})"]
        for s in ast.symbols[:15]:
            doc = f" — {s.docstring[:80]}" if s.docstring else ""
            lines.append(f"  {s.kind} {s.name} (L{s.line}){doc}")
        for r in ast.relations[:5]:
            lines.append(f"  {r.relation_type} → {r.target}")

        source = path.read_text(encoding="utf-8", errors="replace")
        if len(source) < 3000:
            lines.append(f"\n```{ast.language}\n{source[:2000]}\n```")

        return "\n".join(lines)
    except Exception as exc:
        _log.debug("scan %s failed: %s", path, exc)
        return ""


def _find_identifier_files(identifier: str) -> list[Path]:
    results: list[Path] = []
    try:
        from code_context.graph_index import build_graph_index
        g = build_graph_index()
        related = g.search([identifier], max_depth=1, max_results=3)
        for r in related:
            p = Path(r.entity)
            if p.exists():
                results.append(p)
    except Exception:
        pass

    if not results:
        try:
            from code_context.index_store import InMemoryCodeIndex
            idx = InMemoryCodeIndex()
            matches = idx.search(identifier, limit=3)
            for m in matches:
                p = Path(m.path)
                if p.exists():
                    results.append(p)
        except Exception:
            pass

    return results
