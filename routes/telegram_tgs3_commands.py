"""TG-S3 operator commands — /s3 put, /s3 list, /s3 stats."""

from __future__ import annotations

import telegram_bot
from routes.telegram_tgs3 import tg_s3_list, tg_s3_stats


async def cmd_s3_put(chat_id: str, args: str) -> None:
    await telegram_bot.send_message(
        "TG-S3: send a file with caption `/s3 tag1,tag2` to archive it.\n"
        "Files are stored as Telegram documents with metadata.",
        chat_id=chat_id, parse_mode="Markdown",
    )


async def cmd_s3_list(chat_id: str, args: str) -> None:
    tag = args.strip()
    items = tg_s3_list(tag=tag) if tag else tg_s3_list()
    if not items:
        await telegram_bot.send_message("TG-S3 empty. Send files to archive.", chat_id=chat_id, parse_mode="")
        return
    lines = ["*TG-S3 Objects*"]
    for item in items[:15]:
        kb = item["size_bytes"] / 1024
        size = f"{kb:.0f}KB" if kb < 1024 else f"{kb/1024:.1f}MB"
        tags = ", ".join(item["tags"]) if item["tags"] else "-"
        lines.append(f"  `{item['filename'][:50]}` {size} [{tags}]")
    if len(items) > 15:
        lines.append(f"  ... +{len(items) - 15} more")
    await telegram_bot.send_message("\n".join(lines), chat_id=chat_id, parse_mode="Markdown")


async def cmd_s3_stats(chat_id: str, args: str) -> None:
    stats = tg_s3_stats()
    kb = stats["total_bytes"] / 1024
    size = f"{kb:.0f}KB" if kb < 1024 else f"{kb/1024:.1f}MB"
    await telegram_bot.send_message(
        f"*TG-S3 Stats*\n  Objects: {stats['total_objects']}\n  Size: {size}",
        chat_id=chat_id, parse_mode="Markdown",
    )
