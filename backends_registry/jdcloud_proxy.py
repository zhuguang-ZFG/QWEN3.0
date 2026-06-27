"""京东云 Worker 代理后端（Phase 2）.

主 VPS 通过 Tailscale 内网地址调用京东云 Worker 的 /proxy/{provider} 端点。
试点接入无 key 免费上游 Pollinations：Worker 持有零 key（Pollinations 免 key），
仅靠共享的 JDCLOUD_WORKER_TOKEN 鉴权。
"""

from __future__ import annotations

_JDCLOUD_WORKER_HOST = "http://100.85.114.65:8700"
_JDCLOUD_POLLINATIONS_URL = f"{_JDCLOUD_WORKER_HOST}/proxy/pollinations"
_JDCLOUD_WORKER_TOKEN_VAR = "JDCLOUD_WORKER_TOKEN"

BACKENDS: dict[str, dict] = {
    # ── Pollinations 无 key 免费 upstream（试点流量分担）──
    # 主 VPS → 京东云 Worker /proxy/pollinations → text.pollinations.ai。
    "jdcloud_pollinations_openai": {
        "url": _JDCLOUD_POLLINATIONS_URL,
        "key": "",
        "key_env_var": _JDCLOUD_WORKER_TOKEN_VAR,
        "model": "openai",
        "fmt": "openai",
        "timeout": 45,
        "headers": {"User-Agent": "LiMa-JDCloud-Proxy/1.0"},
    },
    "jdcloud_pollinations_deepseek": {
        "url": _JDCLOUD_POLLINATIONS_URL,
        "key": "",
        "key_env_var": _JDCLOUD_WORKER_TOKEN_VAR,
        "model": "deepseek",
        "fmt": "openai",
        "timeout": 45,
        "headers": {"User-Agent": "LiMa-JDCloud-Proxy/1.0"},
    },
}
