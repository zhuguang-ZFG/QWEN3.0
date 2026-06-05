"""
LiMa Probe Loop — 主动探活后台线程
只对 dead/suspicious 后端发探针，省配额。

设计:
- healthy/degraded: 不探活(有真实流量)
- suspicious: 每 5 分钟探一次
- dead: 每 15 分钟探一次
- 探针: max_tokens=1 的最小请求
"""

import time
import threading
import logging
from typing import Callable, Optional

import health_tracker

logger = logging.getLogger("probe_loop")

PROBE_INTERVAL_SUSPICIOUS = 300   # 5 min
PROBE_INTERVAL_DEAD = 900         # 15 min
PROBE_INTERVAL_UNKNOWN = 1800     # 30 min — unprobed backends
LOOP_SLEEP = 60                   # 主循环每分钟跑一次
PROBE_BATCH_UNKNOWN = 8           # cap probes per cycle to save quota

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_probe_lock = threading.Lock()
_last_probe: dict[str, float] = {}


def start(probe_fn: Callable[[str], bool]):
    """启动探活线程。probe_fn(backend) -> True=成功, False=失败"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, args=(probe_fn,), daemon=True)
    _thread.start()
    logger.info("Probe loop started")


def stop():
    _stop_event.set()


def _loop(probe_fn: Callable[[str], bool]):
    while not _stop_event.is_set():
        try:
            _probe_cycle(probe_fn)
        except Exception as e:
            logger.error(f"Probe cycle error: {e}")
        _stop_event.wait(timeout=LOOP_SLEEP)


def _backend_probe_eligible(name: str) -> bool:
    """Skip backends that cannot accept a minimal probe request."""
    try:
        from backends_registry import BACKENDS
        import http_request_builder as hrb
    except ImportError:
        return False
    cfg = BACKENDS.get(name, {})
    if not cfg:
        return False
    return hrb._has_key(name, cfg)


def _probe_one(probe_fn: Callable[[str], bool], backend: str, *, recovered: bool) -> None:
    success = False
    try:
        success = probe_fn(backend)
    except Exception as e:
        logger.warning(f"[PROBE] {backend} probe_fn raised: {type(e).__name__}: {e}")

    if success:
        health_tracker.record_success(backend, 0)
        if recovered:
            logger.info(f"[PROBE] {backend} recovered!")
        else:
            logger.info(f"[PROBE] {backend} probe ok (was unknown)")
    else:
        health_tracker.record_failure(backend, error_code=None, error_text="probe failed")
        logger.debug(f"[PROBE] {backend} probe failed")


def _probe_cycle(probe_fn: Callable[[str], bool]):
    now = time.monotonic()
    hmap = health_tracker.get_health_map()
    unknown_due: list[str] = []

    for backend, state in hmap.items():
        if state in ("healthy", "degraded"):
            continue
        if not _backend_probe_eligible(backend):
            continue

        if state == "unknown":
            with _probe_lock:
                last = _last_probe.get(backend, 0)
                if now - last >= PROBE_INTERVAL_UNKNOWN:
                    unknown_due.append(backend)
            continue

        interval = PROBE_INTERVAL_SUSPICIOUS if state == "suspicious" else PROBE_INTERVAL_DEAD
        with _probe_lock:
            last = _last_probe.get(backend, 0)
            if now - last < interval:
                continue
            _last_probe[backend] = now

        _probe_one(probe_fn, backend, recovered=True)

    if unknown_due:
        unknown_due.sort()
        for backend in unknown_due[:PROBE_BATCH_UNKNOWN]:
            with _probe_lock:
                _last_probe[backend] = now
            _probe_one(probe_fn, backend, recovered=False)
