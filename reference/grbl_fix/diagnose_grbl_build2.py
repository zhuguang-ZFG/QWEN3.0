"""Deep Grbl_Esp32 build diagnosis. Run: python D:\\QWEN3.0\\diagnose_grbl_build2.py"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
OUT = Path(r"D:\QWEN3.0\tmp\grbl_build_diag.txt")
LOG_DIR = OUT.parent


def run_capture(label: str, args: list[str], *, shell: bool = False, cwd: Path | None = None) -> str:
    lines = [f"\n=== {label} ===", f"cmd: {args!r} shell={shell}"]
    try:
        proc = subprocess.run(
            args,
            cwd=cwd or REPO,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=shell,
        )
        lines.append(f"exit_code={proc.returncode}")
        if proc.stdout:
            lines.append("--- stdout ---")
            lines.append(proc.stdout)
        if proc.stderr:
            lines.append("--- stderr ---")
            lines.append(proc.stderr)
        if not proc.stdout and not proc.stderr:
            lines.append("(no stdout/stderr)")
    except Exception as exc:
        lines.append(f"EXCEPTION: {exc}")
    return "\n".join(lines)


def tail_file(path: Path, n: int = 80) -> str:
    if not path.is_file():
        return f"(missing {path})"
    data = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(data[-n:])


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = [f"REPO={REPO}", f"cwd exists={REPO.is_dir()}"]

    env = os.environ.copy()
    env["PLATFORMIO_BUILD_FLAGS"] = "-DMACHINE_FILENAME=test_drive.h"
    chunks.append(f"PLATFORMIO_BUILD_FLAGS={env['PLATFORMIO_BUILD_FLAGS']}")

    # Basic toolchain probes
    for label, cmd, shell in [
        ("where pio", ["where", "pio"], False),
        ("where platformio", ["where", "platformio"], False),
        ("pio --version", ["pio", "--version"], False),
        ("python -m platformio --version", [sys.executable, "-m", "platformio", "--version"], False),
    ]:
        chunks.append(run_capture(label, cmd, shell=shell, cwd=REPO))

    # File redirect build (most reliable on Windows)
    build_log = LOG_DIR / "pio_run_redirect.log"
    cmdline = (
        f'cd /d "{REPO}" && set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME=test_drive.h && '
        f'pio run -v > "{build_log}" 2>&1'
    )
    chunks.append(f"\n=== pio run via cmd redirect ===\n{cmdline}")
    proc = subprocess.run(cmdline, shell=True, cwd=str(REPO))
    chunks.append(f"shell exit_code={proc.returncode}")
    chunks.append(f"--- {build_log} (last 120 lines) ---")
    chunks.append(tail_file(build_log, 120))

    # Fallback: python -m platformio
    build_log2 = LOG_DIR / "pio_module_redirect.log"
    cmdline2 = (
        f'cd /d "{REPO}" && set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME=test_drive.h && '
        f'"{sys.executable}" -m platformio run -v > "{build_log2}" 2>&1'
    )
    chunks.append(f"\n=== python -m platformio via cmd redirect ===\n{cmdline2}")
    proc2 = subprocess.run(cmdline2, shell=True, cwd=str(REPO))
    chunks.append(f"shell exit_code={proc2.returncode}")
    chunks.append(f"--- {build_log2} (last 120 lines) ---")
    chunks.append(tail_file(build_log2, 120))

    # Existing repo build logs
    for name in sorted(REPO.glob("build*.log")):
        chunks.append(f"\n=== existing {name.name} (last 40 lines) ===")
        chunks.append(tail_file(name, 40))

    text = "\n".join(chunks)
    OUT.write_text(text, encoding="utf-8")
    print(text[-12000:] if len(text) > 12000 else text)
    print(f"\nFull report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
