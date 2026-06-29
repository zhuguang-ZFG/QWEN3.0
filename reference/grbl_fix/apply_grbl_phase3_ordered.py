"""Phase 3 ordered: (1) WebSettings (2) paper_system (3) security + dual build"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
REPORT = Path(r"D:\QWEN3.0\tmp\grbl_phase3_report.txt")
lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = path.with_suffix(path.suffix + f".bak_{stamp}")
    dst.write_bytes(path.read_bytes())
    log(f"backup: {dst.name}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


PAPER_HELPERS = """
// Paper path safety helpers (phase-3 review)
static bool paper_motion_allowed() {
    if (sys.abort) {
        return false;
    }
    switch (sys.state) {
        case State::Alarm:
        case State::Cycle:
        case State::Hold:
        case State::Homing:
            return false;
        default:
            return true;
    }
}

static bool paper_blocking_wait(uint32_t ms) {
    if (!paper_motion_allowed()) {
        return false;
    }
    return delay_msec(ms, DwellMode::Dwell);
}

"""


def fix_websettings(path: Path) -> bool:
    log("\n=== Step 1: WebSettings.cpp ===")
    if not path.is_file():
        log("MISSING")
        return False
    text = read_text(path)
    orig = text
    subs = [
        (
            r"byte\s+line\[256\];\s*\r?\n(\s*)int\s+len\s*=\s*file\.getBytes\(line,\s*255\);",
            "byte line[LINE_BUFFER_SIZE];\n\\1int len = file.getBytes(line, LINE_BUFFER_SIZE - 1);",
        ),
        (
            r"byte\s+line\[255\];\s*\r?\n(\s*)int\s+len\s*=\s*file\.getBytes\(line,\s*254\);",
            "byte line[LINE_BUFFER_SIZE];\n\\1int len = file.getBytes(line, LINE_BUFFER_SIZE - 1);",
        ),
        (
            r"byte\s+line\[LINE_BUFFER_SIZE\];\s*\r?\n(\s*)int\s+len\s*=\s*file\.getBytes\(line,\s*255\);",
            "byte line[LINE_BUFFER_SIZE];\n\\1int len = file.getBytes(line, LINE_BUFFER_SIZE - 1);",
        ),
        (
            r"uint8_t\s+line\[256\];\s*\r?\n(\s*)int\s+len\s*=\s*file\.getBytes\(line,\s*255\);",
            "uint8_t line[LINE_BUFFER_SIZE];\n\\1int len = file.getBytes(line, LINE_BUFFER_SIZE - 1);",
        ),
    ]
    for pat, repl in subs:
        text, n = re.subn(pat, repl, text, count=1)
        if n:
            break
    if text == orig:
        log("pattern not found; context:")
        for i, ln in enumerate(text.splitlines(), 1):
            if "runLocalFile" in ln or ("getBytes" in ln and "line" in ln):
                log(f"  L{i}: {ln.rstrip()}")
        return False
    backup(path)
    write_text(path, text)
    log("OK: runLocalFile uses LINE_BUFFER_SIZE")
    return True


def fix_paper_system(path: Path) -> bool:
    log("\n=== Step 2: paper_system.cpp ===")
    if not path.is_file():
        log("MISSING")
        return False
    text = read_text(path)
    orig = text

    if "paper_motion_allowed" not in text:
        m = re.search(r"(#include[^\n]+\n(?:#include[^\n]+\n)*)", text)
        insert = m.end() if m else 0
        text = text[:insert] + "\n" + PAPER_HELPERS + text[insert:]

    skip_guard = {
        "machine_init",
        "display_init",
        "paper_motion_allowed",
        "paper_blocking_wait",
    }

    def guard_for(name: str) -> str:
        return f"\n    if (!paper_motion_allowed()) {{\n        return;\n    }}\n"

    for m in list(re.finditer(r"\n(void\s+(\w+)\s*\([^)]*\)\s*\{)", text)):
        name = m.group(2)
        if name in skip_guard:
            continue
        if not re.search(r"paper|feed|motor|user_", name, re.I):
            continue
        brace_end = m.end()
        window = text[brace_end : brace_end + 120]
        if "paper_motion_allowed" in window:
            continue
        text = text[:brace_end] + guard_for(name) + text[brace_end:]

    text = re.sub(
        r"\bdelay\s*\(\s*(\d+)\s*\)\s*;",
        r"if (!paper_blocking_wait(\1)) { return; }",
        text,
    )

    if text == orig:
        log("no edits (already patched?)")
        return False
    backup(path)
    write_text(path, text)
    log("OK: guards + delay_msec via paper_blocking_wait")
    return True


def fix_security() -> None:
    log("\n=== Step 3: Security (configure-features.py) ===")
    script = REPO / "configure-features.py"
    if not script.is_file():
        log("configure-features.py missing")
        return
    steps = [
        [sys.executable, str(script), "-e", "AUTHENTICATION"],
        [sys.executable, str(script), "-d", "TELNET", "OTA"],
    ]
    for cmd in steps:
        log("RUN: " + " ".join(cmd))
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        log((p.stdout or "") + (p.stderr or ""))
        log(f"exit={p.returncode}")


def build(machine: str) -> int:
    pio = Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe"
    exe = str(pio) if pio.is_file() else "pio"
    log_file = REPORT.parent / f"build_{machine.replace('.h', '')}.log"
    cmd = (
        f'cd /d "{REPO}" && set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME={machine} && "{exe}" run > "{log_file}" 2>&1'
    )
    log(f"\nBUILD {machine}: {cmd}")
    rc = subprocess.call(cmd, shell=True)
    tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-15:] if log_file.is_file() else []
    for ln in tail:
        log(ln)
    log(f"exit_code={rc} log={log_file}")
    return rc


def main() -> int:
    log(f"Phase3 @ {datetime.now().isoformat()}")
    web = REPO / "Grbl_Esp32" / "src" / "WebUI" / "WebSettings.cpp"
    paper = REPO / "Grbl_Esp32" / "Custom" / "paper_system.cpp"

    fix_websettings(web)
    fix_paper_system(paper)
    fix_security()

    ec1 = build("test_drive.h")
    ec2 = build("custom_3axis_hr4988.h")
    ec = 0 if ec1 == 0 and ec2 == 0 else 1
    log(f"\nOVERALL exit_code={ec}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return ec


if __name__ == "__main__":
    raise SystemExit(main())
