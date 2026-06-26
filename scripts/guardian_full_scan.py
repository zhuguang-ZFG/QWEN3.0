"""Full-directory scanner used by lima_guardian."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scripts.guardian_scanner import CodeScanner, PROJECT

CORE_SCAN_DIRS = (
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
)


class FullScanner:
    @staticmethod
    def scan(modules: list[str] | None = None) -> dict:
        all_findings: dict[str, list] = defaultdict(list)
        paths = [PROJECT / m for m in modules] if modules else [PROJECT / d for d in CORE_SCAN_DIRS]

        scanned = 0
        for path in paths:
            if path.is_dir():
                for py_file in sorted(path.rglob("*.py")):
                    if py_file.name == "__init__.py":
                        continue
                    if "site-packages" in str(py_file) or ".venv" in str(py_file):
                        continue
                    if "esp32" in str(py_file).lower():
                        continue
                    for f in CodeScanner.scan_file(py_file):
                        all_findings[f["type"]].append(f)
                    scanned += 1
            elif path.is_file() and path.suffix == ".py":
                for f in CodeScanner.scan_file(path):
                    all_findings[f["type"]].append(f)
                scanned += 1

        errors, warnings, infos = [], [], []
        for flist in all_findings.values():
            for f in flist:
                if f["severity"] == "error":
                    errors.append(f)
                elif f["severity"] == "warning":
                    warnings.append(f)
                else:
                    infos.append(f)

        return {
            "scanned": scanned,
            "total_findings": len(errors) + len(warnings) + len(infos),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "by_type": {k: len(v) for k, v in all_findings.items()},
            "timestamp": datetime.now().isoformat(),
        }
