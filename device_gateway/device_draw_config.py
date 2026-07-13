"""绘图请求配置解析 — 从 device_draw_handler.py 拆出以控制行数。"""

from __future__ import annotations

import logging

from device_gateway.draw_prompt_enhancer import (
    get_draw_conversation_context,
    get_failed_draw_prompts,
    resolve_device_type,
)

logger = logging.getLogger(__name__)

# try_backends backend name → DashScope model (matches DEVICE_ROLE_PREFERENCES).
DRAW_BACKEND_MODELS = {
    "dashscope_wanx": "wanx2.1-t2i-turbo",
    "dashscope_flux": "flux-schnell",
}

# Whitelist of DashScope wanx models that callers may request; prevents
# arbitrary/high-cost model injection via user-supplied prefs["model"].
ALLOWED_WANX_MODELS: frozenset[str] = frozenset(DRAW_BACKEND_MODELS.values())


def resolve_draw_model(backend_name: str, caller_model: str) -> str:
    """Map try_backends entry to DashScope model; caller overrides wanx only.

    ``caller_model`` is accepted only if it appears in ``ALLOWED_WANX_MODELS``;
    unknown values fall back to the default for the backend.
    """
    default_model = DRAW_BACKEND_MODELS.get(backend_name, "wanx2.1-t2i-turbo")
    if caller_model and backend_name == "dashscope_wanx" and caller_model in ALLOWED_WANX_MODELS:
        return caller_model
    return default_model


def _resolve_draw_request(prefs: dict, device_id: str | None, prompt: str) -> dict:
    """Resolve drawing request config and log the request."""
    model = prefs.get("model", "wanx2.1-t2i-turbo")
    size = prefs.get("size", "1024*1024")
    device_type = resolve_device_type(device_id, prefs)
    style = str(prefs.get("style", "简约"))
    complexity = str(prefs.get("complexity", "中"))
    font_name = prefs.get("font_name") or prefs.get("font")
    failed_prompts = get_failed_draw_prompts(device_id)
    conversation_context = get_draw_conversation_context(device_id, prompt)

    logger.info(
        f"Device {device_id} draw request: {prompt[:50]}... (model={model}, "
        f"device_type={device_type}, font_name={font_name})"
    )
    return {
        "model": model,
        "size": size,
        "device_type": device_type,
        "style": style,
        "complexity": complexity,
        "font_name": font_name,
        "failed_prompts": failed_prompts,
        "conversation_context": conversation_context,
    }
