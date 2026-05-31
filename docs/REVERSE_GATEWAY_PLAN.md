# Reverse Gateway Plan

LiMa production routing must not depend on the Windows host, FRP, or ad-hoc local proxy ports. Browser/reverse-engineered providers are managed as isolated VPS sidecars and remain disabled until they have health, auth, and eval evidence.

## Goals

- Keep default LiMa backend pools fully VPS/cloud independent.
- Track reverse providers separately from normal API providers.
- Require explicit opt-in plus green health before any reverse provider can be called.
- Classify auth, quota, captcha, upstream, network, timeout, and protocol failures.
- Promote only after smoke and eval evidence; failed providers auto-demote.

## Initial Backend Policy

| Backend family | Former port | Status | Reason |
| --- | ---: | --- | --- |
| Duck/desktop web reverse | 4500 | disabled_no_adapter | Windows/local proxy only. |
| Kimi web reverse | 4504 | disabled_no_adapter | Auth/quota state unknown. |
| SCNet large web reverse | 4505 | ready_protocol_adapter when explicitly configured | VPS sidecar uses SCNet Web Chat protocol template and private cookies; still outside main pools until smoke/eval pass. |
| LongCat web reverse | 4506 | disabled_no_adapter | Web proxy source unavailable. |
| MiMo web reverse | 4507 | disabled_no_adapter | Needs VPS browser/cookie sidecar. |
| Ollama/local models | 11434 | disabled_local_host | Local GPU host dependency. |
| OldLLM reverse | public tunnel | disabled_host_dependent | External reverse service not production-owned. |

## Promotion Flow

1. Implement a provider adapter under `reverse_gateway/providers/`.
2. Run sidecar on VPS bound to `127.0.0.1:<port>` only.
3. Register health probe, auth freshness, rate limit, and error classifier.
4. Keep backend outside default `router_v3.POOLS` and `code_orchestrator_context.POOLS`.
5. Run smoke and eval; only then change admission from `disabled_no_adapter` to `sandbox_only`.
6. Promote to `code_floor_candidate` or `code_medium_candidate` only after stable eval evidence.

## SCNet Trial Shape

SCNet Web Chat is served from `https://www.scnet.cn/ui/chatbot/`; frontend analysis shows the effective backend prefix is `/acx`, and the confirmed chat endpoint is `/acx/chatbot/v1/chat/completion`. The sidecar maps OpenAI-compatible requests to a private protocol template, injects private cookie state, normalizes responses, and reports unhealthy unless the adapter, protocol, and cookie state are all present.

The protocol template supports transcript fields, default online search, optional `tools`/`mcpServers` placeholders, and a gated file bridge for large prompts. Direct Web Chat `content` rejects well below 1M, so `SCNET_REVERSE_ENABLE_FILE_CONTEXT=1` uploads medium input as ordered `textFile` OSS attachment chunks before sending. Browser/XHR smoke confirms uploaded text files are read by the model, but current SCNet Web Chat rejects raw 1M total attachment text; 1M-scale coding use must be implemented through retrieval/MCP chunk selection instead of raw pass-through. Actual tool execution is still gated on SCNet-side MCP configuration and eval evidence.
