"""HTTP helpers for short-lived WebSocket tickets (smoke / manual checks)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


def _https_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def post_json(
    url: str,
    *,
    bearer: str | None = None,
    body: dict | None = None,
    timeout: float = 15,
) -> tuple[int, dict]:
    headers = {"User-Agent": "LiMaSmoke/1.0", "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    payload = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=_https_ctx(), timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def ws_url_with_ticket(base_url: str, ticket: str) -> str:
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}ticket={urllib.parse.quote(ticket, safe='')}"


def issue_chat_ws_ticket(host: str, api_key: str) -> str:
    status, body = post_json(f"https://{host}/v1/ws/ticket", bearer=api_key)
    if status != 200:
        raise RuntimeError(f"/v1/ws/ticket returned {status}: {body}")
    ticket = body.get("ticket")
    if not ticket:
        raise RuntimeError(f"/v1/ws/ticket missing ticket: {body}")
    return str(ticket)


def issue_device_ws_ticket(host: str, device_id: str, token: str) -> str:
    status, body = post_json(
        f"https://{host}/device/v1/ws/ticket",
        bearer=token,
        body={"device_id": device_id},
    )
    if status != 200:
        raise RuntimeError(f"/device/v1/ws/ticket returned {status}: {body}")
    ticket = body.get("ticket")
    if not ticket:
        raise RuntimeError(f"/device/v1/ws/ticket missing ticket: {body}")
    return str(ticket)
