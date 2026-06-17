"""Narrative Casting — reframe context during backend handoff.

Based on Google ADK Narrative Casting pattern:
- When fallback switches from backend A to backend B, reframe prior
  assistant messages so B doesn't think they're its own outputs
- Prevents identity confusion in multi-backend fallback chains
"""


def reframe_for_handoff(
    messages: list[dict],
    from_backend: str,
    to_backend: str,
) -> list[dict]:
    """Reframe assistant messages from a failed backend for handoff.

    Marks prior assistant messages as context from a different source,
    so the new backend doesn't confuse them with its own outputs.
    """
    if not from_backend or not messages:
        return messages

    reframed = []
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                reframed.append(
                    {
                        "role": "user",
                        "content": f"[前一个助手的回答，仅供参考:]\n{content}",
                    }
                )
            else:
                reframed.append(msg)
        else:
            reframed.append(msg)
    return reframed


def should_reframe(error_count: int, from_backend: str, to_backend: str) -> bool:
    """Decide whether to apply narrative casting for this handoff."""
    if not from_backend or not to_backend:
        return False
    if from_backend == to_backend:
        return False
    return error_count > 0


def inject_handoff_context(
    messages: list[dict],
    from_backend: str,
    to_backend: str,
    error_reason: str = "",
) -> list[dict]:
    """Full handoff: reframe messages + inject transition context."""
    reframed = reframe_for_handoff(messages, from_backend, to_backend)

    transition_note = f"[系统提示] 之前的请求由 {from_backend} 处理但失败了"
    if error_reason:
        transition_note += f"（原因: {error_reason[:80]}）"
    transition_note += "。请你重新回答用户的问题。"

    reframed.append({"role": "user", "content": transition_note})
    return reframed
