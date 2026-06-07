"""Admin backend metadata and probe helpers (CQ-014 slice 11)."""

from __future__ import annotations

import json
import time
import urllib.request

import backends


def describe_backend(name: str, cfg: dict, *, enabled: bool, status_info: dict) -> dict:
    url = cfg.get("url", "")
    fmt = cfg.get("fmt", "openai")
    auth = cfg.get("auth", "x-api-key" if fmt == "anthropic" else "bearer")

    vendor = "未知"
    if "longcat" in url:
        vendor = "LongCat"
    elif "nvidia" in url:
        vendor = "英伟达 NVIDIA"
    elif "openrouter" in url:
        vendor = "OpenRouter"
    elif "deepseek" in url:
        vendor = "DeepSeek"
    elif "chinamobile" in url:
        vendor = "中国移动"
    elif "right.codes" in url:
        vendor = "Claude"
    elif "localhost" in url or "127.0.0.1" in url:
        vendor = "本地模型"

    tier = cfg.get("tier", "")
    if not tier:
        if "localhost" in url or "127.0.0.1" in url:
            tier = "L0 本地"
        elif "longcat" in url or "chinamobile" in url:
            tier = "L1 免费无限"
        elif "nvidia" in url:
            tier = "L2 免费额度"
        elif "openrouter" in url:
            tier = "L3 免费限量"
        else:
            tier = "L4 付费"

    caps = list(cfg.get("caps", []))
    if not caps:
        if name in ("claude", "or_deepseek_r1", "or_qwen3_coder", "deepseek_pro", "deepseek_flash"):
            caps.append("工具调用")
        if name in ("claude", "longcat_omni"):
            caps.append("视觉")
        if "thinking" in name or "r1" in name:
            caps.append("深度推理")
        if not caps:
            caps.append("纯文本")

    return {
        "name": name,
        "vendor": vendor,
        "tier": tier,
        "protocol": "Anthropic" if fmt == "anthropic" else "OpenAI",
        "capabilities": caps,
        "url": url,
        "model": cfg.get("model", ""),
        "auth": auth,
        "enabled": enabled,
        "state": status_info.get("state", "closed"),
        "total_calls": status_info.get("total_calls", 0),
        "error_rate": status_info.get("error_rate", "0.0%"),
    }


def test_backend_sync(name: str) -> dict:
    if name not in backends.BACKENDS:
        return {"ok": False, "error": f"backend '{name}' not found"}
    cfg = backends.BACKENDS[name]
    url = cfg.get("url", "")
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
        request = urllib.request.Request(
            url, data=payload, headers=headers, method="POST"
        )
        # Admin-authenticated backend probe; URL comes from configured backend.
        resp = urllib.request.urlopen(request, timeout=15)  # nosec B310
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
