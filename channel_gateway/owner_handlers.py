"""Channel Gateway owner-only command handlers (V2).

Extracted from integrations.py for file-size compliance.
"""

from __future__ import annotations

import os
from typing import Callable


def build_owner_rejection_handler(command_name: str) -> Callable:
    """Return a handler that always rejects with owner-only message."""

    def handler(*args):
        return f"/{command_name} is owner-only and not available in guest mode."

    return handler


def build_owner_code_task_handler() -> Callable:
    """Owner /code-task <goal> — create an agent task for LiMa Code worker."""

    def handler(user_id: str, goal: str) -> str:
        if not goal.strip():
            return "Usage: /code-task <goal description>"
        try:
            from routes.agent_tasks import TaskCreateBody, _create_task_from_body

            created = _create_task_from_body(TaskCreateBody(
                repo="local",
                branch="main",
                goal=goal.strip()[:500],
                constraints=[f"channel_gateway_user={user_id[:80]}"],
                allowed_tools=[],
                max_runtime_sec=300,
                mode="patch",
            ))
            task_id = created["task_id"]
            return (
                f"Task {task_id} created.\n"
                f"Goal: {goal.strip()[:200]}\n"
                f"Run `/lima next` in LiMa Code to claim it."
            )
        except ImportError:
            return "Agent task store not available. Is the server loaded?"

    return handler


def build_owner_device_handler(queue_fn=None) -> Callable:
    """Owner /device <sub-command> — queue a device gateway task."""

    def handler(user_id: str, cmd: str) -> str:
        if not cmd.strip():
            return "Usage:\n/device text <content>\n/device draw <svg preview>\n/device home"
        try:
            device_id = "wechat-owner"
            if cmd.startswith("text "):
                text = cmd[5:].strip()[:1000]
                task = {"capability": "write_text", "text": text, "font": "stroke"}
            elif cmd.startswith("draw "):
                preview = cmd[5:].strip()[:4000]
                task = {"capability": "draw_generated", "preview_svg": preview}
            elif cmd.strip() == "home":
                task = {"capability": "home"}
            else:
                return f"Unknown device command: {cmd}\nUsage: text <content> | draw <svg> | home"

            if queue_fn:
                result = queue_fn(device_id, task)
            else:
                result = _queue_device_task_http(device_id, task)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            return f"Device task: {task.get('capability')} → {status}"
        except Exception as e:
            return f"Device error: {type(e).__name__}: {e}"

    return handler


def _voice_task_from_channel_task(task: dict) -> dict:
    capability = task.get("capability", "")
    if capability == "write_text":
        return {
            "capability": "write_text",
            "params": {"text": str(task.get("text", ""))[:1000]},
            "source": "channel_gateway",
        }
    if capability == "draw_generated":
        return {
            "capability": "draw_generated",
            "params": {"prompt": str(task.get("preview_svg", ""))[:4000]},
            "source": "channel_gateway",
        }
    if capability == "home":
        return {"capability": "home", "params": {}, "source": "channel_gateway"}
    return {
        "capability": "write_text",
        "params": {"text": str(task.get("text", ""))[:1000]},
        "source": "channel_gateway",
    }


def _queue_device_task_http(device_id: str, task: dict) -> dict:
    try:
        from device_gateway.tasks import enqueue_pending_task, project_to_motion_task

        voice_task = _voice_task_from_channel_task(task)
        result = project_to_motion_task(device_id, voice_task)
        if result.get("error"):
            return {
                "status": "failed",
                "task_id": result.get("task_id", "?"),
                "capability": result.get("capability", "?"),
                "error": result.get("error"),
            }
        enqueue_pending_task(device_id, result)
        return {
            "status": "queued",
            "task_id": result.get("task_id", "?"),
            "capability": result.get("capability", "?"),
        }
    except ImportError:
        return {"status": "device_gateway not loaded"}


def build_owner_status_handler() -> Callable:
    """Owner /status — show recent task, device, and backend health."""

    def handler(user_id: str) -> str:
        lines = ["LiMa Status\n"]
        try:
            from routes.agent_tasks import _store
            tasks = list(_store.values())
            tasks.sort(key=lambda t: t.get("created_at", 0), reverse=True)
            lines.append(f"Tasks: {len(tasks)} total")
            for t in tasks[:3]:
                status = t.get("status", "?")
                goal = str(t.get("request", {}).get("goal", "")) if isinstance(t.get("request"), dict) else "?"
                lines.append(f"  [{status}] {goal[:60]}")
        except ImportError:
            lines.append("Tasks: agent store not loaded")
        try:
            from device_gateway.sessions import registry
            lines.append(f"Device sessions: {registry.count()}")
        except ImportError:
            pass
        try:
            import health_tracker
            hm = health_tracker.get_health_map()
            dead = [b for b, s in hm.items() if s == "dead"]
            degraded = [b for b, s in hm.items() if s == "degraded"]
            lines.append(f"Backends: {len(dead)} dead, {len(degraded)} degraded")
            if dead:
                lines.append(f"  Dead: {', '.join(dead[:3])}")
        except ImportError:
            pass
        return "\n".join(lines)

    return handler


