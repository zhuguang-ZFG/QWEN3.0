"""Capture full platformio build log for Grbl_Esp32. Run: python D:\\QWEN3.0\\diagnose_grbl_build.py"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\Users\Grbl_Esp32")
LOG = Path(r"D:\QWEN3.0\tmp\grbl_build_full.log")


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PLATFORMIO_BUILD_FLAGS"] = "-DMACHINE_FILENAME=test_drive.h"
    cmds = [
        ["platformio", "run"],
        ["pio", "run"],
    ]
    last = None
    for cmd in cmds:
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
            last = proc
            if proc.returncode == 0 or (proc.stdout or proc.stderr):
                break
        except FileNotFoundError:
            continue
    if last is None:
        LOG.write_text("ERROR: platformio/pio not found in PATH\n", encoding="utf-8")
        print(LOG.read_text(encoding="utf-8"))
        return 127

    text = f"cmd={' '.join(cmd)}\nexit_code={last.returncode}\n\n=== STDOUT ===\n{last.stdout}\n\n=== STDERR ===\n{last.stderr}\n"
    LOG.write_text(text, encoding="utf-8")
    print(text[-8000:] if len(text) > 8000 else text)
    return last.returncode


if __name__ == "__main__":
    raise SystemExit(main())
