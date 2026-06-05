# Dev Search Review Follow-up Plan

## Scope

Close the review findings after LiMa dev-search:

- Harden public URL checks against IPv6 loopback, private/link-local ranges, metadata hosts, integer/hex IPv4 spellings, trailing-dot localhost hostnames, and hostnames that resolve to non-global IPs.
- Reuse the same URL safety check from TinyFish fetch transport and dev-read tools.
- Add Chinese dev-search intent markers for common LiMa prompts.
- Clamp MCP numeric arguments instead of returning raw `ValueError` strings.
- Make Telegram FC/TTS local modules optional so GitHub/VPS deployments do not depend on untracked files.

## Non-goals

- Do not track `fc_caller.py`, `tool_dispatcher.py`, or ignored `mimo_tts.py`.
- Do not wire dev-search into `routing_engine.py`.
- Do not deploy VPS in this round.

## Verification

- Add failing tests before code changes for each behavior.
- Run focused suites for dev-search, MCP, TinyFish transport, and Telegram commands.
- Run compileall and full pytest before commit.