def build_owner_artifact_handler() -> Callable:
    """Owner /artifact <task_id> — show LiMa Code artifact bundle summary."""

    def handler(task_id: str) -> str:
        if not task_id.strip():
            return "Usage: /artifact <task_id>"
        try:
            from routes.agent_tasks import _store
            tid = task_id.strip()
            if not _store.contains(tid):
                return f"Task {tid} not found."
            task = _store.get(tid)
            result = task.get("result", {})
            artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
            files = result.get("changed_files", []) if isinstance(result, dict) else []
            status = task.get("status", "?")
            summary = str(result.get("summary", "no summary"))[:200] if isinstance(result, dict) else "no summary"
            lines = [
                f"Task {tid}: status={status}",
                f"Summary: {summary}",
                f"Artifacts: {', '.join(artifacts) if artifacts else 'none'}",
                f"Changed files ({len(files)}): {', '.join(files[:10])}",
            ]
            return "\n".join(lines)
        except ImportError:
            return "Agent task store not available."

    return handler


def build_owner_memory_handler() -> Callable:
    """Owner /memory [type <t>|search <q>|recent] — query session memory."""

    def handler(user_id: str, args: str) -> str:
        try:
            from session_memory.store import query_by_type, search_memories_keyword
            a = args.strip()
            if a.startswith("type "):
                mtype = a[5:].strip()
                entries = query_by_type(mtype, limit=5)
            elif a.startswith("search "):
                query = a[7:].strip()
                entries = search_memories_keyword("_global", query, limit=5)
            else:
                entries = query_by_type("routing_lesson", limit=5)
            if not entries:
                return "No memories found."
            lines = ["Recent memories:"]
            for e in entries:
                summary = (e.summary or "")[:80]
                mtype = getattr(e, "memory_type", "?")
                lines.append(f"  [{mtype}] {summary}")
            return "\n".join(lines)
        except ImportError:
            return "Session memory store not available."

    return handler


def build_owner_digest_handler() -> Callable[[str], str]:
    """Owner /简报 — morning digest (weather, tasks, backends)."""

    def handler(user_id: str) -> str:
        from channel_gateway.public_apis import fetch_time, fetch_weather

        city = os.environ.get("LIMA_CHANNEL_DIGEST_CITY", "北京")
        lines = ["LiMa 晨间简报", fetch_time().get("text", "")]
        w = fetch_weather(city)
        if w.get("ok"):
            lines.append(w["text"])
        else:
            lines.append(f"天气：{w.get('error', '不可用')}")
        lines.append(build_owner_status_handler()(user_id))
        try:
            from session_memory.store import query_by_type

            entries = query_by_type("routing_lesson", limit=3)
            if entries:
                lines.append("近期路由记忆：")
                for e in entries:
                    lines.append(f"  · {(e.summary or '')[:60]}")
        except ImportError:
            pass
        return "\n".join(lines)[:4000]

    return handler


def build_owner_github_handler() -> Callable[[str, str], str]:
    """Owner /github <owner/repo> <path> [ref] — fetch public file via search_gateway."""

    def handler(user_id: str, args: str) -> str:
        parts = args.split()
        if len(parts) < 2:
            return "用法：/github owner/repo path/to/file [ref]"
        repo = parts[0].strip()
        path = parts[1].strip()
        ref = parts[2].strip() if len(parts) > 2 else "main"
        if repo.count("/") != 1:
            return "仓库格式应为 owner/repo"
        adapter = None
        if os.environ.get("TINYFISH_API_KEY", "").strip():
            from search_gateway.dev_adapter import get_dev_search_adapter

            adapter = get_dev_search_adapter()
        else:
            try:
                from search_gateway.searxng_adapter import searxng_enabled

                if searxng_enabled():
                    from search_gateway.dev_adapter import get_dev_search_adapter

                    adapter = get_dev_search_adapter()
            except ImportError:
                pass
        if adapter is None:
            from search_gateway.dev_tools import read_url

            raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path.lstrip('/')}"
            return _format_github_read(
                read_url(raw_url, adapter=_StubExtractAdapter(), max_chars=6000)
            )
        from search_gateway.dev_tools import fetch_github_file

        raw = fetch_github_file(repo, path, ref, adapter=adapter, max_chars=6000)
        return _format_github_read(raw)

    return handler


class _StubExtractAdapter:
    """Minimal adapter for raw GitHub URLs when TinyFish is off."""

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        return {"ok": False, "error": "stub: search not available"}

    def batch_search(self, queries: list[str], *, domain: str | None = None, max_results: int = 5) -> dict:
        return {"ok": False, "error": "stub: batch_search not available"}

    def extract_url(self, url: str) -> dict:
        import urllib.request

        from search_gateway.safety import is_public_http_url

        if not is_public_http_url(url):
            return {"ok": False, "error": "url_blocked"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LiMa-ChannelTools/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read(120_000).decode("utf-8", errors="replace")
            return {"ok": True, "title": url.split("/")[-1], "text": text}
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__}


def _format_github_read(raw: dict) -> str:
    if not raw.get("ok"):
        return f"GitHub 读取失败：{raw.get('error', 'unknown')}"
    title = raw.get("title") or raw.get("path") or "file"
    body = str(raw.get("text") or "")[:3500]
    return f"【{title}】\n{body}"
