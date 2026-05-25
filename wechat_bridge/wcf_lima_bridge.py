"""WeChatFerry (Windows PC 微信) -> LiMa Channel Gateway bridge.

Requires: Windows, matching WeChat PC + wcferry, SSH tunnel to VPS :8080.

  ssh -N -L 8080:127.0.0.1:8080 -i %USERPROFILE%\.ssh\id_ed25519 root@47.112.162.80

  set LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080
  set LIMA_WECHAT_SIDECAR_TOKEN=<from VPS /opt/lima-router/.env>
  python -m wechat_bridge.wcf_lima_bridge
"""

from __future__ import annotations

import os
import sys
import time

from wechat_bridge.lima_client import post_wechat_message


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> None:
    try:
        from wcferry import Wcf
    except ImportError:
        print("pip install wcferry")
        sys.exit(1)

    base = _env("LIMA_CHANNEL_BASE_URL", "http://127.0.0.1:8080")
    token = _env("LIMA_WECHAT_SIDECAR_TOKEN")
    if not token:
        print("Set LIMA_WECHAT_SIDECAR_TOKEN (VPS /opt/lima-router/.env)")
        sys.exit(2)

    wcf = Wcf()
    if not wcf.is_login():
        print("请先登录 Windows 微信 PC 客户端（需与 wcferry 版本匹配）")
        sys.exit(3)

    wcf.enable_receiving_msg()
    print("WCF bridge running. Send a private text to this WeChat to test.")

    while wcf.is_receiving_msg():
        for msg in wcf.get_msg():
            if msg.type != 1:
                continue
            sender = str(getattr(msg, "sender", "") or "")
            if not sender or sender.endswith("@chatroom"):
                continue
            if str(getattr(msg, "roomid", "") or "").endswith("@chatroom"):
                continue
            text = str(getattr(msg, "content", "") or "").strip()
            if not text:
                continue
            mid = f"wcf-{msg.id}-{int(time.time())}"
            result = post_wechat_message(
                base_url=base,
                sidecar_token=token,
                message_id=mid,
                sender_id=sender,
                conversation_id=sender,
                text=text,
                timestamp=int(time.time()),
            )
            reply = ""
            if result.get("ok") and isinstance(result.get("reply"), dict):
                reply = str(result["reply"].get("text") or "")
            elif result.get("error"):
                reply = f"LiMa: {result['error']}"
            if reply:
                try:
                    wcf.send_text(reply[:4000], sender)
                except Exception as exc:
                    print("send_fail", type(exc).__name__)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
