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

_log = logging.getLogger(__name__)
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


def scores_max_age_seconds() -> int:
    days = float(os.environ.get("LIMA_CODING_EVAL_MAX_AGE_DAYS", "7"))
    return max(86400, int(days * 86400))


def scores_are_stale() -> tuple[bool, str]:
    """Return (stale, detail) when newest eval scores file is missing or too old."""
    from eval_slice_summary import latest_scores_path

    base = ROOT / "data"
    path = latest_scores_path(base, full=True) or latest_scores_path(base, full=False)
    if not path or not path.is_file():
        return True, "no scores file"
    age = time.time() - path.stat().st_mtime
    limit = scores_max_age_seconds()
    if age > limit:
        return True, f"scores age {int(age // 86400)}d > {int(limit // 86400)}d"
    return False, f"scores fresh ({path.name})"


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


def _wait_server_ready(max_seconds: int = 180) -> tuple[bool, str]:
    """Block until /health responds or timeout (eval must run after uvicorn binds)."""
    deadline = time.monotonic() + max_seconds
    last_detail = "timeout"
    while time.monotonic() < deadline and not _stop.is_set():
        ok, detail = check_eval_health()
        if ok:
            return True, detail
        last_detail = detail
        _stop.wait(timeout=5)
    return False, last_detail


def _loop() -> None:
    # Stagger first run unless eval evidence is stale (operator-visible quality gap).
    stale, stale_detail = scores_are_stale()
    if stale:
        _log_info("periodic coding eval: stale scores (%s), waiting for server", stale_detail)
        _stop.wait(timeout=10)
    else:
        _stop.wait(timeout=120)
    while not _stop.is_set():
        ready, detail = _wait_server_ready()
        if ready:
            try:
                from eval_notify import notify_eval_finished, periodic_full_eval

                quick = not periodic_full_eval()
                code = run_eval_slice(quick=quick)
                _log_info("periodic coding eval finished exit=%s (%s)", code, detail)
                notify_eval_finished(code=code, quick=quick, source="periodic")
            except Exception as exc:
                logger.exception("periodic coding eval subprocess failed")
        else:
            _log_info("periodic coding eval skipped: server not ready (%s)", detail)
        _stop.wait(timeout=interval_seconds())
