#!/usr/bin/env python3
"""Lightweight path-rewrite proxy for one-api
Listens on :8901 (zhipu) and :8902 (github)
Rewrites /v1/chat/completions to the correct upstream path"""
import http.server, urllib.request, ssl, json, sys, threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROUTES = {
    8901: ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "open.bigmodel.cn"),
    8902: ("https://models.inference.ai.azure.com/chat/completions", "models.inference.ai.azure.com"),
    8903: ("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "dashscope.aliyuncs.com"),
}

ctx = ssl.create_default_context()

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        port = self.server.server_address[1]
        upstream_url, host = ROUTES.get(port, (None, None))
        if not upstream_url:
            self.send_error(404)
            return
        # Handle both Content-Length and chunked transfer
        length = int(self.headers.get("Content-Length", 0))
        te = self.headers.get("Transfer-Encoding", "")
        if length > 0:
            body = self.rfile.read(length)
        elif "chunked" in te.lower():
            body = self._read_chunked()
        else:
            body = self.rfile.read()
        # Inject enable_thinking=false for aliyun (port 8903)
        if port == 8903 and body:
            try:
                obj = json.loads(body)
                obj["enable_thinking"] = False
                body = json.dumps(obj).encode()
            except (json.JSONDecodeError, ValueError):
                pass
        auth = self.headers.get("Authorization", "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth,
        }
        req = urllib.request.Request(upstream_url, data=body, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            resp_body = resp.read()
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

    def _read_chunked(self):
        data = b""
        while True:
            line = self.rfile.readline().strip()
            if not line:
                break
            chunk_size = int(line, 16)
            if chunk_size == 0:
                self.rfile.readline()
                break
            data += self.rfile.read(chunk_size)
            self.rfile.readline()
        return data

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
