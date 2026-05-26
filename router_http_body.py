"""Request body builders for legacy router_http (CQ-096)."""

from __future__ import annotations

import json

from backends import BACKENDS
from router_prompt import SYS


def _ide_system_prompt(ide: str) -> str:
    sys_prompt = SYS
    if ide and ide not in ("unknown", "未知"):
        sys_prompt += (
            f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、"
            "代码搜索等工具能力。请正常回应用户的文件操作请求，"
            "不要说'无法访问本地文件'。"
        )
    return sys_prompt


def build_request_body(name, msgs, mt=1024, ide="unknown", stream=False):
    backend = BACKENDS.get(name)
    if not backend:
        return None, None, None, 60
    auth_style = backend.get("auth", "x-api-key")

    if backend["fmt"] == "anthropic":
        if backend.get("no_system"):
            omni_msgs = [
                {
                    "role": m["role"],
                    "content": [{"type": "text", "text": m["content"]}]
                    if isinstance(m["content"], str)
                    else m["content"],
                }
                for m in msgs
            ]
            body = {"model": backend["model"], "max_tokens": mt, "messages": omni_msgs}
        else:
            body = {
                "model": backend["model"],
                "max_tokens": mt,
                "system": _ide_system_prompt(ide),
                "messages": msgs,
            }
        if stream:
            body["stream"] = True
        payload = json.dumps(body).encode()
        if auth_style == "bearer":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {backend['key']}",
                "anthropic-version": "2023-06-01",
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": backend["key"],
                "anthropic-version": "2023-06-01",
            }
    else:
        body = {
            "model": backend["model"],
            "max_tokens": mt,
            "messages": [{"role": "system", "content": _ide_system_prompt(ide)}] + msgs,
        }
        if stream:
            body["stream"] = True
        if name == "unclose_qwen":
            body["chat_template_kwargs"] = {"enable_thinking": False}
        payload = json.dumps(body).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {backend['key']}",
            "User-Agent": "LiMa/2.0",
        }

    return payload, headers, backend["fmt"], backend.get("timeout", 60)
