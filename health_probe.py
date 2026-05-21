"""
LiMa Health Probe — 主动探针，定时 ping 不稳定后端，提前标记故障。

目标后端: g4f (PollinationsAI) 等免费/不稳定源
机制: 每 PROBE_INTERVAL 秒发 max_tokens=1 探活请求
  - 成功 → record_success (恢复可用)
  - 失败 → record_failure (进入 cooldown，路由自动跳过)
"""

import threading
import time
import logging

from http_caller import probe
from health_tracker import record_failure, record_success, is_cooled_down

logger = logging.getLogger("health_probe")

PROBE_INTERVAL = 300  # 5 分钟
PROBE_TARGETS = [
    'g4f_openai', 'g4f_deepseek', 'g4f_qwen_coder', 'g4f_llama',
]

_running = False
_thread = None


def _probe_loop():
    global _running
    while _running:
        for backend in PROBE_TARGETS:
            try:
                ok = probe(backend)
                if ok:
                    record_success(backend, latency_ms=500.0)
                    logger.debug(f"[probe] {backend} ✓")
                else:
                    record_failure(backend, error_code=503)
                    logger.warning(f"[probe] {backend} ✗ → cooldown")
            except Exception as e:
                record_failure(backend, error_code=500)
                logger.warning(f"[probe] {backend} exception: {e}")
            time.sleep(2)
        time.sleep(PROBE_INTERVAL)


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_probe_loop, daemon=True, name="health-probe")
    _thread.start()
    logger.info(f"Health probe started: {len(PROBE_TARGETS)} targets, interval={PROBE_INTERVAL}s")


def stop():
    global _running
    _running = False
