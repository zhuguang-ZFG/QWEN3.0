"""Deep context engineering — project-aware coding with import graphs.

Builds a live project model without external dependencies:
  1. Parse Python imports to build dependency graph
  2. Extract top-level symbols (functions, classes, constants)
  3. Track recent git changes for relevant context
  4. Inject structured context into coding prompts
"""
from __future__ import annotations

import ast
import logging
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

_log = logging.getLogger(__name__)

SCAN_IGNORE = {
    "venv", "node_modules", "__pycache__", ".git", ".codegraph",
    "dist", "build", "egg-info", "esp32S_XYZ", "PyWxDump",
    "mempalace", "codegraph", "wx_key_tool", "lima-miniprogram",
}


# ── Python Import Graph ──────────────────────────────────────────────────────

class FileContext:
    """Parsed context for a single source file."""

    def __init__(self, path: Path):
        self.path = path
        self.imports: list[str] = []
        self.functions: list[str] = []
        self.classes: list[str] = []
        self.constants: list[str] = []
        self.dependencies: set[str] = set()  # resolved local module names

    def parse(self) -> bool:
        try:
            source = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(alias.name)
                    if "." not in alias.name and not _is_stdlib(alias.name):
                        self.dependencies.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and not _is_stdlib(node.module.split(".")[0]):
                    self.dependencies.add(node.module.split(".")[0])
            elif isinstance(node, ast.FunctionDef):
                self.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        self.constants.append(target.id)

        return True


def _is_stdlib(name: str) -> bool:
    return name in _STDLIB


_STDLIB = frozenset({
    "os", "sys", "re", "json", "time", "datetime", "logging",
    "threading", "asyncio", "collections", "itertools", "functools",
    "typing", "pathlib", "subprocess", "hashlib", "uuid", "random",
    "math", "io", "csv", "xml", "html", "http", "urllib", "socket",
    "abc", "dataclasses", "enum", "copy", "traceback", "warnings",
    "inspect", "ast", "textwrap", "shutil", "tempfile", "argparse",
    "configparser", "unittest", "pytest", "base64", "struct", "zlib",
    "sqlite3", "__future__", "builtins", "contextlib", "importlib",
})


# ── Project Model ────────────────────────────────────────────────────────────

class ProjectModel:
    """Live model of a Python project: files, symbols, dependencies."""

    def __init__(self, root: str, max_files: int = 500):
        self.root = Path(root).resolve()
        self.max_files = max_files
        self.files: dict[str, FileContext] = {}
        self.importers: dict[str, set[str]] = defaultdict(set)
        self._scanned = False

    def scan(self) -> int:
        """Scan project files. Returns count of successfully parsed files."""
        if self._scanned:
            return len(self.files)

        # Collect all candidates, prioritize important files
        candidates = []
        for entry in self.root.rglob("*.py"):
            if any(p in SCAN_IGNORE for p in entry.parts):
                continue
            rel = str(entry.relative_to(self.root))
            name = entry.name
            # Deprioritize debug/temp files
            priority = 0
            if name.startswith(("debug_", "_", "test_")) or "copy" in name.lower():
                priority = 1
            candidates.append((priority, entry, rel))
            if len(candidates) >= self.max_files * 2:
                break

        candidates.sort(key=lambda x: (x[0], str(x[2])))
        count = 0
        for _, entry, rel in candidates[: self.max_files]:
            ctx = FileContext(entry)
            if ctx.parse():
                self.files[rel] = ctx
                for dep in ctx.dependencies:
                    self.importers[dep].add(rel)
                count += 1

        self._scanned = True
        return count

    def get_importers(self, module_name: str) -> set[str]:
        """Which files import this module?"""
        base = module_name.replace(".py", "").replace("/", ".").replace("\\", ".")
        return self.importers.get(base, set()) | self.importers.get(
            Path(module_name).stem, set(),
        )

    def find_related(self, query_keywords: list[str], max_results: int = 8) -> list[str]:
        """Find files related to query by matching keywords against symbols."""
        scored: list[tuple[str, int]] = []
        for rel, ctx in self.files.items():
            score = 0
            rel_lower = rel.lower()
            name_stem = Path(rel).stem.lower()
            for kw in query_keywords:
                kw_lower = kw.lower()
                # Exact file name match = highest priority
                if kw_lower in name_stem:
                    score += 10
                elif kw_lower in rel_lower:
                    score += 4
                if any(kw_lower in f.lower() for f in ctx.functions):
                    score += 3
                if any(kw_lower in c.lower() for c in ctx.classes):
                    score += 3
                if any(kw_lower in i.lower() for i in ctx.imports):
                    score += 1
            if score > 0:
                scored.append((rel, score))
        scored.sort(key=lambda x: -x[1])
        return [f for f, _ in scored[:max_results]]

    def build_context_string(self, related_files: list[str], max_chars: int = 3000) -> str:
        """Build a context string from related files with symbols."""
        parts: list[str] = []
        total = 0
        for rel in related_files:
            ctx = self.files.get(rel)
            if not ctx:
                continue
            lines = [f"## {rel}"]
            if ctx.functions:
                lines.append("  functions: " + ", ".join(ctx.functions[:8]))
            if ctx.classes:
                lines.append("  classes: " + ", ".join(ctx.classes[:5]))
            if ctx.imports:
                lines.append("  imports: " + ", ".join(ctx.imports[:8]))
            if ctx.dependencies:
                lines.append("  depends on: " + ", ".join(sorted(ctx.dependencies)[:8]))
            importer_list = self.importers.get(Path(rel).stem, set())
            if importer_list:
                upstream = sorted(importer_list)[:5]
                lines.append("  imported by: " + ", ".join(upstream))

            block = "\n".join(lines)
            if total + len(block) < max_chars:
                parts.append(block)
                total += len(block)

        if not parts:
            return ""
        return (
            f"[Deep Context — {len(parts)} files, {total} chars]\n\n"
            + "\n\n".join(parts)
        )


