# Telegram FC/TTS Repo Admission

Date: 2026-05-23

## Context

The Telegram command path can optionally call local Function Calling and TTS helpers:

- `fc_caller.py`
- `tool_dispatcher.py`
- `mimo_tts.py`

These helpers were previously treated as local-only prototype files. That made GitHub/VPS deployment reproducibility weaker because Telegram code could refer to modules that were not tracked by Git.

## Goal

Formally admit the optional Telegram FC/TTS helper modules into the repository while keeping them outside the core request-routing path.

## Constraints

- Do not route ordinary IDE/chat requests through `fc_caller`.
- Do not commit hardcoded API keys, passwords, cookies, or tokens.
- Keep Telegram FC/TTS optional: missing or unconfigured external credentials must degrade cleanly.
- Do not promote `tool_dispatcher.py` into LiMa dev-search; dev-search keeps its smaller focused modules.

## Changes

- Track `fc_caller.py`, `tool_dispatcher.py`, and `mimo_tts.py`.
- Stop ignoring `mimo_tts.py` in `.gitignore`.
- Add local module quality tests for:
  - unique Function Calling tool names;
  - `get_news` returning `missing_gnews_api_key` without network access when `GNEWS_API_KEY` is unset;
  - `mimo_tts.tts()` returning `None` without network access when `MIMO_TTS_KEY` is unset.
- Extend secret hygiene coverage to the newly admitted runtime files.

## Admission Notes

- `tool_dispatcher.py` has been split into the focused `lima_fc_tools` package and now remains only as a compatibility facade.
- Duplicate tool registration now uses last-definition-wins replacement to keep the exported tool schema valid.
- `GNEWS_API_KEY` and `MIMO_TTS_KEY` are environment-only credentials.
- `fc_caller.py` remains behind Telegram command usage and is not imported by normal routing.

## Verification

Run before commit:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_local_tool_modules.py tests\test_secret_hygiene.py tests\test_telegram_bot.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m py_compile fc_caller.py mimo_tts.py tool_dispatcher.py
D:\GIT\venv\Scripts\python.exe -m compileall -q fc_caller.py mimo_tts.py tool_dispatcher.py routes tests
D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model
```
