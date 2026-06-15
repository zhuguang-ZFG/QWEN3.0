"""List Python modules with weak import fan-in via CodeGraph + ripgrep cross-check.

Usage:
  python scripts/codegraph_orphans.py
  python scripts/codegraph_orphans.py --fanin   # ripgrep prod fan-in for graph orphans

Requires: codegraph index on project root (.codegraph/codegraph.db).
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".codegraph" / "codegraph.db"
SKIP_PREFIXES = ("tests/", "scripts/", "esp32S_XYZ/", "deepcode-cli/", ".venv")
SKIP_DIRS = {"tests", "scripts", "esp32S_XYZ", "deepcode-cli", ".venv", "__pycache__"}
ROOT_KEEP = frozenset({"server.py", "conftest.py"})

# Cold modules eligible for test-only pruning (see docs/CODEBASE_SUBSYSTEM_TIER_CN.md)
COLD_MODULES = [
    "evolution",
    "graph_retrieval",
    "retrieval_eval",
    "retrieval_eval_runner",
    "complexity",
    "entity_extraction",
    "graph_context_expander",
    "production_index",
    "session_memory_enhancer",
    "signal_extraction",
    "concurrency_pool",
    "index_protocol",
    "reranker_protocol",
    "retrieval_corpus",
    "retrieval_trace",
]


PROD_SCAN_ROOTS = (
    "device_gateway",
    "routes",
    "context_pipeline",
    "session_memory",
    "channel_gateway",
    "device_memory",
    "device_workflow",
    "device_intelligence",
    "device_policy",
    "device_artifacts",
    "device_ledger",
    "device_support",
    "device_ota",
    "observability",
    "external_enrichment",
    "provider_automation",
    "lima_mcp",
    "xiaozhi_drawing",
    "esp32s_adapter",
)


def _prod_fanin_hits(stem: str, *, self_name: str) -> list[str]:
    """Scan production packages for textual references (catches lazy imports)."""
    needles = (stem, f"{stem}.py", f"import {stem}", f"from {stem}")
    hits: list[str] = []
    candidates: list[Path] = [p for p in ROOT.glob("*.py") if p.name != self_name]
    for rel in PROD_SCAN_ROOTS:
        base = ROOT / rel
        if base.is_dir():
            candidates.extend(base.rglob("*.py"))
    for path in candidates:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        parts = path.parts
        if parts and parts[0] in SKIP_DIRS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(n in text for n in needles):
            hits.append(rel)
    return sorted(set(hits))


def _graph_imports(cur: sqlite3.Cursor) -> list[sqlite3.Row]:
    return cur.execute(
        """
        SELECT n.file_path, n.name
        FROM nodes n
        WHERE n.kind = 'import' AND n.file_path LIKE '%.py'
        """
    ).fetchall()


def _print_schema(cur: sqlite3.Cursor) -> None:
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("tables:", tables[:20])
    for t in ("nodes", "edges", "files"):
        if t in tables:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
            print(f"{t} cols:", cols)


def _scan_root_orphans(imports: list[sqlite3.Row], *, fanin: bool) -> None:
    imported_modules: set[str] = set()
    for row in imports:
        name = row["name"] or ""
        imported_modules.add(name)
        if "." in name:
            imported_modules.add(name.split(".")[0])

    root_py = sorted(p for p in ROOT.glob("*.py") if p.is_file() and p.name not in ROOT_KEEP)

    print("\n=== Root *.py with no static import references in CodeGraph ===")
    for path in root_py:
        stem = path.stem
        if stem in imported_modules:
            continue
        refs = [
            r["file_path"]
            for r in imports
            if stem in (r["name"] or "") or (r["name"] or "").endswith(stem)
        ]
        prod_refs = [f for f in refs if not any(f.startswith(s) for s in SKIP_PREFIXES)]
        if prod_refs:
            continue
        label = "ORPHAN?"
        if fanin:
            prod_hits = _prod_fanin_hits(stem, self_name=path.name)
            if prod_hits:
                label = f"LAZY ({len(prod_hits)} prod hits)"
                print(f"  {label} {path.name}  e.g. {prod_hits[:2]}")
                continue
        print(f"  {label} {path.name}  (test-only refs: {len(refs) - len(prod_refs)})")


def _scan_cold_modules(imports: list[sqlite3.Row], *, fanin: bool) -> None:
    print("\n=== context_pipeline cold modules (import refs outside tests) ===")
    for mod in COLD_MODULES:
        refs = [r["file_path"] for r in imports if mod in (r["name"] or "")]
        prod = sorted({f for f in refs if not f.startswith("tests/")})
        test_only = bool(refs) and not prod
        flag = "TEST-ONLY" if test_only and refs else ("PROD" if prod else "ZERO")
        if flag != "PROD" or len(prod) <= 2:
            print(f"  {mod}: {flag} prod={prod[:5]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CodeGraph orphan scan")
    parser.add_argument("--fanin", action="store_true", help="Cross-check graph orphans with ripgrep prod fan-in")
    args = parser.parse_args()

    if not DB.is_file():
        print(f"Missing {DB}; run: codegraph sync")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if "nodes" not in tables:
        _print_schema(cur)
        return

    imports = _graph_imports(cur)
    _scan_root_orphans(imports, fanin=args.fanin)
    _scan_cold_modules(imports, fanin=args.fanin)
    _scan_cold_packages()


def _scan_cold_packages() -> None:
    """Offline packages that look orphan-like but must be kept by policy."""
    entries = (
        ("provider_probe", "Cold probe pipeline; not mounted on server.py"),
        ("scripts/eval_loop.py", "Cold eval harness (Q5-4 migrated from root)"),
    )
    print("\n=== Cold packages (keep — not slimming targets) ===")
    for rel, note in entries:
        path = ROOT / rel
        status = "present" if path.exists() else "missing"
        print(f"  KEEP {rel} ({status}) — {note}")


if __name__ == "__main__":
    main()
