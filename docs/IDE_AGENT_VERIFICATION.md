# IDE Agent Verification

> Updated: 2026-05-22
> Endpoint: `https://chat.donglicao.com/v1`
> Key used for verification: `lima-local`
> Model: `lima-1.3`

## Result

IDE/agent verification is complete for the private coding assistant baseline.

| Client Path | Command Shape | Result |
|---|---|---|
| OpenAI-compatible IDE request | `POST /v1/chat/completions` with IDE-like system text and exact-output prompt | Returned exact `phase-complete-ok`, backend `scnet_ds_flash` |
| Anthropic/Claude Code-compatible request | `POST /v1/messages` with Claude Code-like system text and exact-output prompt | Returned exact `ide-agent-complete` |
| Real Claude Code CLI | `ANTHROPIC_BASE_URL=https://chat.donglicao.com`, `ANTHROPIC_API_KEY=lima-local`, `claude --bare --model lima-1.3 --max-budget-usd 5 -p "Return exactly: claude-cli-ok"` | Returned exact `claude-cli-ok` |

## Connection Settings

For OpenAI-compatible clients:

```text
Base URL: https://chat.donglicao.com/v1
API Key: lima-local
Model: lima-1.3
```

For Claude Code CLI verification:

```powershell
$env:ANTHROPIC_API_KEY='lima-local'
$env:ANTHROPIC_BASE_URL='https://chat.donglicao.com'
claude --bare --model lima-1.3 --max-budget-usd 5 -p "Return exactly: claude-cli-ok"
```

## Boundary

This proves a real terminal agent and both API compatibility paths can use the endpoint. Longer hands-on IDE sessions can still improve latency/fallback tuning, but they are operational tuning, not a blocker for the phase exit criterion.
