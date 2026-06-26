#!/usr/bin/env python3
"""
LiMa 代码守卫 —— 全量扫描 + 增量监控。

用法:
  python scripts/lima_guardian.py --full-scan
  python scripts/lima_guardian.py --baseline
  python scripts/lima_guardian.py --watch
  python scripts/lima_guardian.py --print-findings
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.guardian_full_scan import CORE_SCAN_DIRS, FullScanner
from scripts.guardian_scanner import CodeScanner, PROJECT

# Re-export for tests and MCP adapters
from scripts.guardian_scanner import _check_route_registration  # noqa: F401

GUARDIAN = PROJECT / ".guardian"
FINDINGS_FILE = GUARDIAN / "findings.json"
BASELINE_FILE = GUARDIAN / "baseline.json"

logging.basicConfig(level=logging.INFO, format="[guardian] %(message)s")
log = logging.getLogger(__name__)


class Watchdog:
    """文件变更监听器（轻量轮询）"""

    def __init__(self, interval: int = 30):
        self.interval = interval
        self.snapshots: dict[str, float] = {}
        self._build_snapshot()

    def _iter_py_files(self):
        for d in CORE_SCAN_DIRS:
            dd = PROJECT / d
            if not dd.is_dir():
                continue
            for f in os.listdir(str(dd)):
                if f.endswith(".py"):
                    yield str(dd / f)

    def _build_snapshot(self):
        for fp in self._iter_py_files():
            self.snapshots[fp] = os.path.getmtime(fp) if os.path.exists(fp) else 0

    def poll(self) -> list:
        changes = []
        for key in self._iter_py_files():
            current = os.path.getmtime(key) if os.path.exists(key) else 0
            if key not in self.snapshots:
                changes.append(("new", key))
            elif current > self.snapshots[key]:
                changes.append(("modified", key))
            self.snapshots[key] = current
        return changes


def _notify_desktop_errors(error_findings: list) -> None:
    if not error_findings:
        return
    toast_script = Path(__file__).resolve().parent / "toast_notify.ps1"
    if not toast_script.is_file():
        log.debug("toast_notify.ps1 missing, skip desktop notification")
        return
    msg = "; ".join(f"{f['file']}:{f['message']}" for f in error_findings[:3])
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(toast_script),
                "-Title",
                f"LiMa Guard: {len(error_findings)} issues",
                "-Message",
                msg,
            ],
            timeout=5,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("desktop toast failed: %s", type(exc).__name__)


def print_summary(result: dict):
    print(f"\n{'=' * 50}")
    print("📋 LiMa 守卫报告")
    print(f"{'=' * 50}")
    print(f"扫描文件: {result['scanned']}")
    print(f"发现问题: {result['total_findings']}")
    print(f"  🔴 错误: {len(result['errors'])}")
    print(f"  🟡 警告: {len(result['warnings'])}")
    print(f"  ℹ️  提示: {len(result['infos'])}")
    print()

    if result["errors"]:
        print("🔴 错误:")
        for f in result["errors"][:10]:
            print(f"  {f['file']}:{f['line']} — {f['message']}")
        print()

    if result["warnings"]:
        print("🟡 警告:")
        for f in result["warnings"][:10]:
            print(f"  {f['file']}:{f['line']} — {f['message']}")
        print()

    if result["by_type"]:
        print("分类统计:")
        for ftype, count in sorted(result["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {ftype:30s}: {count}")


def _save_scan_result(result: dict) -> None:
    GUARDIAN.mkdir(parents=True, exist_ok=True)
    FINDINGS_FILE.write_text(
        json.dumps({k: v for k, v in result.items() if k != "by_type"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    baseline = {
        "scanned": result["scanned"],
        "total": result["total_findings"],
        "errors": [{"file": f["file"], "message": f["message"]} for f in result["errors"]],
        "warnings": [{"file": f["file"], "message": f["message"]} for f in result["warnings"]],
        "by_type": result["by_type"],
        "timestamp": result["timestamp"],
    }
    BASELINE_FILE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_watch() -> None:
    log.info("启动增量守护模式（每 30 秒检测一次）...")
    wd = Watchdog()
    try:
        while True:
            for change_type, file_path in wd.poll():
                fp = Path(file_path)
                log.info("检测到变更: %s %s", change_type, fp.name)
                findings = CodeScanner.scan_file(fp)
                existing = []
                if FINDINGS_FILE.exists():
                    try:
                        data = json.loads(FINDINGS_FILE.read_text("utf-8"))
                        existing = data.get("errors", []) + data.get("warnings", [])
                    except (json.JSONDecodeError, KeyError):
                        existing = []

                existing_ids = {f["id"] for f in existing}
                new_f = [f for f in findings if f["id"] not in existing_ids]
                if not new_f:
                    continue

                for f in new_f:
                    log.info("  → %s: %s", f["severity"], f["message"])
                _notify_desktop_errors([f for f in new_f if f["severity"] == "error"])
                existing.extend(new_f)
                FINDINGS_FILE.write_text(
                    json.dumps(
                        {
                            "errors": [f for f in existing if f["severity"] == "error"],
                            "warnings": [f for f in existing if f["severity"] == "warning"],
                            "infos": [],
                            "scanned": len(existing),
                            "timestamp": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            time.sleep(wd.interval)
    except KeyboardInterrupt:
        log.info("守护进程已停止")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LiMa 代码守卫")
    parser.add_argument("--full-scan", action="store_true", help="全量扫描全项目")
    parser.add_argument("--baseline", action="store_true", help="刷新基线")
    parser.add_argument("--watch", action="store_true", help="增量守护模式")
    parser.add_argument("--print-findings", action="store_true", help="查看当前发现")
    parser.add_argument("--module", "-m", help="仅扫描指定模块")
    args = parser.parse_args()

    if args.full_scan or args.baseline:
        if args.module:
            result = FullScanner.scan(modules=[args.module])
        else:
            log.info("开始全量扫描...")
            result = FullScanner.scan()
        _save_scan_result(result)
        print_summary(result)
        log.info("已保存基线到 %s", GUARDIAN)
        return

    if args.print_findings:
        if FINDINGS_FILE.exists():
            findings = json.loads(FINDINGS_FILE.read_text("utf-8"))
            errs = findings.get("errors", [])
            warns = findings.get("warnings", [])
            print(f"当前发现: {len(errs) + len(warns)}")
            print(f"  🔴 错误: {len(errs)}")
            for f in errs[:15]:
                print(f"    {f['file']}:{f.get('line', 0)} — {f['message']}")
            print(f"  🟡 警告: {len(warns)}")
            for f in warns[:10]:
                print(f"    {f['file']}:{f.get('line', 0)} — {f['message']}")
        else:
            print("暂无发现。运行 --full-scan 进行首次扫描。")
        return

    if args.watch:
        _run_watch()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
