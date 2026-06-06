import logging

_log = logging.getLogger(__name__)
"""Server request context staging."""

from dataclasses import dataclass

from response_builder import messages_to_dicts


@dataclass
class ServerPromptContext:
    request_messages: list[dict]
    prompt_context_messages: list[dict]
    system_prompt: str
    memory_recall_meta: dict
    memory_session_id: str


def messages_with_system_context(messages: list[dict], system_prompt: str) -> list[dict]:
    prompt = (system_prompt or "").strip()
    base_messages = [m for m in (messages or []) if m.get("role") != "system"]
    if not prompt:
        return base_messages
    return [{"role": "system", "content": prompt}] + base_messages


def build_prompt_context(
    req,
    *,
    system_prompt: str = "",
    request_headers: dict | None = None,
    client_ip: str = "",
    ide_source: str = "",
    trace=None,
) -> ServerPromptContext:
    request_messages = messages_to_dicts(req.messages)
    memory_recall_meta = {"checked": False, "applied": False, "prompt_chars_added": 0}
    memory_session_id = ""

    try:
        from session_memory.prompt_recall import apply_prompt_memory_recall

        recall = apply_prompt_memory_recall(
            request_messages,
            system_prompt=system_prompt or "",
            headers=request_headers,
            client_ip=client_ip,
            ide_source=ide_source,
            trace=trace,
        )
        system_prompt = recall.system_prompt
        memory_recall_meta = recall.meta()
        memory_session_id = recall.session_id
    except ImportError:
        _log.debug("server_context: optional module not available", exc_info=True)
    return ServerPromptContext(
        request_messages=request_messages,
        prompt_context_messages=messages_with_system_context(
            request_messages,
            system_prompt,
        ),
        system_prompt=system_prompt,
        memory_recall_meta=memory_recall_meta,
        memory_session_id=memory_session_id,
    )
