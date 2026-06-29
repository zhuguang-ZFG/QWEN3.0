#!/usr/bin/env python3
"""Apply Grbl_Esp32 code review fixes. Run: python D:\\QWEN3.0\\apply_grbl_fixes.py"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
REPORT = Path(r"D:\QWEN3.0\tmp\grbl_fix_report.txt")
PATCH = Path(r"D:\QWEN3.0\grbl_review_fixes.patch")
SETTINGS = REPO / "Grbl_Esp32" / "src" / "Settings.cpp"
MOTION = REPO / "Grbl_Esp32" / "src" / "MotionControl.cpp"


def log(lines: list[str], msg: str) -> None:
    print(msg)
    lines.append(msg)


def backup(path: Path, lines: list[str]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, dest)
    log(lines, f"Backup: {dest}")


def patch_settings(text: str) -> tuple[str, bool]:
    old = "return sys.state == State::Cycle && sys.state == State::Hold;"
    new = "return sys.state == State::Cycle || sys.state == State::Hold;"
    if old in text:
        return text.replace(old, new), True
    if new in text:
        return text, False
    raise RuntimeError("Settings.cpp: notCycleOrHold pattern not found")


def patch_motion(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    early = '    grbl_msg_sendf(CLIENT_SERIAL, MsgLevel::Info, "Found");\r\n'
    if early in text:
        text = text.replace(early, "")
        notes.append("removed early Found (CRLF)")
    elif '    grbl_msg_sendf(CLIENT_SERIAL, MsgLevel::Info, "Found");\n' in text:
        text = text.replace('    grbl_msg_sendf(CLIENT_SERIAL, MsgLevel::Info, "Found");\n', "")
        notes.append("removed early Found (LF)")

    if re.search(
        r"sys\.probe_succeeded = true;.*grbl_msg_sendf\(CLIENT_SERIAL, MsgLevel::Info, \"Found\"\)",
        text,
        re.S,
    ):
        notes.append("Found already after probe_succeeded")
        return text, notes

    patterns = [
        (
            "        sys.probe_succeeded = true;  // Indicate to system the probing cycle completed successfully.\r\n    }",
            '        sys.probe_succeeded = true;  // Indicate to system the probing cycle completed successfully.\r\n        grbl_msg_sendf(CLIENT_SERIAL, MsgLevel::Info, "Found");\r\n    }',
            "added Found after probe_succeeded (CRLF)",
        ),
        (
            "        sys.probe_succeeded = true;  // Indicate to system the probing cycle completed successfully.\n    }",
            '        sys.probe_succeeded = true;  // Indicate to system the probing cycle completed successfully.\n        grbl_msg_sendf(CLIENT_SERIAL, MsgLevel::Info, "Found");\n    }',
            "added Found after probe_succeeded (LF)",
        ),
    ]
    for old, new, note in patterns:
        if old in text:
            text = text.replace(old, new)
            notes.append(note)
            return text, notes

    raise RuntimeError("MotionControl.cpp: probe success block pattern not found")


def try_git_apply(lines: list[str]) -> bool:
    if not PATCH.is_file():
        return False
    proc = subprocess.run(
        ["git", "apply", "--check", str(PATCH)],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        log(lines, "git apply --check failed; using Python patch")
        return False
    proc = subprocess.run(["git", "apply", str(PATCH)], cwd=REPO, capture_output=True, text=True)
    log(lines, f"git apply: exit {proc.returncode}")
    return proc.returncode == 0


def run_build(lines: list[str]) -> int:
    env = os.environ.copy()
    env["PLATFORMIO_BUILD_FLAGS"] = "-DMACHINE_FILENAME=test_drive.h"
    build_log = Path(r"D:\QWEN3.0\tmp\grbl_build_full.log")
    build_log.parent.mkdir(parents=True, exist_ok=True)
    log(lines, "Running platformio run ...")
    proc = None
    for cmd in (["platformio", "run"], ["pio", "run"]):
        try:
            proc = subprocess.run(
                cmd,
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            break
        except FileNotFoundError:
            continue
    if proc is None:
        log(lines, "BUILD error: platformio/pio not found in PATH")
        return 127
    combined = (proc.stdout or "") + (proc.stderr or "")
    build_log.write_text(f"cmd={' '.join(cmd)}\nexit_code={proc.returncode}\n\n{combined}", encoding="utf-8")
    log(lines, f"BUILD exit_code={proc.returncode}")
    log(lines, f"Full log: {build_log}")
    tail = combined.splitlines()[-40:] if combined else ["(no build output captured)"]
    lines.extend(tail)
    return proc.returncode


def main() -> int:
    lines: list[str] = [f"REPO={REPO}", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    try:
        if not SETTINGS.is_file() or not MOTION.is_file():
            raise FileNotFoundError("Settings.cpp or MotionControl.cpp missing")

        if not try_git_apply(lines):
            backup(SETTINGS, lines)
            backup(MOTION, lines)

            sc = SETTINGS.read_text(encoding="utf-8", errors="replace")
            sc, changed_s = patch_settings(sc)
            if changed_s:
                log(lines, "Settings.cpp: patched && -> ||")
            else:
                log(lines, "Settings.cpp: already patched")
            SETTINGS.write_text(sc, encoding="utf-8", newline="")

            mc = MOTION.read_text(encoding="utf-8", errors="replace")
            mc, motion_notes = patch_motion(mc)
            for n in motion_notes:
                log(lines, f"MotionControl.cpp: {n}")
            MOTION.write_text(mc, encoding="utf-8", newline="")

        diff = subprocess.run(
            ["git", "diff", "--", "Grbl_Esp32/src/Settings.cpp", "Grbl_Esp32/src/MotionControl.cpp"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log(lines, "=== git diff ===")
        lines.append(diff.stdout or "(no diff)")

        code = run_build(lines)
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return code

    except Exception as exc:
        log(lines, f"ERROR: {exc}")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
