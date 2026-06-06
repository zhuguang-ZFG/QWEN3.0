#!/usr/bin/env python3
"""Echo server to capture what one-api actually sends to upstream"""
import http.server
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        print("=== REQUEST ===", flush=True)
        print("PATH: " + self.path, flush=True)
        print("HEADERS:", flush=True)
        for k, v in self.headers.items():
            print("  " + k + ": " + v[:60], flush=True)
        print("BODY: " + body[:300], flush=True)
        print("===============", flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = json.dumps({
            "id": "echo-1",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "echo-ok"}, "finish_reason": "stop"}],
            "model": "echo",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        })
        self.wfile.write(resp.encode())

    def log_message(self, format, *args):
        pass

print("Echo server on :9999", flush=True)
http.server.HTTPServer(("0.0.0.0", 9999), Handler).serve_forever()
