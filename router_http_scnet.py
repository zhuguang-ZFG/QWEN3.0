"""SCNet chunked HTTP calls for legacy router_http (CQ-096)."""

from __future__ import annotations

import json
import logging
import time
import urllib.request

from backends import BACKENDS
from response_cleaner import clean_response
from router_circuit_breaker import cb_record
from router_http_body import UNAVAILABLE_USER_MESSAGE

_log = logging.getLogger(__name__)

SCNET_API = "https://www.scnet.cn/acx/chatbot/v1/chat/completion"
SCNET_MODELS = {
    "qwen3-30b": 17,
    "minimax-m2.5": 410,
    "qwen3-235b": 120,
    "deepseek-v4-flash": 520,
    "deepseek-v4-pro": 510,
}
SCNET_CHUNK = 38000


def scnet_send_message(content: str, conv_id: str, model_id: int) -> tuple[str, str]:
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


def call_scnet_chunked(name: str, msgs, mt, started: float):
    backend = BACKENDS.get(name)
    model_name = backend["model"] if backend else "qwen3-30b"
    model_id = SCNET_MODELS.get(model_name, 17)
    full_text = "\n".join(f"[{m['role']}]: {m['content']}" for m in msgs)

    try:
        if len(full_text) <= SCNET_CHUNK:
            answer, _ = scnet_send_message(full_text, "", model_id)
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
                answer, conv_id = scnet_send_message(message, conv_id, model_id)
        cb_record(name, True, int((time.time() - started) * 1000))
        return clean_response(answer, name)
    except Exception as exc:
        _log.warning("%s scnet call failed: %s", name, type(exc).__name__)
        cb_record(name, False)
        return UNAVAILABLE_USER_MESSAGE
