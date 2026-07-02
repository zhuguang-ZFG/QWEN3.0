"""唤醒词配置读取/保存/拼音转换（从 http_server.py 提取，纯逻辑无 socket 依赖）。

ponytail: 无 socket/self 依赖，便于单测；上限是拼音转换依赖 pypinyin。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..bridge import WakewordEventBridge
from ..config.config_loader import load_config


def build_wakeword_config_message(bridge: WakewordEventBridge, test_root: Path) -> str:
    """读取配置并构建 wakeword_config 消息。"""
    try:
        runtime_root = test_root / "wakeword_runtime"
        config = load_config(runtime_root)
        payload = {
            "enabled": config.wakeword_enabled,
            "wakeWords": config.wake_words,
        }
        return bridge.build_message("wakeword_config", payload)
    except Exception as exc:
        return bridge.build_message(
            "wakeword_config",
            {},
            success=False,
            error=f"读取唤醒词配置失败: {exc}",
        )


def save_wakeword_config(payload: dict, test_root: Path) -> dict:
    """保存唤醒词开关与词表到 config.json + keywords.txt，返回归一化结果。"""
    runtime_root = test_root / "wakeword_runtime"
    config_path = runtime_root / "config.json"
    model_root = runtime_root / "models"
    keywords_path = model_root / "keywords.txt"

    enabled = bool(payload.get("enabled", True))
    wake_words = payload.get("wakeWords") or []
    normalized_wake_words = []
    for item in wake_words:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and text not in normalized_wake_words:
            normalized_wake_words.append(text)

    if enabled and not normalized_wake_words:
        raise ValueError("wakeWords cannot be empty when wakeword is enabled")

    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    raw_config.setdefault("wakeword", {})["enabled"] = enabled
    config_path.write_text(
        json.dumps(raw_config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    keywords_lines = [build_keyword_line(item) for item in normalized_wake_words]
    keywords_path.write_text(
        ("\n".join(keywords_lines) + "\n") if keywords_lines else "",
        encoding="utf-8",
    )

    return {
        "enabled": enabled,
        "wakeWords": normalized_wake_words,
    }


def build_keyword_line(keyword_text: str) -> str:
    """生成 keywords.txt 的单行：拼音首/尾声 + @原词。"""
    from pypinyin import Style, pinyin

    initials = pinyin(keyword_text, style=Style.INITIALS, strict=False)
    finals = pinyin(
        keyword_text,
        style=Style.FINALS_TONE,
        strict=False,
        neutral_tone_with_five=True,
    )

    tokens: list[str] = []
    for initial_parts, final_parts in zip(initials, finals, strict=False):
        initial = initial_parts[0].strip()
        final = final_parts[0].strip()
        if initial:
            tokens.append(initial)
        if final:
            tokens.append(final)

    if not tokens:
        raise ValueError(f"failed to generate pinyin tokens for wake word: {keyword_text}")

    return f"{' '.join(tokens)} @{keyword_text}"
