"""Channel Gateway LiMa integrations - guest-safe handlers.

V1: All handlers produce public/demo content only.
- Chat: routes through LiMa with guest persona, no private memory.
- Code: explanation/suggestion only, no task creation, no repo access.
- Draw: path preview metadata only, no Device Gateway queueing.
- Demo/About: static visitor-safe text.
- Reset: clears lightweight channel session only.
- Owner-only stubs: reserved for V2.
"""

import os
from typing import Callable, Optional


def build_chat_handler(
    route_fn: Optional[Callable] = None,
    call_api_fn: Optional[Callable] = None,
) -> Callable[[str, str], str]:
    """Guest chat handler: routes through LiMa with public persona."""

    if route_fn is None:
        import routing_engine
        import http_caller

        def _default_route(query, messages, call_fn):
            return routing_engine.route(query, messages, call_fn=call_fn)

        route_fn = _default_route
        call_api_fn = http_caller.call_api

    def handler(user_id: str, text: str) -> str:
        if not text.strip():
            return ""
        try:
            system_prompt = (
                "You are LiMa, a private coding and hardware assistant. "
                "You are talking to a guest user through WeChat. "
                "Be helpful, concise, and friendly. "
                "Do not mention internal infrastructure, server status, file paths, "
                "API keys, or private project details."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]
            if call_api_fn:
                result = route_fn(text, messages, call_fn=call_api_fn)
            else:
                result = route_fn(text, messages)
            answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
            return answer if answer else "LiMa returned an empty response."
        except Exception as e:
            return f"Chat error: {type(e).__name__}"

    return handler


def build_code_handler(
    route_fn: Optional[Callable] = None,
) -> Callable[[str, str], str]:
    """Guest code handler: explanation/suggestion only. No task creation, no repo reads."""

    if route_fn is None:
        import routing_engine
        import http_caller

        def _default_route(query, messages, call_fn):
            return routing_engine.route(query, messages, call_fn=call_fn)

        route_fn = _default_route
        call_api_fn = http_caller.call_api
    else:
        call_api_fn = None

    def handler(user_id: str, question: str) -> str:
        try:
            system_prompt = (
                "You are LiMa, a coding assistant. A guest user on WeChat is asking "
                "a code question. Explain clearly with examples if helpful. "
                "Do NOT create files, execute commands, or access repositories. "
                "This is a read-only explanation."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
            if call_api_fn:
                result = route_fn(question, messages, call_fn=call_api_fn)
            else:
                result = route_fn(question, messages)
            answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
            return answer if answer else "Could not explain that."
        except Exception as e:
            return f"Code help error: {type(e).__name__}"

    return handler


def build_draw_handler() -> Callable[[str, str], str]:
    """Guest draw handler: preview/demo metadata only. No Device Gateway queueing."""

    def handler(user_id: str, prompt: str) -> str:
        safe_text = prompt.strip()[:200]
        if not safe_text:
            return "Usage: /draw <prompt>"
        try:
            from device_gateway.path_pipeline import render_text_task

            rendered = render_text_task(safe_text)
            path = rendered.get("path") or []
            preview = str(rendered.get("preview_svg", ""))
            lines = [
                f"Draw demo: '{safe_text}'",
                "",
                "Preview (demo only — no hardware queue):",
                f"  Path points: {rendered.get('point_count', len(path))}",
                "  Font: stroke (demo)",
            ]
            if preview:
                lines.append(f"  SVG: {preview[:120]}{'...' if len(preview) > 120 else ''}")
            lines.extend([
                "",
                "This is a demo preview. Real device drawing requires owner access.",
            ])
            return "\n".join(lines)
        except ImportError:
            return (
                f"Draw demo: '{safe_text}'\n\n"
                "Preview not available (path pipeline not loaded).\n"
                "Real device drawing requires owner access."
            )

    return handler


def build_owner_rejection_handler(command_name: str) -> Callable:
    """Return a handler that always rejects with owner-only message."""

    def handler(*args):
        return f"/{command_name} is owner-only and not available in guest mode."

    return handler


# ── Owner-only command handlers (V2) ──────────────────────────────────────────


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
