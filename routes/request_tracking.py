"""routes/request_tracking.py — 请求追踪与可观测性函数。

从 server.py 提取。通过 inject_state() 注入共享状态。
"""
import asyncio
import functools
import json
import logging
import os
import threading
import time

from fastapi import Request

_log = logging.getLogger(__name__)
log = logging.getLogger(__name__)

# ── Shared state (injected from server.py) ────────────────────────────────────
_stats: dict = {}
_stats_lock: threading.Lock = threading.Lock()

_DATA_DIR = os.environ.get("LIMA_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
FALLBACK_LOG = os.path.join(_DATA_DIR, "fallback_log.jsonl")
TRUSTED_PROXIES = {"127.0.0.1", "::1", "10.0.0.1"}


def inject_state(stats: dict, stats_lock: threading.Lock) -> None:
    """Called once from server.py to wire in shared mutable state."""
    global _stats, _stats_lock
    _stats = stats
    _stats_lock = stats_lock


def record_fallback(query, original_backend, fallback_backend, intent, ide):
    """记录 fallback 事件到日志文件，供 auto_retrain 自动训练使用。"""
    try:
        os.makedirs(os.path.dirname(FALLBACK_LOG), exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query[:300],
            "original_backend": original_backend,
            "fallback_backend": fallback_backend,
            "intent": intent,
            "ide": ide,
        }
        with open(FALLBACK_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:
        log.warning(f"[FALLBACK_LOG] write failed: {e}")


@functools.lru_cache(maxsize=256)
def get_ip_location(ip: str) -> str:
    """查询 IP 地理位置（缓存结果）。"""
    if ip in ("127.0.0.1", "localhost", "::1", ""):
        return "本地"
    import re
    if not re.match(r'^[\d.:a-fA-F]+$', ip):
        return "未知"
    try:
        import urllib.request
        # Fixed ip-api URL after IP literal validation.
        resp = urllib.request.urlopen(  # nosec B310
            f"http://ip-api.com/json/{ip}?fields=country,city&lang=zh-CN",
            timeout=0.5,
        )
        data = json.loads(resp.read().decode())
        return f"{data.get('country', '')} {data.get('city', '')}"
    except Exception as exc:
        log.debug("ip location lookup failed ip=%s: %s", ip, type(exc).__name__)
        return "未知"


def client_ip(request: Request) -> str:
    """统一 IP 提取：可信代理后用 XFF，否则用 direct IP。"""
    direct = request.client.host if request.client else ""
    if direct in TRUSTED_PROXIES:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return direct


def detect_ide(messages: list) -> str:
    """从消息中检测 IDE 来源。使用 router_v3 的指纹匹配作为单一来源。"""
    from router_v3 import detect_ide_by_fingerprints
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            ide = detect_ide_by_fingerprints(content)
            if ide:
                return ide
    return ""


def elapsed_ms(started_at: float) -> int:
    return max(0, int((time.time() - started_at) * 1000))


def record_request(query: str, backend: str, intent: str, duration_ms: int,
                   success: bool = True, client_ip: str = "",
                   ide_source: str = "", sys_prompt_preview: str = ""):
    """记录一次请求到统计数据。"""
    country = get_ip_location(client_ip) if client_ip else ""

    with _stats_lock:
        _stats["total_requests"] += 1
        if backend not in _stats["backend_calls"]:
            _stats["backend_calls"][backend] = {"count": 0, "success": 0, "total_ms": 0}
        _stats["backend_calls"][backend]["count"] += 1
        if success:
            _stats["backend_calls"][backend]["success"] += 1
        _stats["backend_calls"][backend]["total_ms"] += duration_ms
        _stats["intent_distribution"][intent] = _stats["intent_distribution"].get(intent, 0) + 1
        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "query": query[:80],
            "backend": backend,
            "intent": intent,
            "ms": duration_ms,
            "success": success,
            "ip": client_ip,
            "country": country,
            "ide": ide_source,
            "sys_prompt": sys_prompt_preview[:100] if sys_prompt_preview else "",
        }
        _stats["recent_logs"].append(log_entry)
        if len(_stats["recent_logs"]) > 100:
            _stats["recent_logs"] = _stats["recent_logs"][-100:]

    # Fan-out to SSE log stream subscribers (best-effort, non-blocking).
    try:
        from routes.admin_sse import _main_sse_loop, publish_log_event
        loop = _main_sse_loop
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return
        if loop and loop.is_running():
            loop.create_task(publish_log_event(log_entry))
    except ImportError as exc:
        log.debug("SSE log fan-out unavailable: %s", exc)
    except Exception as exc:
        log.warning("Failed to fan-out SSE log event", exc_info=True)
