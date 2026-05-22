# Local Reverse AI Status

> Updated: 2026-05-22
> Scope: Windows local machine plus LiMa registration state under `D:\GIT`.

## Current Answer

DuckAI is already reverse-engineered locally. It should not be treated as a new no-login web candidate. The local service is OpenAI-compatible on port `4500`; LiMa now has a `no_system` request path for DuckAI so it no longer sends the rejected OpenAI `system` role to this backend.

SCNet-large is also already reverse-engineered and usable through the Windows local proxy on `4505`. Kimi and TheOldLLM have local proxy/reverse code, but their current chat paths are blocked by quota/session or timeout. HeckAI and Umint have adapter drafts, but they are not running or registered in LiMa. HIX Chat, GPT.chat, Deep-seek mirror, and PLAI.chat are only page-reachability candidates at this point.

## Runtime Inventory

| Port | Process | Local Role | Smoke Result | Decision |
|---:|---|---|---|---|
| `4500` | `bun run src/server.ts` in `D:\duckai` | DuckAI OpenAI-compatible bridge | `/v1/models` OK; user-only chat OK; LiMa `no_system` request body fixed | Already reversed; keep late fallback until more route evidence |
| `4501` | `node token_refresh_server.js` | TheOldLLM token refresh helper | `/health` returned `Not Found`; `/refresh` now reports token presence only | Helper only, not a model endpoint |
| `4502` | `node D:/ollama_server/oldllm_proxy.js` | TheOldLLM local proxy | `/v1/models` OK; local chat timed out after 30s | Already reversed, currently unhealthy |
| `4503` | `python D:/ollama_server/g4f_server.py` | g4f local OpenAI-compatible wrapper | `/v1/models` OK; default chat OK; PollinationsAI plus `gpt-4o-mini` invalid | Generic wrapper usable only after provider/model mapping |
| `4504` | `node kimi_proxy.js` | Kimi local proxy | `/v1/models` OK; chat returns `chat.anonymous_usage_exceeded` | Already proxied, needs session refresh/login |
| `4505` | `node scnet_large_proxy.js` | SCNet-large local proxy | `/v1/models` OK; chat OK; coding route eval 3/3 for both models | Already reversed and strong on Windows local path |
| `8080` | Windows LiMa router | Local OpenAI/Anthropic entry | `/health` OK; chat OK via `scnet_qwen235b` | Local route is live |
| `8088` | VPS FRP path to Windows `8080` | Public validation path | `/health` OK from public IP path | FRP path remains closed-loop |
| `11434` | Ollama | Local model server | Listening | Local model capacity, not web reverse |

## Already Reverse-Engineered Or Proxied

