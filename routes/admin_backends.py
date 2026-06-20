"""Admin backend metadata and probe helpers (CQ-014 slice 11)."""

from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.request
from urllib.parse import urlparse

from backends_registry import BACKENDS


def _is_safe_backend_url(url: str) -> bool:
    """Reject non-HTTPS URLs, private IPs, loopback, and file:// schemes."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = parsed.hostname
    if not host:
        return False
    if host.lower() in ("localhost", "localhost."):
        return False
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
            return False
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                addr = ipaddress.ip_address(info[4][0])
                if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
                    return False
        except socket.gaierror:
            return False
    return True


def _resolve_vendor(url: str) -> str:
    if "longcat" in url:
        return "LongCat"
    if "nvidia" in url:
        return "英伟达 NVIDIA"
    if "openrouter" in url:
        return "OpenRouter"
    if "deepseek" in url:
        return "DeepSeek"
    if "chinamobile" in url:
        return "中国移动"
    if "right.codes" in url:
        return "Claude"
    if "localhost" in url or "127.0.0.1" in url:
        return "本地模型"
    return "未知"


def _resolve_tier(url: str, cfg_tier: str) -> str:
    if cfg_tier:
        return cfg_tier
    if "localhost" in url or "127.0.0.1" in url:
        return "L0 本地"
    if "longcat" in url or "chinamobile" in url:
        return "L1 免费无限"
    if "nvidia" in url:
        return "L2 免费额度"
    if "openrouter" in url:
        return "L3 免费限量"
    return "L4 付费"


def _resolve_capabilities(name: str, cfg_caps: list[str]) -> list[str]:
    caps = list(cfg_caps)
    if caps:
        return caps
    if name in ("claude", "or_deepseek_r1", "or_qwen3_coder", "deepseek_pro", "deepseek_flash"):
        caps.append("工具调用")
    if name in ("claude", "longcat_omni"):
        caps.append("视觉")
    if "thinking" in name or "r1" in name:
        caps.append("深度推理")
    if not caps:
        caps.append("纯文本")
    return caps


def describe_backend(name: str, cfg: dict, *, enabled: bool, status_info: dict) -> dict:
    url = cfg.get("url", "")
    fmt = cfg.get("fmt", "openai")
    auth = cfg.get("auth", "x-api-key" if fmt == "anthropic" else "bearer")
    caps = _resolve_capabilities(name, cfg.get("caps", []))
    return {
        "name": name,
        "vendor": _resolve_vendor(url),
        "tier": _resolve_tier(url, cfg.get("tier", "")),
        "protocol": "Anthropic" if fmt == "anthropic" else "OpenAI",
        "fmt": fmt,
        "capabilities": caps,
        "caps": caps,
        "url": url,
        "model": cfg.get("model", ""),
        "auth": auth,
        "enabled": enabled,
        "state": status_info.get("state", "closed"),
        "total_calls": status_info.get("total_calls", 0),
        "error_rate": status_info.get("error_rate", "0.0%"),
        "key_configured": bool(cfg.get("key", "")),
        "in_registry": True,
        "pools": cfg.get("pools", []),
        "admission": cfg.get("admission", ""),
    }


def test_backend_sync(name: str) -> dict:
    if name not in BACKENDS:
        return {"ok": False, "error": f"backend '{name}' not found"}
    cfg = BACKENDS[name]
    url = cfg.get("url", "")
    if not _is_safe_backend_url(url):
        return {"ok": False, "error": f"backend URL is not a public HTTPS endpoint: {url}"}
    key = cfg.get("key", "")
    fmt = cfg.get("fmt", "openai")
    model = cfg.get("model", "")
    started = time.time()
    try:
        if fmt == "anthropic":
            headers = {
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            if cfg.get("auth") == "bearer":
                headers["Authorization"] = f"Bearer {key}"
            else:
                headers["x-api-key"] = key
            payload = json.dumps(
                {
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                }
            ).encode()
        else:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }
            payload = json.dumps(
                {
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                }
            ).encode()
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        resp = urllib.request.urlopen(request, timeout=15)
        elapsed = int((time.time() - started) * 1000)
        data = json.loads(resp.read().decode())
        return {
            "ok": True,
            "latency_ms": elapsed,
            "status": resp.status,
            "capabilities_detected": ["纯文本"],
            "response_preview": str(data)[:200],
        }
    except Exception as exc:
        elapsed = int((time.time() - started) * 1000)
        return {"ok": False, "latency_ms": elapsed, "error": str(exc)[:200]}
