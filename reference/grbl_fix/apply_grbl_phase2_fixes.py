"""Phase 2 code review fixes for D:\\Users\\Grbl_Esp32"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
REPORT = Path(r"D:\QWEN3.0\tmp\grbl_phase2_report.txt")
lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = path.with_suffix(path.suffix + f".bak_{stamp}")
    dst.write_bytes(path.read_bytes())
    log(f"backup: {dst}")


def patch_telnet(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    orig = text
    text = text.replace('        log_i("[TELNET]push %c", data);\n', "")
    text = text.replace('        log_i("[TELNET]buffer size %d", _RXbufferSize);\n', "")
    if text == orig:
        return False
    backup(path)
    path.write_text(text, encoding="utf-8", newline="")
    return True


def patch_websettings(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    orig = text
    # Align with Grbl LINE_BUFFER_SIZE (256) but fix off-by-one: use 255 bytes + NUL semantics
    text = re.sub(
        r"byte\s+line\[256\];\s*\n(\s*)int\s+len\s*=\s*file\.getBytes\(line,\s*255\);",
        "byte line[LINE_BUFFER_SIZE];\n\\1int len = file.getBytes(line, LINE_BUFFER_SIZE - 1);",
        text,
        count=1,
    )
    if text == orig:
        # fallback: only bump getBytes if buffer already LINE_BUFFER_SIZE
        text2 = text.replace("file.getBytes(line, 255)", "file.getBytes(line, LINE_BUFFER_SIZE - 1)")
        if text2 == orig:
            return False
        text = text2
    backup(path)
    path.write_text(text, encoding="utf-8", newline="")
    return True


def review_paper_system(path: Path) -> None:
    log("\n=== paper_system.cpp review ===")
    if not path.is_file():
        log("MISSING (skip custom review)")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    if re.search(r"\bdelay\s*\(", text):
        findings.append("uses delay() — verify not called during Cycle/motion")
    if re.search(r"\bdelayMicroseconds\s*\(", text):
        findings.append("uses delayMicroseconds()")
    if "sys.state" not in text and "State::" not in text:
        findings.append("no sys.state checks — verify interlocks with motion")
    if not re.search(r"limit|alarm|abort|hold", text, re.I):
        findings.append("no obvious limit/alarm/hold guards")
    if not findings:
        findings.append("no automatic red flags; manual runtime test still recommended")
    for f in findings:
        log(f"- {f}")
    log(f"lines: {len(text.splitlines())}")


def find_pio() -> list[str]:
    p = Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe"
    if p.is_file():
        return [str(p)]
    return ["pio"]


def build() -> int:
    env = os.environ.copy()
    env["PLATFORMIO_BUILD_FLAGS"] = "-DMACHINE_FILENAME=test_drive.h"
    pio = find_pio()
    cmd = f'cd /d "{REPO}" && set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME=test_drive.h && "{pio[0]}" run'
    log(f"\n=== build: {cmd} ===")
    return subprocess.call(cmd, shell=True)


def main() -> int:
    log(f"Phase2 fixes @ {datetime.now().isoformat()}")
    telnet = REPO / "Grbl_Esp32" / "src" / "WebUI" / "TelnetServer.cpp"
    web = REPO / "Grbl_Esp32" / "src" / "WebUI" / "WebSettings.cpp"
    paper = REPO / "Grbl_Esp32" / "Custom" / "paper_system.cpp"

    if patch_telnet(telnet):
        log("TelnetServer.cpp: removed per-char log_i in push()")
    else:
        log("TelnetServer.cpp: already clean or pattern not found")

    if patch_websettings(web):
        log("WebSettings.cpp: runLocalFile uses LINE_BUFFER_SIZE consistently")
    else:
        log("WebSettings.cpp: no change (pattern not found)")

    review_paper_system(paper)

    ec = build()
    log(f"BUILD exit_code={ec}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return ec


if __name__ == "__main__":
    raise SystemExit(main())
