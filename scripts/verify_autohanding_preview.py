"""Verify autohanding.com free preview endpoint end-to-end.

Saves the returned handwritten PNG to /tmp/autohanding_preview.png.
"""

from __future__ import annotations

import asyncio
import sys

from integrations.autohanding import client


async def main() -> int:
    text = "你好，世界！这是一段测试手写文本。"
    if len(sys.argv) > 1:
        text = sys.argv[1]

    print(f"Requesting handwriting preview for: {text[:50]}...")
    try:
        png_bytes = await client.convert_text(
            text,
            font_type="0",
            paper_bg_type="20",
            mistake_rate=3,
            messy_ratio=0,
            char_random=0,
        )
    except client.AutohandingRateLimitError as exc:
        print(f"Rate limited: {exc}")
        return 1
    except client.AutohandingClientError as exc:
        print(f"Client error: {exc}")
        return 1

    output_path = "autohanding_preview.png"
    with open(output_path, "wb") as f:
        f.write(png_bytes)
    print(f"Saved {len(png_bytes)} bytes to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
