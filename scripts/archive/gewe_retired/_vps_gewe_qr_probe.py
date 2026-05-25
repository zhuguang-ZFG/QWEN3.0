"""Run on VPS: probe Gewechat login QR across regions/types."""
import json
import sys
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


def main() -> None:
    tok = post("tools/getTokenId", {})["data"]
    print("token_ok", len(tok))
    regions = ["330000", "440000", "110000", "310000", "510000"]
    types = ["ipad", "mac", "win", "android"]
    for typ in types:
        for rid in regions:
            body = {"appId": "", "regionId": rid, "proxyIp": "", "type": typ}
            try:
                raw = post("login/getLoginQrCode", body, tok)
            except Exception as exc:
                print(typ, rid, "http_err", exc)
                continue
            print(typ, rid, "ret", raw.get("ret"), "msg", (raw.get("msg") or "")[:60])
            if raw.get("ret") == 200:
                d = raw.get("data") or {}
                print("  OK appId", d.get("appId"), "qr_len", len(str(d.get("qrImgBase64", ""))))
                sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
