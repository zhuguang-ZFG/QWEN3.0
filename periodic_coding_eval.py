"""Background periodic coding-backend eval (default off).

Enable with ``LIMA_PERIODIC_CODING_EVAL=1``. Interval hours via
``LIMA_CODING_EVAL_INTERVAL_HOURS`` (default 168 = weekly).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from eval_preflight import check_eval_health, quick_backend_list

logger = logging.getLogger("periodic_coding_eval")

ROOT = Path(__file__).resolve().parent
_stop = threading.Event()
_thread: threading.Thread | None = None


def enabled() -> bool:
    return os.environ.get("LIMA_PERIODIC_CODING_EVAL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def interval_seconds() -> int:
    hours = float(os.environ.get("LIMA_CODING_EVAL_INTERVAL_HOURS", "168"))
    return max(3600, int(hours * 3600))


def run_eval_slice(*, quick: bool = True) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "run_radar_eval_slice.py"), "--preflight"]
    if quick:
        cmd.append("--quick")
    backends = ",".join(quick_backend_list())
    if backends:
        cmd.extend(["--backends", backends])
    logger.info("periodic coding eval: %s", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def start() -> None:
    global _thread
    if not enabled():
        logger.debug("periodic coding eval disabled (LIMA_PERIODIC_CODING_EVAL=0)")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="periodic-coding-eval", daemon=True)
    _thread.start()
    logger.info(
        "Periodic coding eval started (interval=%sh, quick backends=%s)",
        os.environ.get("LIMA_CODING_EVAL_INTERVAL_HOURS", "168"),
        ",".join(quick_backend_list()),
    )


def stop() -> None:
    _stop.set()


def _loop() -> None:
    # Stagger first run so server boot is not blocked by eval traffic.
    _stop.wait(timeout=120)
    while not _stop.is_set():
        ok, detail = check_eval_health()
        if ok:
            try:
                code = run_eval_slice(quick=True)
                logger.info("periodic coding eval finished exit=%s (%s)", code, detail)
            except Exception:
                logger.exception("periodic coding eval subprocess failed")
        else:
            logger.warning("periodic coding eval skipped: %s", detail)
        _stop.wait(timeout=interval_seconds())
