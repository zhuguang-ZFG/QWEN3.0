"""opencode_media_detect.py — Unsupported media type graceful degradation.

复刻 OpenCode transform.ts unsupportedParts() (L372-408)。
在发送消息前检测附件的 MIME type，如果后端不支持该模态，
将附件替换为错误提示文本，避免后端 400 错误。

核心功能:
  1. filter_unsupported_media() — 过滤/替换不支持的媒体附件
  2. mime_to_modality() — MIME type → 模态映射

支持的模态:
  - image (image/*)
  - audio (audio/*)
  - video (video/*)
  - pdf (application/pdf)
"""

from __future__ import annotations

import logging
from typing import Any

from provider_kind import detect_provider_kind

_log = logging.getLogger(__name__)

# ── MIME → modality mapping (transform.ts:10-15) ────────────────────────────


def mime_to_modality(mime: str) -> str | None:
    """Map a MIME type to an OpenCode modality string.

    Ported from transform.ts mimeToModality() (L10-15).
    """
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        return "pdf"
    return None


# ── Provider modality support (based on OpenCode models-dev capabilities) ────

# Default: assume image support only (most basic LLM vision)
_PROVIDER_MODALITY_SUPPORT: dict[str, frozenset[str]] = {
    "anthropic": frozenset({"image", "pdf"}),
    "openai": frozenset({"image", "audio"}),
    "google": frozenset({"image", "audio", "video", "pdf"}),
    "openrouter": frozenset({"image"}),
    "qwen": frozenset({"image"}),
    "kimi": frozenset({"image"}),
    "deepseek_reasoning": frozenset(),
    "openai_compatible": frozenset({"image"}),
}


def _get_supported_modalities(
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> frozenset[str]:
    """Get supported input modalities for a backend/model."""
    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    return _PROVIDER_MODALITY_SUPPORT.get(pk, frozenset({"image"}))


# ── Main filter function ────────────────────────────────────────────────────


def filter_unsupported_media(
    messages: list[dict],
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> list[dict]:
    """Filter/replace unsupported media attachments in user messages.

    Ported from transform.ts unsupportedParts() (L372-408).

    For each user message with array content:
      - image parts with empty base64 → error text
      - file/image parts with unsupported modality → error text
      - supported parts → kept as-is

    Args:
        messages: Message list (will not be mutated).
        backend_name: Backend identifier.
        model_id: Model identifier.
        provider_kind: Optional pre-computed provider kind.

    Returns:
        New message list with unsupported media replaced.
    """
    supported = _get_supported_modalities(backend_name, model_id, provider_kind)

    result = []
    for msg in messages:
        if msg.get("role") != "user":
            result.append(msg)
            continue

        content = msg.get("content")
        if not isinstance(content, list):
            result.append(msg)
            continue

        filtered_parts = []
        changed = False
        for part in content:
            if not isinstance(part, dict):
                filtered_parts.append(part)
                continue

            part_type = part.get("type")
            if part_type not in ("file", "image"):
                filtered_parts.append(part)
                continue

            # Check for empty base64 image (transform.ts:380-391)
            if part_type == "image":
                image_data = str(part.get("image", ""))
                if image_data.startswith("data:"):
                    mime_end, _, b64_data = image_data.partition(";base64,")
                    if not b64_data:
                        filtered_parts.append({
                            "type": "text",
                            "text": "ERROR: Image file is empty or corrupted. "
                                    "Please provide a valid image.",
                        })
                        changed = True
                        continue

                # Extract MIME from data URI or use mediaType
                mime = image_data.split(";")[0].replace("data:", "")
            else:
                # file type: use mediaType field
                mime = part.get("mediaType", "")

            filename = part.get("filename") if part_type == "file" else None
            modality = mime_to_modality(mime)

            if modality is None:
                # Unknown MIME — keep as-is
                filtered_parts.append(part)
                continue

            if modality in supported:
                filtered_parts.append(part)
                continue

            # Unsupported modality → replace with error text
            name = f'"{filename}"' if filename else modality
            filtered_parts.append({
                "type": "text",
                "text": f"ERROR: Cannot read {name} (this model does not support "
                        f"{modality} input). Inform the user.",
            })
            changed = True

        if changed:
            result.append({**msg, "content": filtered_parts})
        else:
            result.append(msg)

    return result
