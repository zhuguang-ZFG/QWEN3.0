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
LOOP_SLEEP = 60                   # 主循环每分钟跑一次

_last_probe: dict[str, float] = {}
_running = False
_thread: Optional[threading.Thread] = None


def start(probe_fn: Callable[[str], bool]):
    """启动探活线程。probe_fn(backend) -> True=成功, False=失败"""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, args=(probe_fn,), daemon=True)
    _thread.start()
    logger.info("Probe loop started")


def stop():
    global _running
    _running = False


def _loop(probe_fn: Callable[[str], bool]):
    global _running
    while _running:
        try:
            _probe_cycle(probe_fn)
        except Exception as e:
            logger.error(f"Probe cycle error: {e}")
        time.sleep(LOOP_SLEEP)


def _probe_cycle(probe_fn: Callable[[str], bool]):
    now = time.monotonic()
    hmap = health_tracker.get_health_map()

    for backend, state in hmap.items():
        if state in ("healthy", "degraded"):
            continue

        interval = PROBE_INTERVAL_SUSPICIOUS if state == "suspicious" else PROBE_INTERVAL_DEAD
        last = _last_probe.get(backend, 0)
        if now - last < interval:
            continue

        _last_probe[backend] = now
        success = False
        try:
            success = probe_fn(backend)
        except Exception:
            pass

        if success:
            health_tracker.record_success(backend, 0)
            logger.info(f"[PROBE] {backend} recovered!")
        else:
            logger.debug(f"[PROBE] {backend} still down")
