"""Shared helpers for chat request handling (CQ-014 slice 4)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime

import asyncio

import smart_router


async def thinking_route(query: str, max_tokens: int = 4096, ide: str = "unknown") -> dict | None:
    """Route to a thinking-capable backend. Returns result dict or None on failure."""
    thinking_backend = smart_router.get_thinking_backend()
    msgs = [{"role": "user", "content": query}]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(smart_router.call_api, thinking_backend, msgs, max_tokens, ide),
            timeout=90.0,
        )
        if result and not (
            isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)
        ):
            return {"answer": result, "backend": thinking_backend, "thinking_mode": True}
    except (asyncio.TimeoutError, Exception) as exc:
        if smart_router.DEBUG:
            print(f"[THINKING] {thinking_backend} failed: {exc}", file=sys.stderr)
    for alt in smart_router.THINKING_BACKENDS:
        if alt == thinking_backend:
            continue
        if alt not in smart_router.BACKENDS or not smart_router.BACKENDS[alt].get("key"):
            continue
        if not smart_router.cb_allow(alt):
            continue
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(smart_router.call_api, alt, msgs, max_tokens, ide),
                timeout=90.0,
            )
            if result and not (
                isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)
            ):
                return {"answer": result, "backend": alt, "thinking_mode": True}
        except (asyncio.TimeoutError, Exception):
            continue
    return None


def attach_memory_recall_meta(response: dict, memory_meta: dict) -> dict:
    if memory_meta.get("checked") and isinstance(response, dict):
        response.setdefault("x_lima_meta", {})["memory_recall"] = memory_meta
    return response


def attach_context_injection_meta(response: dict, injection_meta: dict | None) -> dict:
    """Attach routing injection trace (retrieval/memory/skills) without full prompts."""
    if isinstance(response, dict) and injection_meta:
        response.setdefault("x_lima_meta", {})["context_injection"] = injection_meta
    return response


def attach_lima_meta(
    response: dict,
    *,
    memory_meta: dict | None = None,
    injection_meta: dict | None = None,
) -> dict:
    if memory_meta:
        attach_memory_recall_meta(response, memory_meta)
    if injection_meta:
        attach_context_injection_meta(response, injection_meta)
    return response


def log_sys_prompt(sys_prompt: str) -> None:
    """Record new system prompts with SHA256 dedup."""
    os.makedirs(smart_router.DISTILL_QUEUE_DIR.replace("pending", "sys_prompts"), exist_ok=True)
    phash = hashlib.sha256(sys_prompt.encode()).hexdigest()[:16]
    sys_prompt_dir = os.path.join(os.path.dirname(smart_router.DISTILL_QUEUE_DIR), "sys_prompts")

    existing = os.listdir(sys_prompt_dir) if os.path.exists(sys_prompt_dir) else []
    if any(phash in name for name in existing):
        return

    ide_source = "unknown"
    ide_markers = {
        "OpenCode": "opencode",
    }
    for marker, source in ide_markers.items():
        if marker in sys_prompt:
            ide_source = source
            break

    entry = {
        "ide_source": ide_source,
        "prompt_hash": phash,
        "prompt_preview": sys_prompt[:500],
        "prompt_length": len(sys_prompt),
        "logged_at": datetime.now().isoformat(),
    }
    fname = os.path.join(sys_prompt_dir, f"{ide_source}_{phash}.json")
    with open(fname, "w", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, indent=2)
    if smart_router.DEBUG:
        print(f"[SYS_PROMPT] new: {ide_source} ({len(sys_prompt)} chars)", file=sys.stderr)
