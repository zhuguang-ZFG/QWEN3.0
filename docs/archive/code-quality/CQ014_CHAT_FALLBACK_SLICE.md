# CQ-014 Slice 5: Chat Fallback Extraction

Date: 2026-05-25

## Problem

`routes/chat_handler.py` remained ~380 lines because the non-stream quality
fallback loop (same-tier + upgrade chain) lived inline in `handle_chat`.

## Decision

Extract fallback into `routes/chat_fallback.py` with `resolve_quality_fallback()`
and `QualityFallbackRequest` dataclass. Wire via `inject_deps` from `chat_handler`.

## Verification

- `pytest tests/test_chat_fallback.py tests/test_chat_handler.py -q`
- Full suite green before deploy
