"""Telegram operator tools: GitHub file read and Device Gateway status (TG-GH-4)."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx


def _public_chat_root() -> str:
    return os.environ.get("LIMA_PUBLIC_CHAT_ROOT", "https://chat.donglicao.com").rstrip("/")


def _loopback_root() -> str:
    return os.environ.get("LIMA_LOOPBACK_ROOT", "http://127.0.0.1:8080").rstrip("/")


def parse_github_args(args: str) -> tuple[str, str, str] | None:
    first_line = (args or "").splitlines()[0].strip()
    parts = first_line.split()
    if len(parts) < 2:
        return None
    repo = parts[0].strip()
    path = parts[1].strip()
    ref = parts[2].strip() if len(parts) > 2 else "main"
    if repo.count("/") != 1:
        return None
    return repo, path, ref


def fetch_github_file_text(repo: str, path: str, ref: str = "main", *, max_chars: int = 3500) -> str:
    from search_gateway.dev_tools import fetch_github_file, read_url

    if os.environ.get("TINYFISH_API_KEY", "").strip():
        from search_gateway.dev_adapter import get_dev_search_adapter

        adapter = get_dev_search_adapter()
        raw = fetch_github_file(repo, path, ref, adapter=adapter, max_chars=max_chars + 500)
    else:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path.lstrip('/')}"
        raw = read_url(raw_url, adapter=_RawUrlAdapter(), max_chars=max_chars + 500)
    return format_github_read(raw, max_chars=max_chars)


class _RawUrlAdapter:
    def extract_url(self, url: str) -> dict:
        from search_gateway.safety import is_public_http_url
        import urllib.request

        if not is_public_http_url(url):
            return {"ok": False, "error": "url_blocked"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LiMa-Telegram/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read(120_000).decode("utf-8", errors="replace")
            return {"ok": True, "title": url.split("/")[-1], "text": text}
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__}


def format_github_read(raw: dict, *, max_chars: int = 3500) -> str:
    if not raw.get("ok"):
        return f"GitHub read failed: {raw.get('error', 'unknown')}"
    title = raw.get("title") or raw.get("path") or "file"
    body = str(raw.get("text") or "")[:max_chars]
    return f"{title}\n---\n{body}"


async def fetch_device_gateway_status(
    *,
    client: httpx.AsyncClient | None = None,
    root: str = "",
) -> str:
    """Read-only Device Gateway health summary for Telegram."""
    bases = []
    if root:
        bases.append(root.rstrip("/"))
    else:
        bases.extend([_loopback_root(), _public_chat_root()])

    owns = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)

    last_err = ""
    try:
        for base in bases:
            url = f"{base}/device/v1/health"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                data = resp.json()
                lines = [
                    "Device Gateway",
                    f"status: {data.get('status', '?')}",
                    f"protocol: {data.get('protocol', '?')}",
                    f"task_store: {data.get('task_store', {}).get('backend', '?')}",
                    f"session_bus: listener={data.get('session_bus', {}).get('listener_alive', '?')}",
                    f"source: {urlparse(base).netloc or base}",
                ]
                pending = data.get("pending_tasks")
                if pending is not None:
                    lines.append(f"pending_tasks: {pending}")
                return "\n".join(lines)
            except Exception as exc:
                last_err = type(exc).__name__
                continue
    finally:
        if owns:
            await client.aclose()
    return f"Device Gateway unavailable ({last_err or 'no endpoint'})"


def append_recent_tasks_summary(lines: list[str], *, limit: int = 3) -> None:
    try:
        from routes.agent_tasks import _store

        tasks = sorted(_store.values(), key=lambda t: t.get("created_at", 0), reverse=True)
    except ImportError:
        return
    if not tasks:
        return
    lines.append(f"Recent tasks ({min(len(tasks), limit)}):")
    for task in tasks[:limit]:
        status = task.get("status", "?")
        req = task.get("request") or {}
        goal = str(req.get("goal", ""))[:60] if isinstance(req, dict) else "?"
        lines.append(f"  [{status}] {goal}")
