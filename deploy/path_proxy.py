#!/usr/bin/env python3
"""Lightweight path-rewrite proxy for one-api
Listens on :8901-8908 (zhipu/github/aliyun/chinamobile/google/baidu/volcengine/longcat)
Rewrites /v1/chat/completions to the correct upstream path"""

import http.server, urllib.request, ssl, json, sys, threading

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

    def do_POST(self):
        port = self.server.server_address[1]
        upstream_url, host = ROUTES.get(port, (None, None))
        if not upstream_url:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        te = self.headers.get("Transfer-Encoding", "")
        if length > 0:
            if length > 10 * 1024 * 1024:
                self.send_error(413)
                return
            body = self.rfile.read(length)
        elif "chunked" in te.lower():
            body = self._read_chunked()
        else:
            body = b""
        if port == 8903 and body:
            try:
                obj = json.loads(body)
                obj["enable_thinking"] = False
                body = json.dumps(obj).encode()
            except (json.JSONDecodeError, ValueError):
                pass
        auth = self.headers.get("Authorization", "")
        headers = {"Content-Type": "application/json", "Authorization": auth}
        # LongCat-Omni: convert OpenAI→Anthropic format
        if port == 8908 and body:
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
        else:
            self._omni_convert = False
        req = urllib.request.Request(upstream_url, data=body, headers=headers)
        try:
            if port in PROXY_PORTS:
                proxy_handler = urllib.request.ProxyHandler({"https": PROXY_URL, "http": PROXY_URL})
                opener = urllib.request.build_opener(proxy_handler)
                resp = opener.open(req, timeout=30)
            else:
                resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            resp_body = resp.read()
            if port in REWRITE_RESPONSE_PORTS:
                resp_body = self._rewrite_reasoning(resp_body)
            if getattr(self, "_omni_convert", False):
                resp_body = self._anthropic_to_openai(resp_body)
            self.send_response(resp.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as e:
            err = json.dumps({"error": {"message": str(e)}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

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
