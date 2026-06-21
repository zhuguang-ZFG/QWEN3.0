#!/usr/bin/env python3
"""Lightweight path-rewrite proxy for one-api
Listens on :8901-8908 (zhipu/github/aliyun/chinamobile/google/baidu/volcengine/longcat)
Rewrites /v1/chat/completions to the correct upstream path"""

import http.server, urllib.error, urllib.request, ssl, json, sys, threading
from typing import cast

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROUTES = {
    8901: ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "open.bigmodel.cn"),
    8902: ("https://models.inference.ai.azure.com/chat/completions", "models.inference.ai.azure.com"),
    8903: ("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "dashscope.aliyuncs.com"),
    8904: ("https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions", "maas.gd.chinamobile.com"),
    8905: (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "generativelanguage.googleapis.com",
    ),
    8906: ("https://qianfan.baidubce.com/v2/chat/completions", "qianfan.baidubce.com"),
    8907: ("https://ark.cn-beijing.volces.com/api/v3/chat/completions", "ark.cn-beijing.volces.com"),
    8908: ("https://api.longcat.chat/openai/v1/chat/completions", "api.longcat.chat"),
}

REWRITE_RESPONSE_PORTS = {8904}
PROXY_PORTS = {8905}
PROXY_URL = "http://127.0.0.1:7897"

ctx = ssl.create_default_context()


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _read_request_body(self) -> bytes:
        """Read the request body respecting Content-Length or chunked encoding."""
        length = int(self.headers.get("Content-Length", 0))
        te = self.headers.get("Transfer-Encoding", "")
        if length > 0:
            if length > 10 * 1024 * 1024:
                self.send_error(413)
                return b""
            return self.rfile.read(length)
        if "chunked" in te.lower():
            return self._read_chunked()
        return b""

    def _maybe_disable_thinking(self, body: bytes) -> bytes:
        """DashScope-specific: disable thinking mode in the request body."""
        try:
            obj = json.loads(body)
            obj["enable_thinking"] = False
            return json.dumps(obj).encode()
        except (json.JSONDecodeError, ValueError):
            return body

    def _maybe_convert_longcat_omni(self, body: bytes, upstream_url: str) -> tuple[bytes, dict, str]:
        """LongCat-Omni: convert OpenAI format to Anthropic format when needed."""
        headers = {"Content-Type": "application/json"}
        try:
            obj = json.loads(body)
            if "Omni" in obj.get("model", ""):
                upstream_url = "https://api.longcat.chat/anthropic/v1/messages"
                msgs = [m for m in obj.get("messages", []) if m.get("role") != "system"]
                anth_msgs = [
                    {
                        "role": m["role"],
                        "content": [
                            {
                                "type": "text",
                                "text": m["content"] if isinstance(m["content"], str) else str(m["content"]),
                            }
                        ],
                    }
                    for m in msgs
                ]
                body = json.dumps(
                    {"model": obj["model"], "messages": anth_msgs, "max_tokens": obj.get("max_tokens", 1024)}
                ).encode()
                headers["anthropic-version"] = "2023-06-01"
                self._omni_convert = True
            else:
                self._omni_convert = False
        except (json.JSONDecodeError, ValueError):
            self._omni_convert = False
        return body, headers, upstream_url

    def _forward_request(self, req: urllib.request.Request, port: int):
        """Send the upstream request and return the response object."""
        if port in PROXY_PORTS:
            proxy_handler = urllib.request.ProxyHandler({"https": PROXY_URL, "http": PROXY_URL})
            opener = urllib.request.build_opener(proxy_handler)
            return opener.open(req, timeout=30)
        return urllib.request.urlopen(req, timeout=30, context=ctx)

    def _transform_response(self, resp_body: bytes, port: int) -> bytes:
        """Apply response rewrites for specific ports and Omni conversion."""
        if port in REWRITE_RESPONSE_PORTS:
            resp_body = self._rewrite_reasoning(resp_body)
        if getattr(self, "_omni_convert", False):
            resp_body = self._anthropic_to_openai(resp_body)
        return resp_body

    def _send_json_response(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        server_address = cast(tuple[str, int], self.server.server_address)
        port = server_address[1]
        upstream_url, host = ROUTES.get(port, (None, None))
        if not upstream_url:
            self.send_error(404)
            return

        body = self._read_request_body()
        if not body and int(self.headers.get("Content-Length", 0)) > 10 * 1024 * 1024:
            return

        if port == 8903 and body:
            body = self._maybe_disable_thinking(body)

        auth = self.headers.get("Authorization", "")
        headers = {"Content-Type": "application/json", "Authorization": auth}
        if port == 8908 and body:
            body, extra_headers, upstream_url = self._maybe_convert_longcat_omni(body, upstream_url)
            headers.update(extra_headers)
        else:
            self._omni_convert = False

        req = urllib.request.Request(upstream_url, data=body, headers=headers)
        try:
            resp = self._forward_request(req, port)
            resp_body = self._transform_response(resp.read(), port)
            self._send_json_response(resp.status, resp_body)
        except urllib.error.HTTPError as e:
            self._send_json_response(e.code, e.read())
        except Exception as e:
            self._send_json_response(502, json.dumps({"error": {"message": str(e)}}).encode())

    def _anthropic_to_openai(self, resp_body):
        try:
            obj = json.loads(resp_body)
            content = ""
            for block in obj.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            openai_resp = {
                "id": obj.get("id", ""),
                "object": "chat.completion",
                "model": obj.get("model", ""),
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": obj.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": obj.get("usage", {}).get("output_tokens", 0),
                    "total_tokens": obj.get("usage", {}).get("input_tokens", 0)
                    + obj.get("usage", {}).get("output_tokens", 0),
                },
            }
            return json.dumps(openai_resp).encode()
        except (json.JSONDecodeError, ValueError, KeyError):
            return resp_body

    def _read_chunked(self):
        data = b""
        max_size = 10 * 1024 * 1024
        for _ in range(10000):
            line = self.rfile.readline().strip()
            if not line:
                break
            try:
                chunk_size = int(line, 16)
            except ValueError:
                break
            if chunk_size == 0:
                self.rfile.readline()
                break
            if len(data) + chunk_size > max_size:
                break
            data += self.rfile.read(chunk_size)
            self.rfile.readline()
        return data

    def _rewrite_reasoning(self, resp_body):
        try:
            obj = json.loads(resp_body)
            for choice in obj.get("choices", []):
                msg = choice.get("message", {})
                if msg.get("content") is None:
                    reasoning = msg.get("reasoning", "") or msg.get("reasoning_content", "")
                    if reasoning:
                        msg["content"] = reasoning
            return json.dumps(obj).encode()
        except (json.JSONDecodeError, ValueError):
            return resp_body

    def do_GET(self):
        body = b"path-proxy ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_server(port):
    srv = http.server.HTTPServer(("0.0.0.0", port), ProxyHandler)
    srv.serve_forever()


print("Starting path-rewrite proxy...")
for port in ROUTES:
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    print("  :" + str(port) + " -> " + ROUTES[port][0][:50])

print("Proxy ready.")
import time

while True:
    time.sleep(3600)
