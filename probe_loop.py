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

        # Token health check every 30 minutes (reduce frequency)
        try:
            import token_health
            results = token_health.check_all_tokens()
            expired = [r for r in results if r.get("status") == "expired"]
            if expired:
                names = [r["backend"] for r in expired]
                # Only alert once per hour per backend
                import time as _time
                now = _time.time()
                for r in expired:
                    key = f"alert_{r['backend']}"
                    last_alert = getattr(_loop, '_last_alerts', {}).get(key, 0)
                    if now - last_alert > 3600:  # 1 hour cooldown
                        logger.warning("TOKEN EXPIRED: %s", r["backend"])
                        try:
                            from telegram_notify import notify_health_change
                            notify_health_change(r["backend"], "healthy", "auth_expired")
                        except (ImportError, Exception):
                            pass
                        if not hasattr(_loop, '_last_alerts'):
                            _loop._last_alerts = {}
                        _loop._last_alerts[key] = now
            token_health.save_token_status(results)
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Token health check error: %s", e)

        _stop_event.wait(timeout=LOOP_SLEEP)


def _probe_cycle(probe_fn: Callable[[str], bool]):
    now = time.monotonic()
    hmap = health_tracker.get_health_map()

    for backend, state in hmap.items():
        if state in ("healthy", "degraded"):
            continue

        interval = PROBE_INTERVAL_SUSPICIOUS if state == "suspicious" else PROBE_INTERVAL_DEAD
        with _probe_lock:
            last = _last_probe.get(backend, 0)
            if now - last < interval:
                continue
            _last_probe[backend] = now

        success = False
        try:
            success = probe_fn(backend)
        except Exception as e:
            logger.warning(f"[PROBE] {backend} probe_fn raised: {type(e).__name__}: {e}")

        if success:
            health_tracker.record_success(backend, 0)
            logger.info(f"[PROBE] {backend} recovered!")
            # Update backend profile
            try:
                import backend_profile
                backend_profile.record_request(backend, 0.0, success=True, scenario="probe")
            except ImportError:
                pass
        else:
            logger.debug(f"[PROBE] {backend} still down")
            # Update backend profile
            try:
                import backend_profile
                backend_profile.record_request(backend, 0.0, success=False, scenario="probe")
            except ImportError:
                pass
