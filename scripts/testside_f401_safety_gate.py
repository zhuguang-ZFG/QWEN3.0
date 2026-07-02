#!/usr/bin/env python3
"""测试侧 F401 安全门 — 防范批量 test 端 `ruff --fix --select F401` 误删
import 导致 pytest 收集失败。

背景（findings.md 2026-07-03 G1b 结项 lesson learned）
==================================================

测试侧 F401（未使用导入）存在四类「具名失效型态」对静态分析
不可见 / 容易漏检：

(a) ``from <module_dotted> import <name>`` 直引 —— 显式 ImportFrom，
    AST 可解析。
(b) 模块别名访问 ``<alias>.<name>``（例 ``dg._reset_for_tests()``，
    其中 ``from routes import device_gateway as dg``）——
    需别名反向解析（F1 批次首跑 12 failed/22 errors 根因）。
(c) pytest 通过 ``conftest.py`` 把 ``tests/`` 加到 ``sys.path``，
    消费者写 ``from <baseline> import <name>`` 而非
    ``from <dotted.path> import <name>``（G1b 第一轮盲点根因）。
(d) pytest fixture 字符串匹配注入（最隐蔽，G1b 三轮盲点根因）——
    import 名作为测试函数签名参数名，被 pytest 在收集期通过参数名
    字符串匹配发现并注入；ruff 看不到这种间接使用，会误判为死
    导入并删除。

(d) 类型的危险在于：被删后 *helper module* 的 import 仍在原文件，
只是消费测试文件中 fixture 不再可用 → ``pytest`` 收集时报
``fixture '<name>' not found`` → ERROR（非 fail），可能整文件 0 个
test 跑就整文件中断。

本安全门
=========

**触发条件**：调用方提供 staged 文件列表（``--paths``）中包含 ``tests/``
路径下的 ``.py`` 文件时，安全门执行 ``python -m pytest --collect-only -q``，
若收集失败（含 ERROR 等级），打印失败文件并返回非零退出码，阻止提交。

**为什么是 pytest --collect-only 而非 AST 静态分析**：因为四类盲点
（尤其 (d)）只能被运行时 pytest 收集发现，静态分析天然不可靠。
唯一可靠的安全网就是「让 pytest 自己说 OK」。

**避开预先存在的破坏性 collect error**：通过 ``--baseline-skip-from``
参数接收一个文本文件，每行一个测试文件路径；这些文件视为 baseline
已知会错的「预先存在」，本门跳过。本批次修改它们的处理不视为破坏。

用法
=====

::

    # 直接对一组 staged 文件运行（pre-commit 调用入口）
    python scripts/testside_f401_safety_gate.py \\
        --paths tests/test_device_app_sharing.py \\
        --paths tests/fake_u1_helpers.py

    # 等价:从 stdin 每行一个路径
    git diff --cached --name-only -- 'tests/*.py' | \\
        python scripts/testside_f401_safety_gate.py --paths-file -

    # 自定义 pytest 解释器
    python scripts/testside_f401_safety_gate.py --paths <...> \\
        --python .venv310/Scripts/python.exe

退出码
-------

- 0：未触发（无 tests/ staged）或收集成功
- 1：收集失败或参数错误
- 2：暂存了 tests/ 文件但 解释器 / pytest 缺失
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent


def _normalize_paths(paths_arg: list[str]) -> list[Path]:
    """Resolve and normalize each input path against repo root."""
    normalized: list[Path] = []
    for p in paths_arg:
        if p == "-":
            for line in sys.stdin:
                line = line.strip()
                if line:
                    normalized.append((ROOT / line).resolve())
        else:
            normalized.append((ROOT / p).resolve())
    return normalized


def _staged_test_files(paths: Iterable[Path]) -> list[Path]:
    """Keep only existing .py files under tests/ that lie inside repo root."""
    root = ROOT
    tests_root = (root / "tests").resolve()
    kept: list[Path] = []
    for p in paths:
        try:
            rel = p.relative_to(tests_root)
        except ValueError:
            continue
        if rel.suffix == ".py" and p.exists():
            kept.append(p)
    return kept


def _load_baseline_skip(path: str | None) -> set[Path]:
    """Return absolute-path set of files to NOT attribute failures to (known pre-existing).
    Always reads from a file path, never stdin (stdin is reserved for --paths)."""
    if not path:
        return set()
    skip = set[Path]()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            skip.add((ROOT / line).resolve())
    return skip


def run_collection(python: str) -> tuple[int, str]:
    """Run `python -m pytest --collect-only -q`. Return (returncode, stdout tail)."""
    cmd = [python, "-m", "pytest", "--collect-only", "-q", "--no-header"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    out = proc.stdout + proc.stderr
    return proc.returncode, out


def extract_collect_error_files(out: str, baseline: set[Path]) -> list[Path]:
    """Parse pytest collection output for ERROR files; drop baseline ones.

    Pytest --collect-only emits lines like ``ERROR tests/foo/test_x.py`` at tail.
    Returns absolute Path objects whose collection failed and are NOT in baseline.
    """
    files: list[Path] = []
    seen: set[Path] = set()
    for line in out.splitlines():
        stripped = line.strip()
        # Skip summary lines like "ERROR tests/foo/test_x.py - ImportError: ..."
        if stripped.startswith("ERROR "):
            tail = stripped[len("ERROR ") :]
            path_part = tail.split(" - ", 1)[0].strip()
            if not path_part:
                continue
            abs_path = (ROOT / path_part).resolve()
            if abs_path in baseline or abs_path in seen:
                continue
            seen.add(abs_path)
            files.append(abs_path)
    return files


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--paths",
        action="append",
        default=[],
        help="Staged file path (repeatable). Use '-' to read paths from stdin, one per line.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use for running pytest (default: current).",
    )
    parser.add_argument(
        "--baseline-skip-from",
        default=None,
        dest="baseline_skip_from",
        help="File listing known pre-existing broken test files to skip (one per line). NOT stdin-compatible to avoid clash with --paths -.",
    )
    return parser


def _print_blocked(failing: list[Path], out: str) -> None:
    """Emit the standard "COMMIT BLOCKED" message + failing paths + collection tail."""
    print("=" * 80, file=sys.stderr)
    print("COMMIT BLOCKED: pytest --collect-only reports collection failures.", file=sys.stderr)
    print("This is the test-side F401 safety gate (findings.md G1b lesson learned).", file=sys.stderr)
    print("Likely causes (per findings.md four-failure-types):", file=sys.stderr)
    print("  (a) direct from-import removal", file=sys.stderr)
    print("  (b) module alias access (alias.name)", file=sys.stderr)
    print("  (c) pytest sys.path baseline name import", file=sys.stderr)
    print("  (d) pytest fixture string-match injection (ruff INVISIBLE)", file=sys.stderr)
    print("Failing test files (NOT in baseline-skip):", file=sys.stderr)
    for p in failing:
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(p)
        print(f"  - {rel}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    tail = "\n".join(out.splitlines()[-30:])
    print(tail, file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    paths_arg = list(args.paths)
    if not paths_arg:
        # Default: read from stdin if piped, else nothing to do.
        if not sys.stdin.isatty():
            paths_arg = ["-"]
        else:
            print("testside_f401_safety_gate: no --paths given and stdin is a tty; nothing to do.")
            return 0

    paths = _normalize_paths(paths_arg)
    baseline = _load_baseline_skip(args.baseline_skip_from)

    staged_tests = _staged_test_files(paths)
    if not staged_tests:
        print("testside_f401_safety_gate: no tests/ files staged; skipping collection safety gate.")
        return 0

    print(f"testside_f401_safety_gate: {len(staged_tests)} test file(s) staged; running pytest --collect-only...")
    rc, out = run_collection(args.python)
    if rc == 0:
        print("testside_f401_safety_gate: pytest --collect-only OK.")
        return 0

    failing = extract_collect_error_files(out, baseline)
    if not failing:
        # Collection failed but all offending files are in baseline → treat as pre-existing.
        print("testside_f401_safety_gate: collection had ERRORs but all are in baseline-skip; PASS.")
        return 0

    _print_blocked(failing, out)
    return 1


if __name__ == "__main__":
    sys.exit(main())
