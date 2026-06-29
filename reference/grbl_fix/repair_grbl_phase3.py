"""Repair paper_system.cpp after phase3 guard bug + fix WebSettings getBytes."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
PAPER = REPO / "Grbl_Esp32" / "Custom" / "paper_system.cpp"
WEB = REPO / "Grbl_Esp32" / "src" / "WebUI" / "WebSettings.cpp"
REPORT = Path(r"D:\QWEN3.0\tmp\grbl_phase3_repair_report.txt")

PAPER_HELPERS = """
// Paper path safety helpers
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

# Only helpers + delay replacement (no auto function guards)
GUARD_FUNCTIONS: set[str] = set()


def log(lines: list[str], msg: str) -> None:
    print(msg)
    lines.append(msg)


def restore_paper_backup() -> Path | None:
    backups = sorted(PAPER.parent.glob("paper_system.cpp.bak_*"))
    if not backups:
        return None
    src = backups[-1]
    PAPER.write_bytes(src.read_bytes())
    return src


def patch_paper_conservative(text: str) -> str:
    # strip broken auto-guards from phase3
    text = re.sub(
        r"\n\s*if \(!paper_motion_allowed\(\)\) \{\n\s*return;\n\s*\}\n",
        "\n",
        text,
    )
    # remove duplicate helpers blocks, keep one
    while text.count("static bool paper_motion_allowed") > 1:
        text = re.sub(
            r"\n// Paper path safety helpers[\s\S]*?static bool paper_blocking_wait[\s\S]*?\}\n",
            "\n",
            text,
            count=1,
        )
    if "paper_motion_allowed" not in text:
        m = re.search(r"(#include[^\n]+\n(?:#include[^\n]+\n)*)", text)
        insert = m.end() if m else 0
        text = text[:insert] + "\n" + PAPER_HELPERS + text[insert:]

    for fn in GUARD_FUNCTIONS:
        if not fn:
            continue
        pat = rf"(\n(?:void|bool|uint8_t|int|float)\s+{re.escape(fn)}\s*\([^{{]*\{{\s*\n)"
        if re.search(pat, text):

            def add(m: re.Match, _fn=fn) -> str:
                body = m.group(1)
                if "paper_motion_allowed" in text[text.find(body) : text.find(body) + 160]:
                    return body
                return body + "    if (!paper_motion_allowed()) {\n        return;\n    }\n"

            text = re.sub(pat, add, text, count=1)

    # delay -> paper_blocking_wait (void paths only use return;)
    text = re.sub(
        r"\bdelay\s*\(\s*(\d+)\s*\)\s*;",
        r"if (!paper_blocking_wait(\1)) { return; }",
        text,
    )
    return text


def patch_websettings(text: str) -> tuple[str, bool]:
    orig = text
    text = text.replace(
        "currentline.getBytes(line, 255);",
        "currentline.getBytes(line, LINE_BUFFER_SIZE - 1);",
    )
    text = re.sub(
        r"(\s+)char\s+line\[256\];",
        r"\1char line[LINE_BUFFER_SIZE];",
        text,
        count=1,
    )
    return text, text != orig


def build(machine: str) -> int:
    pio = Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe"
    cmd = f'cd /d "{REPO}" && set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME={machine} && "{pio}" run'
    return subprocess.call(cmd, shell=True)


def main() -> int:
    lines: list[str] = [f"repair @ {datetime.now().isoformat()}"]
    bak = restore_paper_backup()
    log(lines, f"restored backup: {bak.name if bak else 'NONE'}")

    paper = patch_paper_conservative(PAPER.read_text(encoding="utf-8", errors="replace"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    PAPER.with_suffix(".cpp.bak_" + stamp).write_bytes(PAPER.read_bytes())
    PAPER.write_text(paper, encoding="utf-8", newline="")
    log(lines, "paper_system.cpp: conservative re-patch")

    if WEB.is_file():
        w, changed = patch_websettings(WEB.read_text(encoding="utf-8", errors="replace"))
        if changed:
            WEB.with_suffix(".cpp.bak_" + stamp).write_bytes(WEB.read_bytes())
            WEB.write_text(w, encoding="utf-8", newline="")
            log(lines, "WebSettings.cpp: LINE_BUFFER_SIZE fix")
        else:
            log(lines, "WebSettings.cpp: no change")

    ec1 = build("test_drive.h")
    log(lines, f"test_drive exit={ec1}")
    ec2 = build("custom_3axis_hr4988.h")
    log(lines, f"custom_3axis_hr4988 exit={ec2}")
    ec = 0 if ec1 == 0 and ec2 == 0 else 1
    log(lines, f"OVERALL={ec}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return ec


if __name__ == "__main__":
    raise SystemExit(main())
