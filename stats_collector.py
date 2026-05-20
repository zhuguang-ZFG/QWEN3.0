"""stats_collector.py — 请求统计收集 + 日志 + System Prompt 去重记录
从 server.py 提取。
"""
import os
import json
import time
import hashlib
import functools
import threading

# ── 统计 ─────────────────────────────────────────────────────────────────────

_stats_lock = threading.Lock()
_stats = {
    "total_requests": 0,
    "backend_calls": {},
    "intent_distribution": {},
    "recent_logs": [],
    "start_time": time.time(),
}


def record_request(query: str, backend: str, intent: str, duration_ms: int,
                   success: bool = True, client_ip: str = "",
                   ide_source: str = "", sys_prompt_preview: str = ""):
    """记录一次请求到统计数据。"""
    with _stats_lock:
        _stats["total_requests"] += 1
        if backend not in _stats["backend_calls"]:
            _stats["backend_calls"][backend] = {"count": 0, "success": 0, "total_ms": 0}
        _stats["backend_calls"][backend]["count"] += 1
        if success:
            _stats["backend_calls"][backend]["success"] += 1
        _stats["backend_calls"][backend]["total_ms"] += duration_ms
        _stats["intent_distribution"][intent] = _stats["intent_distribution"].get(intent, 0) + 1
        _stats["recent_logs"].append({
            "time": time.strftime("%H:%M:%S"), "query": query[:80],
            "backend": backend, "intent": intent, "ms": duration_ms,
            "success": success, "ip": client_ip,
            "country": _get_ip_location(client_ip) if client_ip else "",
            "ide": ide_source,
            "sys_prompt": sys_prompt_preview[:100] if sys_prompt_preview else "",
        })
        if len(_stats["recent_logs"]) > 100:
            _stats["recent_logs"] = _stats["recent_logs"][-100:]


def get_stats() -> dict:
    with _stats_lock:
        return {
            "total_requests": _stats["total_requests"],
            "uptime_seconds": int(time.time() - _stats["start_time"]),
            "backend_calls": dict(_stats["backend_calls"]),
            "intent_distribution": dict(_stats["intent_distribution"]),
            "recent_logs": list(_stats["recent_logs"]),
        }


@functools.lru_cache(maxsize=256)
def _get_ip_location(ip: str) -> str:
    if ip in ("127.0.0.1", "localhost", "::1", ""):
        return "本地"
    try:
        import urllib.request
        resp = urllib.request.urlopen(
            f"http://ip-api.com/json/{ip}?fields=country,city&lang=zh-CN", timeout=0.5
        )
        data = json.loads(resp.read().decode())
        return f"{data.get('country', '')} {data.get('city', '')}"
    except Exception:
        return "未知"

import functools

# ── IDE 检测 ─────────────────────────────────────────────────────────────────

def detect_ide(messages: list) -> str:
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            if "Claude Code" in content or "claude-code" in content:
                return "Claude Code"
            if "Cursor" in content or "You are Cursor" in content:
                return "Cursor"
            if "GitHub Copilot" in content:
                return "GitHub Copilot"
            if "Codex" in content:
                return "Codex"
            if "Continue" in content:
                return "Continue"
            if "Cline" in content:
                return "Cline"
    return "未知"


# ── System Prompt 去重记录 ───────────────────────────────────────────────────

def extract_system_prompt(messages: list) -> str | None:
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system" and msg.get("content"):
            return msg["content"]
    return None


def log_sys_prompt(sys_prompt: str, distill_queue_dir: str = "D:/GIT/data/pending"):
    import datetime
    os.makedirs(distill_queue_dir.replace("pending", "sys_prompts"), exist_ok=True)
    phash = hashlib.sha256(sys_prompt.encode()).hexdigest()[:16]
    sys_prompt_dir = os.path.join(os.path.dirname(distill_queue_dir), "sys_prompts")
    existing = os.listdir(sys_prompt_dir) if os.path.exists(sys_prompt_dir) else []
    if any(phash in f for f in existing):
        return
    ide_source = "unknown"
    ide_markers = {"Claude Code": "claude_code", "Cursor": "cursor",
                   "Codex": "codex", "GitHub Copilot": "copilot"}
    for marker, source in ide_markers.items():
        if marker in sys_prompt:
            ide_source = source
            break
    entry = {
        "ide_source": ide_source, "prompt_hash": phash,
        "prompt_preview": sys_prompt[:500], "prompt_length": len(sys_prompt),
        "logged_at": datetime.datetime.now().isoformat(),
    }
    os.makedirs(sys_prompt_dir, exist_ok=True)
    fname = os.path.join(sys_prompt_dir, f"{ide_source}_{phash}.json")
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)


# ── Fallback 日志 ────────────────────────────────────────────────────────────

FALLBACK_LOG = "D:/GIT/data/fallback_log.jsonl"

def record_fallback(query: str, original_backend: str, fallback_backend: str,
                    intent: str, ide: str):
    try:
        os.makedirs(os.path.dirname(FALLBACK_LOG), exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query[:300], "original_backend": original_backend,
            "fallback_backend": fallback_backend, "intent": intent, "ide": ide,
        }
        with open(FALLBACK_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass
