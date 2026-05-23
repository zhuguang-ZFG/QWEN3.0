"""Prompt-time Session Memory recall integration."""

from dataclasses import dataclass, field
import logging

from context_pipeline import RequestContext

log = logging.getLogger(__name__)


@dataclass
class PromptMemoryRecallResult:
    system_prompt: str
    applied: bool = False
    session_id: str = ""
    prompt_chars_added: int = 0
    headers: dict = field(default_factory=dict)

    def meta(self) -> dict:
        return {
            "checked": True,
            "applied": self.applied,
            "prompt_chars_added": self.prompt_chars_added,
        }


def build_memory_headers(
    headers: dict | None = None,
    *,
    client_ip: str = "",
    ide_source: str = "",
) -> dict:
    """Build stable memory headers from request headers plus server-derived facts."""
    merged = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if client_ip and "x-forwarded-for" not in merged and "x-real-ip" not in merged:
        merged["x-forwarded-for"] = client_ip
    if ide_source and "user-agent" not in merged:
        merged["user-agent"] = ide_source
    return merged


def _normalise_messages(messages: list) -> list[dict]:
    normalised = []
    for msg in messages or []:
        role = msg.role if hasattr(msg, "role") else msg.get("role", "")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        normalised.append({"role": role, "content": content})
    return normalised


def _update_span_metadata(span, values: dict) -> None:
    if hasattr(span, "metadata"):
        span.metadata.update(values)
    elif isinstance(span, dict):
        span.setdefault("metadata", {}).update(values)


def apply_prompt_memory_recall(
    messages: list,
    *,
    system_prompt: str = "",
    headers: dict | None = None,
    client_ip: str = "",
    ide_source: str = "",
    trace=None,
) -> PromptMemoryRecallResult:
    """Inject relevant session memory before routing, failing open on errors."""
    memory_headers = build_memory_headers(
        headers, client_ip=client_ip, ide_source=ide_source)
    base_prompt = system_prompt or ""
    span = None

    try:
        from session_memory.processor import (
            _session_id_from_headers,
            session_memory_processor,
        )

        session_id = _session_id_from_headers(memory_headers)
        if trace:
            span = trace.start_span(
                "prompt_memory_recall",
                session_id=session_id,
                message_count=len(messages or []),
            )

        ctx = RequestContext(
            headers=memory_headers,
            messages=_normalise_messages(messages),
            system_prompt=base_prompt,
        )
        ctx = session_memory_processor(ctx)
        recalled_prompt = ctx.system_prompt or ""
        added = max(0, len(recalled_prompt) - len(base_prompt))
        applied = recalled_prompt != base_prompt

        result = PromptMemoryRecallResult(
            system_prompt=recalled_prompt,
            applied=applied,
            session_id=session_id,
            prompt_chars_added=added,
            headers=memory_headers,
        )
        if span is not None:
            _update_span_metadata(span, result.meta())
        return result
    except Exception as exc:
        if span is not None:
            _update_span_metadata(span, {
                "checked": True,
                "applied": False,
                "error": type(exc).__name__,
            })
        log.debug("prompt memory recall skipped: %s", exc)
        return PromptMemoryRecallResult(
            system_prompt=base_prompt,
            session_id="",
            headers=memory_headers,
        )
    finally:
        if trace and span is not None:
            trace.end_span(span)
