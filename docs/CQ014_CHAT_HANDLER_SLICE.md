# CQ-014 Slice 4: Chat Handler Extraction

Date: 2026-05-25

## Problem

`server.py` still ~611 lines because `_handle_chat`, `_stream_response`, and
supporting helpers lived in the entry module alongside app wiring.

## Decision

Extract chat execution into focused route modules:

- `routes/chat_support.py` — thinking route, sys-prompt logging, memory meta
- `routes/chat_stream.py` — OpenAI SSE stream generator
- `routes/chat_handler.py` — non-stream and stream dispatch (`handle_chat`)

`server.py` injects deps and re-exports `_handle_chat` for test compatibility.

## Scope

- Move logic from `server.py` lines ~124-571 into the modules above
- Reuse `response_builder._split_sentences` instead of duplicating
- Test: `tests/test_chat_handler.py`

## Out of scope

- Changing routing/fallback behavior
- Anthropic stream refactor (still injected from server)

## Verification

- `pytest tests/test_chat_handler.py tests/test_prompt_memory_recall.py tests/test_chat_endpoints.py -q`
- Full suite + VPS smoke before commit