| Provider | Evidence | LiMa Registration | Current State | Next Action |
|---|---|---|---|---|
| DuckAI / DuckDuckGo AI | `D:\duckai\src\duckai.ts` calls `duckduckgo.com/duckchat/v1/status` and `/chat`; port `4500` exposes six models | `ddg_gpt4o_mini`, `ddg_gpt5_mini`, `ddg_claude_haiku_45`, `ddg_llama4`, `ddg_mistral`, `ddg_tinfoil_gptoss_120b` | `ddg_gpt4o_mini` and `ddg_gpt5_mini` passed 3/3 local coding fixtures; `ddg_claude_haiku_45` failed strict JSON; `ddg_tinfoil_gptoss_120b` returned 500/cooldown; public `ddg.zhuguang.ccwu.cc` still returns 1033 | Keep `gpt4o-mini` and `gpt5-mini` as late local fallback; repair/replace public tunnel before VPS use |
| SCNet-large local | `D:\ollama_server\scnet_large_proxy.js`; port `4505` | `scnet_large_ds_flash`, `scnet_large_ds_pro` | Local chat works; route eval passed 3/3 for both models; `flash` averaged 987ms, `pro` averaged 3899ms | Eligible for stronger local/FRP routing, but only behind a local-proxy topology guard |
| SCNet direct worker | `D:\ollama_server\scnet-worker.js`; public `scnet.zhuguang.ccwu.cc` registered | `scnet_qwen30b`, `scnet_qwen235b`, `scnet_ds_flash`, `scnet_ds_pro`, `scnet_minimax` | Direct SCNet winners are already first-tier coding backends; `/v1/models` endpoint is not implemented on the public worker | Keep first-tier winners; keep `scnet_minimax` inactive until timeout fixed |
| Kimi local | `D:\ollama_server\kimi_proxy.js`; port `4504` | `kimi`, `kimi_thinking`, `kimi_search` | Models endpoint works; chat blocked by anonymous quota/session state; `health_tracker` classifies as `manual_refresh_required`; refresh logs now redacted | Refresh session with environment token set; keep inactive until chat passes |
| Kimi worker draft | `D:\ollama_server\kimi-worker.js` | Not currently a primary LiMa route | Code exists for CF Worker style proxy | Do not promote until token refresh and smoke pass |
| TheOldLLM | `D:\ollama_server\oldllm_proxy.js`, `lima-oldllm-v2.js`, `refresh_theoldllm_token.js` | `oldllm_*` via `https://llm.zhuguang.ccwu.cc` | Public `/v1/models` OK; local chat timed out after 30s; refresh scripts no longer print raw token values | Diagnose upstream timeout before placing in hot path |
| StockAI worker | Public `https://stock.zhuguang.ccwu.cc/v1/models` returns model list | `stock_*` | Registered, but prior smoke found `stock_kimi_k2` invalid/empty | Keep late fallback only; re-smoke model by model |
| HeckAI worker draft | `D:\ollama_server\heckai-worker.js` targets `api.heckai.weight-wave.com/api/ha/v1` | Not registered | Reverse draft exists but no local port or LiMa backend | Treat as adapter draft; deploy only in sandbox after harmless chat smoke |
| Umint proxy draft | `D:\ollama_server\umint_proxy.js` | Not registered | Adapter draft exists; no listener found | Keep in research backlog |
| g4f wrapper | `D:\ollama_server\g4f_server.py`; port `4503` | Not directly registered | Generic provider wrapper works for default route but model/provider names are fragile | Use only as sandbox fallback after explicit provider mapping |

## Not Yet Reverse-Engineered

| Candidate | Current Evidence | State | Next Action |
|---|---|---|---|
| HIX Chat | Page reachability probe returned HTTP 200 | Not reversed | Capture harmless request flow only if it passes trust review |
| GPT.chat | Page reachability probe returned HTTP 200 | Not reversed | Low-trust; harmless probes only |
| Deep-seek mirror | Page reachability probe returned HTTP 200 | Not reversed | Verify provenance before any adapter work |
| PLAI.chat | Page reachability probe returned HTTP 200 | Not reversed | Inspect model list, limits, and protocol |
| Blackbox AI / other coding web UIs | Mentioned as future candidate class, not in local registry | Not reversed | Add only after current adapters are stabilized |

## Integration Gaps

1. DuckAI request construction is fixed locally with OpenAI `no_system`; `gpt4o-mini` and `gpt5-mini` are admitted only as late local fallback.
2. DuckAI public tunnel remains broken with Cloudflare 1033, so production/VPS use still needs tunnel repair or a different exposure path.
3. `ddg_claude_haiku_45` is useful for chat-like fallback but failed strict JSON in the admission fixture.
4. `ddg_tinfoil_gptoss_120b` is registered for completeness but should stay inactive until the upstream 500 is fixed.
5. Kimi should stay out of hot routes until session refresh makes `4504` chat pass. Current failure cools down as `manual_refresh_required`.
6. SCNet-large passed the local route-path fixture and is faster than direct SCNet, but promotion must be topology-aware so VPS `localhost:4505` is never used as a false local proxy.
7. TheOldLLM should stay late because local chat times out; refresh logs are now redacted, but refresh was not executed in this pass.
8. HeckAI should not be researched from scratch; start from the existing `heckai-worker.js` draft.

## Token-Safe Refresh Update

Date: 2026-05-22

Local refresh tooling under `D:\ollama_server` has been redacted in-place:

- `secret_redactor.js` added.
- Kimi and TheOldLLM refresh scripts now require Cloudflare API tokens from environment variables.
- Token, request-body, and localStorage logs are redacted.
- `token_refresh_server.js` reports token presence instead of returning raw token values.
- `oldllm_proxy.js` no longer embeds a request token literal.

Refresh was not executed in this pass. The next refresh attempt should set the needed environment variables and verify login/session state without printing token values.

## Next Closed-Loop Plan

Use `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md` as the execution plan after this inventory is reviewed.
