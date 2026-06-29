"""Write changelog, commit, push to GitHub."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
DOC_SRC = Path(r"D:\QWEN3.0\变更说明_代码审查_2026-06-27.md")
DOC_DST = REPO / "doc" / "变更说明_代码审查_2026-06-27.md"

FILES = [
    "Grbl_Esp32/src/Settings.cpp",
    "Grbl_Esp32/src/MotionControl.cpp",
    "Grbl_Esp32/src/WebUI/TelnetServer.cpp",
    "Grbl_Esp32/src/WebUI/WebSettings.cpp",
    "Grbl_Esp32/Custom/paper_system.cpp",
    "Grbl_Esp32/src/Config.h",
    "doc/变更说明_代码审查_2026-06-27.md",
]


def run(cmd: list[str]) -> tuple[int, str]:
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if out.strip():
        print(out)
    return p.returncode, out


def main() -> int:
    DOC_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOC_SRC, DOC_DST)
    print("copied changelog ->", DOC_DST)

    for f in FILES:
        if (REPO / f).is_file():
            run(["git", "add", f])
        else:
            print("WARN missing", f)

    run(["git", "status", "--short"])

    msg = (
        "fix: code review fixes, paper path waits, and security hardening\n\n"
        "See doc/变更说明_代码审查_2026-06-27.md for full changelog."
    )
    rc, _ = run(["git", "commit", "-m", msg])
    if rc != 0:
        return rc

    rc, _ = run(["git", "push", "-u", "origin", "HEAD"])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
