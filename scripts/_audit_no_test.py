"""Count real no_test_file with current heuristic vs smarter check"""

import sys

sys.path.insert(0, "D:\\QWEN3.0")
import ast
from pathlib import Path

PROJECT = Path("D:/QWEN3.0")

# Ignored: test files, __init__, scripts, esp32
CORE_SCAN_DIRS = [
    "routes",
    "device_gateway",
    "context_pipeline",
    "routing_selector",
    "backends_registry",
    "device_intelligence",
    "device_ota",
    "device_voice",
    "device_memory",
    "device_ledger",
    "device_logic",
    "device_support",
    "device_policy",
    "device_workflow",
    "session_memory",

    "observability",
    "fleet",
    "provider_automation",
    "provider_inventory",
    "response_cleaner",
    "local_retrieval",
    "lima_mcp_stdio",
    "tool_gateway",
]

from scripts.guardian_test_index import find_test_file, clear_test_index_cache

clear_test_index_cache()

count_no_match = 0
count_match = 0
total = 0
no_test_files = []

for d in CORE_SCAN_DIRS:
    dd = PROJECT / d
    if not dd.is_dir():
        continue
    for f in sorted(dd.iterdir()):
        if not f.name.endswith(".py") or f.name == "__init__.py":
            continue
        if ".venv" in str(f) or "esp32" in str(f).lower() or "site-packages" in str(f):
            continue
        total += 1
        rel = str(f.relative_to(PROJECT))

        # Check if file has public functions
        has_public = False
        try:
            tree = ast.parse(f.read_text("utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        has_public = True
                        break
        except (SyntaxError, OSError):
            pass

        if not has_public:
            continue  # no public functions = no need for test

        result = find_test_file(rel)
        if result:
            count_match += 1
        else:
            count_no_match += 1
            no_test_files.append((rel, has_public))

print(f"Total scanned: {total}")
print(f"With public functions: {count_no_match + count_match}")
print(f"Has test match: {count_match}")
print(f"NO test match: {count_no_match}")
print()

if no_test_files:
    print("Files with no test match:")
    for f, has_public in no_test_files:
        print(f"  {f} (public_funcs=True)")
