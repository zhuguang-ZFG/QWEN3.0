#!/usr/bin/env python3
"""Strip accidental /v1 between /v4 and /chat/completions for Zhipu coding plan."""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.request

UPSTREAM = "https://open.bigmodel.cn"


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _fwd(self):
        path = self.path.replace("/v4/v1/", "/v4/")
        url = UPSTREAM + path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "accept-encoding")
        }
        # Avoid gzip so NewAPI gets plain JSON (urllib may leave \x1f compressed body).
        headers["Accept-Encoding"] = "identity"
        req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-encoding", "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            raw = e.read() if hasattr(e, "read") else str(e).encode()
            code = getattr(e, "code", 502) or 502
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw if isinstance(raw, (bytes, bytearray)) else raw.encode())

    def do_POST(self):
        self._fwd()

    def do_GET(self):
        self._fwd()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 3012), H).serve_forever()
