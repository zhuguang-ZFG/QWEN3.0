# Free Web AI Candidates

> Updated: 2026-05-22
> State: sandbox research only for page-only candidates. Private code is not allowed for these candidates.

Important correction: DuckAI is already reverse-engineered locally under `D:\duckai`; HeckAI already has a worker draft under `D:\ollama_server\heckai-worker.js`. They are no longer plain "capture from scratch" candidates.

| ID | URL | Access | Trust | Current State | Next Check |
|---|---|---|---|---|---|
| duck_ai | https://duck.ai/chat | no-login web | medium-high | already reversed locally; `4500` models/chat OK; LiMa `no_system` path fixed; `gpt4o-mini` and `gpt5-mini` passed local coding admission | repair public tunnel; keep late fallback until stability run |
| heck_ai | https://heck.ai/zh | no-login web | medium | page reachable; existing worker draft in `D:\ollama_server\heckai-worker.js` | smoke existing draft before new capture; latency risk |
| hix_chat | https://hix.ai/a/chat | no-login web | low-medium | reachable: 200, 1325ms; not reversed | check limits and data policy later |
| gpt_chat | https://gpt.chat | no-login web | low | reachable: 200, 3544ms; not reversed | harmless probe only |
| deep_seek_mirror | https://deep-seek.com | no-login web | low | reachable: 200, 1121ms; not reversed | verify provenance |
| plai_chat | https://plai.chat | no-login web | low-medium | reachable: 200, 1252ms; not reversed | inspect model list and limits |

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
