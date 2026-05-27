# Cloudflare Model Inventory

Updated: 2026-05-22

## Current Integration

LiMa uses Cloudflare AI through two paths.

### Direct Account API

These backends call:

`https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions`

They require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN` in the process environment.

| Backend | Model | Current role |
|---|---|---|
| `cf_llama70b` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | chat/IDE strong |
| `cf_llama4` | `@cf/meta/llama-4-scout-17b-16e-instruct` | chat/IDE medium |
| `cf_qwen_coder` | `@cf/qwen/qwen2.5-coder-32b-instruct` | code/IDE/chat strong |
| `cf_mistral` | `@cf/mistralai/mistral-small-3.1-24b-instruct` | chat/IDE medium |
| `cf_vision` | `@cf/meta/llama-3.2-11b-vision-instruct` | registered, needs vision adapter check |
| `cf_kimi_k26` | `@cf/moonshotai/kimi-k2.6` | fallback, slow in prior evals |
| `cf_deepseek_r1` | `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` | code/chat reasoning |
| `cf_qwq` | `@cf/qwen/qwq-32b` | chat/IDE medium |
| `cf_gptoss_120b` | `@cf/openai/gpt-oss-120b` | code/chat medium |
| `cf_qwen3_30b` | `@cf/qwen/qwen3-30b-a3b-fp8` | code/chat medium |
| `cf_nemotron` | `@cf/nvidia/nemotron-3-120b-a12b` | chat/IDE medium |
| `cf_glm47` | `@cf/zai-org/glm-4.7-flash` | chat/IDE medium |
| `cf_gemma4` | `@cf/google/gemma-4-26b-a4b-it` | chat/IDE medium |

### Worker Wrapper

These backends call the zero-key OpenAI-compatible Worker wrapper:

`https://ai.zhuguang.ccwu.cc/v1/chat/completions`

Verified on 2026-05-22:

- `/v1/models` returns the Worker model list.
- `qwen2.5-coder-32b` completion returned `cfai-ok`.
- VPS deployed runtime direct call to `cf_qwen_coder` returned `cf-direct-ok`.
- VPS deployed runtime Worker call to `cfai_qwen_coder` returned `cfai-ok`.

| Backend | Worker model | Current role |
|---|---|---|
| `cfai_llama70b` | `llama-3.3-70b` | chat/code fallback |
| `cfai_llama4` | `llama-4-scout` | chat/code fallback |
| `cfai_qwen_coder` | `qwen2.5-coder-32b` | code/IDE/chat strong |
| `cfai_deepseek_r1` | `deepseek-r1-32b` | code/chat reasoning |
| `cfai_mistral` | `mistral-small-3.1` | registered only; quick eval returned HTTP 500 |

## Routing Policy

- Keep SCNet coding winners first because local/VPS evals already proved them faster and stronger.
- Add Cloudflare code-capable models immediately after the first-tier winners so they enter the default fallback window.
- Keep Worker models that return HTTP 500 out of active route pools until they pass a smoke/eval.
- Use direct Cloudflare and Worker Cloudflare independently. If account credentials are unavailable, Worker capacity still helps.
- Keep `cf_kimi_k26` active but not first-tier because prior strict coding fixtures failed or were slow.

## Dashboard Model Expansion Rules

The Cloudflare dashboard includes more than chat models. LiMa should split them by adapter:

| Model type | Can use now? | Required path |
|---|---:|---|
| Text/code chat | Yes | `backends.py` + `router_v3.py` + smoke/eval |
| Vision chat | Partly | confirm message format and add to `vision` route |
| Embeddings | Not in chat route | add embeddings adapter |
| Image generation/editing | Not in chat route | add image adapter |
| Speech/ASR/TTS | Not in chat route | add audio adapter |
| Rerank/classification | Not in chat route | add task-specific adapter |

## Current Blocker

The current local shell does not expose `CLOUDFLARE_ACCOUNT_ID` or `CLOUDFLARE_TOKEN`, so direct account API smoke tests cannot run from this process without injecting those environment variables. Do not print token values when testing.

Production note: the deployed VPS runtime can call direct `cf_qwen_coder` successfully. Treat local-shell environment absence as a local test limitation, not a production outage.