# ── Git Context ──────────────────────────────────────────────────────────────

def get_recent_changes(root: str | None = None, max_files: int = 8) -> list[dict]:
    """Get recently changed files from git. Returns [{path, status, since}...]"""
    root = root or os.getcwd()
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--name-status", "-10", "--since=7 days ago"],
            capture_output=True, text=True, timeout=5, cwd=root,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    files: dict[str, dict] = {}
    for line in result.stdout.strip().split("\n"):
        if not line.startswith(("M\t", "A\t", "D\t")):
            continue
        status, path = line[0], line[2:].strip()
        if path.endswith(".py") and path not in files:
            files[path] = {"path": path, "status": status}
            if len(files) >= max_files:
                break

    return list(files.values())


def build_git_context(root: str | None = None) -> str:
    """Build a context string from recent git changes."""
    changes = get_recent_changes(root)
    if not changes:
        return ""
    lines = ["[Recent Changes — last 7 days]"]
    seen: set[str] = set()
    for c in changes:
        name = Path(c["path"]).name
        if name not in seen:
            lines.append(f"  {c['status']} {c['path']}")
            seen.add(name)
    return "\n".join(lines[:10])


# ── Top-Level API ────────────────────────────────────────────────────────────

_model_cache: dict[str, ProjectModel] = {}


def get_project_model(root: str | None = None) -> ProjectModel:
    """Get or create a cached project model."""
    root = str(Path(root or os.getcwd()).resolve())
    if root not in _model_cache:
        model = ProjectModel(root)
        count = model.scan()
        _log.info("Project model built: %d files in %s", count, root)
        _model_cache[root] = model
    return _model_cache[root]


def build_deep_context(
    query: str, root: str | None = None, max_files: int = 6, max_chars: int = 3000,
) -> str:
    """Main entry: build deep project context for a coding query.

    Combines: import graph + symbols + git changes.
    """
    model = get_project_model(root)
    keywords = _extract_query_keywords(query)
    related = model.find_related(keywords, max_files)
    if related:
        context = model.build_context_string(related, max_chars)
    else:
        context = ""

    git_ctx = build_git_context(root)
    if git_ctx:
        context = (context + "\n\n" + git_ctx) if context else git_ctx

    return context


def _extract_query_keywords(query: str) -> list[str]:
    """Extract search keywords from a query."""
    kw: list[str] = []
    kw.extend(re.findall(r"[\w/\\]+\.py", query))
    kw.extend(re.findall(r"\b([a-z]+_[a-z]+(?:_[a-z]+)*)\b", query.lower()))
    kw.extend(re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", query))
    words = re.findall(r"\b([a-z]{4,20})\b", query.lower())
    stops = {"this", "that", "with", "from", "have", "when", "will", "would", "could", "should", "about", "into", "over", "after", "before"}
    kw.extend(w for w in words if w not in stops)
    return list(dict.fromkeys(kw))[:12]
