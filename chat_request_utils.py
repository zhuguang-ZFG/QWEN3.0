"""Small helpers for chat-compatible request bodies."""


def _text_from_content_blocks(content: list) -> str:
    return " ".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def extract_last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return _text_from_content_blocks(content)
        return ""
    return ""


def extract_system_preview(messages: list, system=None, limit: int = 200) -> str:
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "system":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content[:limit]
        return ""

    if isinstance(system, str):
        return system[:limit]
    if isinstance(system, list):
        return _text_from_content_blocks(system)[:limit]
    return ""


def request_sampling_params(req) -> dict:
    """Return explicit client sampling params without materializing defaults."""
    fields = set(
        getattr(req, "model_fields_set", None)
        or getattr(req, "__fields_set__", set())
        or set()
    )
    out = {}
    if "temperature" in fields and getattr(req, "temperature", None) is not None:
        out["temperature"] = req.temperature
    if getattr(req, "top_p", None) is not None:
        out["top_p"] = req.top_p
    return out
