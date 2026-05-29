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


def _log_info(msg: str, *args: object) -> None:
    """Log to logger and stdout so systemd journal captures periodic eval."""
    text = msg % args if args else msg
    logger.info(text)
    print(f"[periodic-coding-eval] {text}", flush=True)
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
    from eval_quiet import set_eval_quiet

    cmd = [sys.executable, str(ROOT / "scripts" / "run_radar_eval_slice.py"), "--preflight"]
    if quick:
        cmd.append("--quick")
    else:
        cmd.append("--full")
    if quick:
        backends = ",".join(quick_backend_list())
        if backends:
            cmd.extend(["--backends", backends])
    _log_info("periodic coding eval: %s", " ".join(cmd))
    set_eval_quiet(True)
    try:
        return subprocess.call(cmd, cwd=ROOT)
    finally:
        set_eval_quiet(False)


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
    _log_info(
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
                from eval_notify import notify_eval_finished, periodic_full_eval

                quick = not periodic_full_eval()
                code = run_eval_slice(quick=quick)
                _log_info("periodic coding eval finished exit=%s (%s)", code, detail)
                notify_eval_finished(code=code, quick=quick, source="periodic")
            except Exception:
                logger.exception("periodic coding eval subprocess failed")
        else:
            _log_info("periodic coding eval skipped: %s", detail)
        _stop.wait(timeout=interval_seconds())
