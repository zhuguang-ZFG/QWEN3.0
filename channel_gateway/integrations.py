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
        try:
            from routes.device_gateway import _path_validator

            # Validate the prompt as if it were a path, but do NOT queue
            safe_text = prompt.strip()[:200]
            # Generate preview-safe metadata
            lines = [
                f"Draw demo: '{safe_text}'",
                "",
                "Preview (not sent to device):",
                f"  Text: {safe_text}",
                "  Font: stroke (demo)",
                "  Bounds: [0, 0, 100, 20] (demo)",
                "",
                "This is a demo preview. Real device drawing requires owner access.",
            ]
            return "\n".join(lines)
        except ImportError:
            safe_text = prompt.strip()[:200]
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
