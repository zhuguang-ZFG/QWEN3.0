"""Fake WeChat sidecar CLI - V1 guest experience smoke.

Usage:
    python scripts/wechat_bridge_fake.py --base-url http://127.0.0.1:8080 --sender wx-test-user
"""

import argparse
import json
import sys
import time
import urllib.request


def get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post(url: str, body: dict, token: str) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Fake WeChat sidecar - V1 guest smoke")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--token", default="test-sidecar-token")
    parser.add_argument("--sender", default="wx-test-user")
    parser.add_argument("--conversation", default="wx-conv-test")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    token = args.token
    sender = args.sender
    conv = args.conversation
    msg_counter = [0]

    def send(text: str) -> dict:
        msg_counter[0] += 1
        mid = f"fake-{int(time.time() * 1000)}-{msg_counter[0]}"
        body = {
            "message_id": mid,
            "sender_id": sender,
            "conversation_id": conv,
            "conversation_type": "private",
            "text": text,
            "timestamp": int(time.time()),
        }
        return post(f"{base}/channel/v1/wechat/message", body, token)

    def step(label: str) -> None:
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")

    # 1. Health
    step("1. Health check")
    resp = get(f"{base}/channel/v1/wechat/health", token)
    print(f"   Health: {json.dumps(resp, indent=2)}")
    assert resp.get("enabled"), "Bridge should be enabled"

    # 2. Create binding code
    step("2. Create binding code")
    resp = post(f"{base}/channel/v1/bind/start", {
        "channel": "wechat",
        "lima_user_id": "operator",
    }, token)
    print(f"   Bind start: {json.dumps(resp, indent=2)}")
    code = resp["binding_code"]
    assert len(code) == 6

    # 3. Bind (guest)
    step("3. Bind (guest)")
    result = send(f"/bind {code}")
    print(f"   Bind result: {json.dumps(result, indent=2)}")
    assert result["ok"], f"Bind failed: {result.get('error')}"
    assert "guest" in result["reply"]["text"].lower()

    # 4. Guest chat
    step("4. Guest plain chat")
    result = send("hello LiMa")
    print(f"   Chat: ok={result.get('ok')}")
    assert result["ok"]

    # 5. Guest /code
    step("5. Guest /code explain")
    result = send("/code explain a debounce function")
    print(f"   /code: ok={result.get('ok')}")
    assert result["ok"]

    # 6. Guest /draw
    step("6. Guest /draw demo")
    result = send("/draw LiMa")
    print(f"   /draw: ok={result.get('ok')}")
    assert result["ok"]

    # 7. Guest /demo
    step("7. Guest /demo")
    result = send("/demo")
    print(f"   /demo: ok={result.get('ok')}")
    assert result["ok"]

    # 8. Guest /about
    step("8. Guest /about")
    result = send("/about")
    print(f"   /about: ok={result.get('ok')}")
    assert result["ok"]

    # 9. Guest rejected /status
    step("9. Guest rejected: /status")
    result = send("/status")
    print(f"   /status: ok={result.get('ok')}")
    assert not result["ok"]
    assert "owner" in result.get("reply", {}).get("text", "").lower()

    # 10. Guest rejected /device
    step("10. Guest rejected: /device")
    result = send("/device write LiMa")
    print(f"   /device: ok={result.get('ok')}")
    assert not result["ok"]

    # 11. Guest rejected /artifact
    step("11. Guest rejected: /artifact")
    result = send("/artifact abc123")
    print(f"   /artifact: ok={result.get('ok')}")
    assert not result["ok"]

    # 12. Guest /reset
    step("12. Guest /reset")
    result = send("/reset")
    print(f"   /reset: ok={result.get('ok')}")
    assert result["ok"]

    # 13. Duplicate
    step("13. Duplicate message (dedupe)")
    body = {
        "message_id": "dup-test-001",
        "sender_id": sender,
        "conversation_id": conv,
        "conversation_type": "private",
        "text": "test duplicate",
        "timestamp": int(time.time()),
    }
    first = post(f"{base}/channel/v1/wechat/message", body, token)
    second = post(f"{base}/channel/v1/wechat/message", body, token)
    print(f"   First ok={first.get('ok')}, Second ok={second.get('ok')}")
    assert first.get("ok"), "First message should succeed"
    assert not second.get("ok"), "Duplicate should be rejected"

    # 14. Pause/resume
    step("14. Pause and resume flow")
    result = send("/pause")
    assert result["ok"]
    result = send("should be blocked")
    assert not result["ok"]
    result = send("/resume")
    assert result["ok"]

    # 15. Final health
    step("15. Final health")
    resp = get(f"{base}/channel/v1/wechat/health", token)
    print(f"   Health: {json.dumps(resp, indent=2)}")
    assert resp["bound_users"] >= 1

    print(f"\n{'=' * 60}")
    print("  ALL GUEST SMOKE STEPS PASSED")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
