# Free Web AI Candidates

> Updated: 2026-05-22
> State: sandbox research only. Private code is not allowed for these candidates.

| ID | URL | Access | Trust | Current State | Next Check |
|---|---|---|---|---|---|
| duck_ai | https://duck.ai/chat | no-login web | medium-high | reachable: 200, 251ms | capture harmless request flow |
| heck_ai | https://heck.ai/zh | no-login web | medium | reachable: 200, 11060ms | capture harmless request flow; latency risk |
| hix_chat | https://hix.ai/a/chat | no-login web | low-medium | reachable: 200, 1325ms | check limits and data policy |
| gpt_chat | https://gpt.chat | no-login web | low | reachable: 200, 3544ms | harmless probe only |
| deep_seek_mirror | https://deep-seek.com | no-login web | low | reachable: 200, 1121ms | verify provenance |
| plai_chat | https://plai.chat | no-login web | low-medium | reachable: 200, 1252ms | inspect model list and limits |

## Rules

- Keep every candidate disabled by default.
- Do not send private code or real IDE context to any candidate until it passes admission checks.
- Use only harmless probes during research.
- Normalize failures into stable LiMa classes before routing decisions use them.
- Prefer documented APIs. Treat undocumented web protocols as fragile and late fallback only.

## Current Probe Scope

The first probe harness only checks reachability and classifies obvious blocking, quota, auth, timeout, and provider errors. It does not automate browser sessions, bypass challenges, or send private prompts.

Latest command:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20
```

Output file:

```text
data/free_web_ai_probe_results.json
```
