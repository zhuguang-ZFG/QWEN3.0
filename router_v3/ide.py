"""IDE source detection helpers for LiMa Router V3."""

from backends_constants import _IDE_FINGERPRINTS


def detect_ide_by_fingerprints(text: str) -> str:
    """根据文本内容检测 IDE 来源。

    Args:
        text: 要检测的文本（通常是 system prompt 或消息内容）

    Returns:
        IDE 名称（如 "cursor", "claude_code" 等），未检测到则返回空字符串
    """
    if not text or not isinstance(text, str):
        return ""

    text_lower = text.lower()
    for ide, markers in _IDE_FINGERPRINTS.items():
        for marker in markers:
            if marker.lower() in text_lower:
                return ide
    return ""


def detect_ide_from_system_prompt(text: str) -> str:
    """公开接口：从 system prompt 检测 IDE 来源"""
    for ide, markers in _IDE_FINGERPRINTS.items():
        if any(m in text for m in markers):
            return ide
    return ""
