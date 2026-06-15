#!/usr/bin/env python3
"""Evaluate device drawing/writing model roles for admission reports.

Usage:
  python scripts/eval_device_model_role.py --list
  python scripts/eval_device_model_role.py --all
  python scripts/eval_device_model_role.py --role intent_parser
  python scripts/eval_device_model_role.py --all --json
  python scripts/eval_device_model_role.py --all --markdown

See docs/model_admission/TEMPLATE.md for report format.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.device_model_role_eval_specs import ROLE_SPECS, RoleEvalSpec, get_role_spec

_PYTEST_SUMMARY = re.compile(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) failed)?")


@dataclass
class RoleEvalResult:
    role_id: str
    label_zh: str
    backend_id: str
    admission_status: str
    fixture_count: int
    pass_count: int
    fail_count: int
    skipped: int
    pass_rate: float
    verdict: str
    pytest_command: str
    notes: str = ""


def _parse_pytest_output(text: str) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for line in reversed(text.splitlines()):
        match = _PYTEST_SUMMARY.search(line)
        if match:
            passed = int(match.group(1))
            skipped = int(match.group(2) or 0)
            failed = int(match.group(3) or 0)
            break
    return passed, failed, skipped


def _run_pytest(targets: tuple[str, ...]) -> tuple[int, int, int, str]:
    if not targets:
        return 0, 0, 0, ""
    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--tb=no"]
    proc = subprocess.run(
        cmd,
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    passed, failed, skipped = _parse_pytest_output(output)
    if proc.returncode != 0 and passed == 0 and failed == 0:
        failed = 1
    return passed, failed, skipped, " ".join(cmd)


def _verdict(spec: RoleEvalSpec, pass_rate: float, fail_count: int) -> str:
    if spec.admission_status == "defer":
        return "defer"
    if fail_count > 0:
        return "fail"
    if pass_rate >= spec.pass_rate_threshold:
        return "admit" if spec.admission_status == "admitted" else "admit_conditional"
    return "concerns"


def evaluate_role(spec: RoleEvalSpec) -> RoleEvalResult:
    if spec.admission_status == "defer" or not spec.pytest_targets:
        return RoleEvalResult(
            role_id=spec.role_id,
            label_zh=spec.label_zh,
            backend_id=spec.backend_id,
            admission_status=spec.admission_status,
            fixture_count=0,
            pass_count=0,
            fail_count=0,
            skipped=0,
            pass_rate=0.0,
            verdict="defer",
            pytest_command="(skipped — not implemented)",
            notes=spec.notes,
        )

    passed, failed, skipped, cmd = _run_pytest(spec.pytest_targets)
    total = passed + failed
    pass_rate = (passed / total) if total else 0.0
    return RoleEvalResult(
        role_id=spec.role_id,
        label_zh=spec.label_zh,
        backend_id=spec.backend_id,
        admission_status=spec.admission_status,
        fixture_count=total,
        pass_count=passed,
        fail_count=failed,
        skipped=skipped,
        pass_rate=round(pass_rate, 4),
        verdict=_verdict(spec, pass_rate, failed),
        pytest_command=cmd,
        notes=spec.notes,
    )


def evaluate_roles(role_ids: list[str] | None) -> list[RoleEvalResult]:
    if role_ids:
        specs = []
        for role_id in role_ids:
            spec = get_role_spec(role_id)
            if spec is None:
                raise SystemExit(f"unknown role: {role_id}")
            specs.append(spec)
    else:
        specs = list(ROLE_SPECS)
    return [evaluate_role(spec) for spec in specs]


def _print_table(results: list[RoleEvalResult]) -> None:
    print(f"Device model role eval — {date.today().isoformat()}")
    print(f"{'role':<20} {'verdict':<18} {'pass':>5} {'fail':>5} {'rate':>6}")
    for row in results:
        rate = f"{row.pass_rate:.0%}" if row.fixture_count else "—"
        print(
            f"{row.role_id:<20} {row.verdict:<18} {row.pass_count:>5} {row.fail_count:>5} {rate:>6}"
        )


def _markdown_report(results: list[RoleEvalResult]) -> str:
    lines = [
        f"# 设备绘图/写字模型角色评测 — {date.today().isoformat()}",
        "",
        "由 `python scripts/eval_device_model_role.py --all --markdown` 生成。",
        "",
        "| 角色 | 后端 ID | 夹具 | 通过 | 失败 | 通过率 | 裁决 |",
        "|------|---------|------|------|------|--------|------|",
    ]
    for row in results:
        rate = f"{row.pass_rate:.0%}" if row.fixture_count else "—"
        lines.append(
            f"| {row.label_zh} | `{row.backend_id}` | {row.fixture_count} | "
            f"{row.pass_count} | {row.fail_count} | {rate} | {row.verdict} |"
        )
    lines.extend(["", "## 复现命令", ""])
    for row in results:
        if row.pytest_command.startswith("python"):
            lines.append(f"- **{row.label_zh}**: `{row.pytest_command}`")
    lines.append("")
    lines.append("- 全量角色：`python scripts/eval_device_model_role.py --all`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate device model roles for admission")
    parser.add_argument("--role", action="append", dest="roles", help="Role id (repeatable)")
    parser.add_argument("--all", action="store_true", help="Evaluate all roles")
    parser.add_argument("--list", action="store_true", help="List role ids")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--markdown", action="store_true", help="Emit markdown report")
    args = parser.parse_args(argv)

    if args.list:
        for spec in ROLE_SPECS:
            print(f"{spec.role_id:20} {spec.admission_status:12} {spec.label_zh}")
        return 0

    if not args.all and not args.roles:
        parser.error("specify --all or --role <id>")

    results = evaluate_roles(args.roles)
    if args.json:
        print(json.dumps([asdict(row) for row in results], ensure_ascii=False, indent=2))
    elif args.markdown:
        print(_markdown_report(results), end="")
    else:
        _print_table(results)

    if any(row.verdict == "fail" for row in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
