# Free Web AI Candidates

> Updated: 2026-05-22
> State: sandbox research only for page-only candidates. Private code is not allowed for these candidates.

Important correction: DuckAI is already reverse-engineered locally under `D:\duckai`; HeckAI already has a worker draft under `D:\ollama_server\heckai-worker.js`. They are no longer plain "capture from scratch" candidates.

| ID | URL | Access | Trust | Current State | Next Check |
|---|---|---|---|---|---|
| duck_ai | https://duck.ai/chat | no-login web | medium-high | probe OK; already reversed locally; `gpt4o-mini` and `gpt5-mini` passed local coding admission | admitted late fallback only; private code still disabled |
| heck_ai | https://heck.ai/zh | no-login web | medium | probe OK; existing worker draft in `D:\ollama_server\heckai-worker.js` | adapter draft pending; model smoke required |
| hix_chat | https://hix.ai/a/chat | no-login web | low-medium | probe OK; not reversed | sandbox only |
| gpt_chat | https://gpt.chat | no-login web | low | probe OK; not reversed | sandbox only |
| deep_seek_mirror | https://deep-seek.com | no-login web | low | probe OK; not reversed | sandbox only |
| plai_chat | https://plai.chat | no-login web | low-medium | probe OK; not reversed | sandbox only |
| deep_seek_ai | https://deep-seek.ai/ | no-login web | low | probe OK; not reversed | sandbox only |
| glm_ai_chat | https://glm-ai.chat/ | no-login web | low | probe OK; not reversed | sandbox only |
| instantseek | https://instantseek.org/ | no-login web | low | probe unknown_error; not reversed | sandbox only |
| chat_gpt_org | https://chat-gpt.org/ | no-login web | low | probe OK; not reversed | sandbox only |

## Rules

- Keep every candidate disabled by default.
- Do not send private code or real IDE context to any candidate until it passes admission checks.
- Use only harmless probes during research.
- Normalize failures into stable LiMa classes before routing decisions use them.
- Prefer documented APIs. Treat undocumented web protocols as fragile and late fallback only.

## Current Probe Scope

The first probe harness only checks reachability and classifies obvious blocking, quota, auth, timeout, and provider errors. It does not automate browser sessions, bypass challenges, or send private prompts.

Current local reverse inventory:

```text
docs/LOCAL_REVERSE_AI_STATUS.md
data/local_reverse_ai_inventory.json
```

Latest command:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20
```

Output file:

```text
data/free_web_ai_probe_results.json
```

Admission record:

```text
docs/FREE_WEB_AI_ADMISSION.md
data/free_web_ai_admission.json
```
