"""Legacy sync HTTP backend calls extracted from smart_router (CQ-014 slice 7)."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

_log = logging.getLogger(__name__)

from backends import BACKENDS, GFW_BACKENDS
from response_cleaner import clean_response
from router_circuit_breaker import cb_allow, cb_record
from router_prompt import SYS
from vision_handler import detect_vision_request

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"
GFW_PROXY_URL = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")

SCNET_API = "https://www.scnet.cn/acx/chatbot/v1/chat/completion"
SCNET_MODELS = {
    "qwen3-30b": 17,
    "minimax-m2.5": 410,
    "qwen3-235b": 120,
    "deepseek-v4-flash": 520,
    "deepseek-v4-pro": 510,
}
SCNET_CHUNK = 38000


def _get_opener(name: str):
    if name in GFW_BACKENDS:
        proxy = urllib.request.ProxyHandler(
            {"http": GFW_PROXY_URL, "https": GFW_PROXY_URL}
        )
        return urllib.request.build_opener(proxy)
    return None


def _has_vision_content(messages: list) -> bool:
    return detect_vision_request(messages)


def _call_cf_vision(msgs, mt, _t0):
    cf_token = os.environ.get("CLOUDFLARE_TOKEN", "")
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not cf_token or not cf_account:
        return None
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/run/"
        "@cf/meta/llama-3.2-11b-vision-instruct"
    )
    body = json.dumps({"messages": msgs, "max_tokens": mt}).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cf_token}",
        "User-Agent": "LiMa/2.0",
    }
    try:
        request = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        answer = payload.get("result", {}).get("response", "")
        if answer:
            cb_record("cf_vision", True, int((time.time() - _t0) * 1000))
            return clean_response(answer, "cf_vision")
        return None
    except Exception as exc:
        if DEBUG:
            print(f"[DEBUG] cf_vision error: {exc}", file=sys.stderr)
        cb_record("cf_vision", False)
        return None


def _call_scnet_chunked(name, msgs, mt, _t0):
    backend = BACKENDS.get(name)
    model_name = backend["model"] if backend else "qwen3-30b"
    model_id = SCNET_MODELS.get(model_name, 17)
    full_text = "\n".join(f"[{m['role']}]: {m['content']}" for m in msgs)

    def _send(content, conv_id):
        payload = json.dumps(
            {
                "conversationId": conv_id,
                "content": content,
                "thinkingEnable": False,
                "onlineEnable": False,
                "modelId": model_id,
                "textFile": [],
                "imageFile": [],
                "autoRun": 0,
                "clusterId": "",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            SCNET_API,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://www.scnet.cn",
                "Referer": "https://www.scnet.cn/ui/chatbot/",
            },
        )
        with urllib.request.urlopen(request, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
        reply, cid = "", conv_id
        for line in raw.split("\n"):
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:])
                    if data.get("conversationId"):
                        cid = data["conversationId"]
                    if data.get("content") and data["content"] != "[done]":
                        reply += data["content"]
                except Exception as exc:
                    _log.debug("scnet sse line parse skipped: %s", type(exc).__name__)
        return reply.replace("[done]", "").strip(), cid

    try:
        if len(full_text) <= SCNET_CHUNK:
            answer, _ = _send(full_text, "")
        else:
            chunks = [
                full_text[i : i + SCNET_CHUNK]
                for i in range(0, len(full_text), SCNET_CHUNK)
            ]
            conv_id = ""
            answer = ""
            for index, chunk in enumerate(chunks):
                is_last = index == len(chunks) - 1
                if not is_last:
                    message = (
                        f"[Part {index + 1}/{len(chunks)}]\n{chunk}\n\n"
                        "[Say OK and wait for next part]"
                    )
                else:
                    message = chunk + "\n\nNow answer based on ALL parts above."
                answer, conv_id = _send(message, conv_id)
        cb_record(name, True, int((time.time() - _t0) * 1000))
        return clean_response(answer, name)
    except Exception as exc:
        print(f"[DEBUG] {name} scnet error: {exc}", file=sys.stderr)
        cb_record(name, False)
        return "服务暂时不可用，请稍后重试"


def _build_request_body(name, msgs, mt=1024, ide="unknown", stream=False):
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
            sys_prompt = SYS
            if ide and ide not in ("unknown", "未知"):
                sys_prompt += (
                    f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、"
                    "代码搜索等工具能力。请正常回应用户的文件操作请求，"
                    "不要说'无法访问本地文件'。"
                )
            body = {
                "model": backend["model"],
                "max_tokens": mt,
                "system": sys_prompt,
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
        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += (
                f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、"
                "代码搜索等工具能力。请正常回应用户的文件操作请求，"
                "不要说'无法访问本地文件'。"
            )
        body = {
            "model": backend["model"],
            "max_tokens": mt,
            "messages": [{"role": "system", "content": sys_prompt}] + msgs,
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


def call_api(name, msgs, mt=1024, ide="unknown"):
    if not cb_allow(name):
        if DEBUG:
            print(f"[CB] {name}: blocked by circuit breaker", file=sys.stderr)
        return None
    started = time.time()
    backend = BACKENDS.get(name)
    if not backend or not backend["key"]:
        cb_record(name, False)
        return f"[ERR] Backend {name} unavailable (no key)"
    auth_style = backend.get("auth", "x-api-key")

    if name == "cf_vision" and _has_vision_content(msgs):
        return _call_cf_vision(msgs, mt, started)

    if name.startswith("scnet_"):
        return _call_scnet_chunked(name, msgs, mt, started)

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
            sys_prompt = SYS
            if ide and ide not in ("unknown", "未知"):
                sys_prompt += (
                    f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、"
                    "代码搜索等工具能力。请正常回应用户的文件操作请求，"
                    "不要说'无法访问本地文件'。"
                )
            body = {
                "model": backend["model"],
                "max_tokens": mt,
                "system": sys_prompt,
                "messages": msgs,
            }
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
        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += (
                f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、"
                "代码搜索等工具能力。请正常回应用户的文件操作请求，"
                "不要说'无法访问本地文件'。"
            )
        payload = json.dumps(
            {
                "model": backend["model"],
                "max_tokens": mt,
                "messages": [{"role": "system", "content": sys_prompt}] + msgs,
            }
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {backend['key']}",
            "User-Agent": "LiMa/2.0",
        }
    try:
        request = urllib.request.Request(backend["url"], data=payload, headers=headers)
        timeout = backend.get("timeout", 60)
        opener = _get_opener(name)
        if opener:
            with opener.open(request, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
        else:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
        if backend["fmt"] == "anthropic":
            answer = (
                payload["content"][0].get("text", "")
                or payload["content"][0].get("thinking", "")
                or json.dumps(payload, ensure_ascii=False)
            )
        else:
            message = payload["choices"][0]["message"]
            answer = (
                message.get("content")
                or message.get("reasoning_content")
                or message.get("reasoning")
                or json.dumps(payload, ensure_ascii=False)
            )
        cb_record(name, True, int((time.time() - started) * 1000))
        return clean_response(answer, name)
    except Exception as exc:
        print(f"[DEBUG] {name} error: {exc}", file=sys.stderr)
        cb_record(name, False)
        return "服务暂时不可用，请稍后重试"


def call_api_stream(name, msgs, mt=1024, ide="unknown"):
    if not cb_allow(name):
        if DEBUG:
            print(f"[CB] {name}: blocked by circuit breaker (stream)", file=sys.stderr)
        yield "服务暂时不可用，请稍后重试"
        return
    backend = BACKENDS.get(name)
    if not backend or not backend["key"]:
        yield f"[ERR] Backend {name} unavailable (no key)"
        return

    payload, headers, fmt, timeout = _build_request_body(name, msgs, mt, ide, stream=True)
    if payload is None:
        yield f"[ERR] Backend {name} not found"
        return

    started = time.time()
    buffer = b""
    try:
        request = urllib.request.Request(backend["url"], data=payload, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line_end = buffer.index(b"\n")
                    line = buffer[:line_end].decode("utf-8", errors="replace").strip()
                    buffer = buffer[line_end + 1 :]
                    if not line:
                        continue
                    if fmt == "openai":
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            pass
        cb_record(name, True, int((time.time() - started) * 1000))
    except Exception as exc:
        if DEBUG:
            print(f"[STREAM] {name} error: {exc}", file=sys.stderr)
        cb_record(name, False)
        yield "服务暂时不可用，请稍后重试"
