"""Run on VPS: one QR attempt with full JSON + devicelibrary tail."""
import json
import subprocess
import urllib.request

BASE = "http://127.0.0.1:2531/v2/api"


def post(path: str, body: dict, token: str = "") -> dict:
    url = f"{BASE}/{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-GEWE-TOKEN"] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


tok = post("tools/getTokenId", {})["data"]
raw = post(
    "login/getLoginQrCode",
    {"appId": "", "regionId": "330000", "proxyIp": "", "type": "ipad"},
    tok,
)
print("qr_json", json.dumps(raw, ensure_ascii=False))
print("--- devicelibrary ---")
subprocess.run(
    [
        "podman",
        "exec",
        "gewe",
        "sh",
        "-c",
        "tail -n 15 /root/gewe/base/log/devicelibrary.txt 2>/dev/null || true",
    ],
    check=False,
)
print("--- env proxy ---")
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    import os

    if os.environ.get(k):
        print(k, "set")
