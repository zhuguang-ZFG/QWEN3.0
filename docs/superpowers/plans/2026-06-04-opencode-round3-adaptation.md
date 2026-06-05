# OpenCode Round 3 深度适配

## Goal
补齐 GPT-5/Claude Opus 4.7+/Gemini 3 等新模型的推理变体(options + reasoning_effort) + stream error 结构化解析能力，对齐 OpenCode provider 层。

## Tasks
- [x] T1: 实现 reasoning_variants — 按 provider+model 映射 reasoning_effort/thinking 层级
  → Verify: `['low', 'medium', 'high', 'max']` for scnet_ds_flash ✅
- [x] T2: 实现 session_options — 注入 store/enable_thinking/toolStreaming/usage/include 等模型级 options
  → Verify: `store=False, reasoningEffort=medium` for openai+gpt-5.1 ✅
- [x] T3: 增补 opencode_message_normalizer — DeepSeek reasoning_content 提取 + interleaved 字段处理
  → Verify: 2 parts (text+reasoning) after injection, providerOptions populated ✅
- [x] T4: 实现 parseStreamError — insufficient_quota/usage_not_included/overloaded/server_error 结构化码
  → Verify: `isRetryable=True` for server_is_overloaded ✅
- [x] T5: 增补 opencode_error_adapter — parseAPICallError 结构化 API error 解析 (statusCode/isRetryable/responseHeaders)
  → Verify: context_overflow detected from body, api_error with metadata ✅
- [x] T6: 接线到 pipeline — routing_engine.py/http_request_builder.py/http_sync.py/http_stream.py 调用新模块
  → Verify: `import` all pass, no regression in 41 existing Opencode tests ✅
- [x] T7: 更新 opencode_config.py — 新增 OPENCODE_REASONING_VARIANTS / OPENCODE_SESSION_OPTIONS 开关
  → Verify: `OPENCODE_REASONING_VARIANTS=True, OPENCODE_SESSION_OPTIONS=True` ✅
- [x] T8: 测试 — test_opencode_round3.py 覆盖 reasoning/options/stream_error/schema 新能力
  → Verify: `pytest tests/test_opencode_round3.py -v --tb=short`: 38 passed ✅
- [x] T9: ruff check + pyright type check
  → Verify: `ruff check`: all passed, 41 OpenCode existing tests no regression ✅
- [x] T10: VPS 部署 + health + smoke + pytest 全量
  → Verify: 30 files deployed, `/health` 200, 14 modules active, 4/4 module checks pass ✅

## Done When
- [x] reasoning_variants.py 覆盖 GPT-5 全系 / Grok / Anthropic adaptive / Gemini / Cerebras / TogetherAI / xAI / DeepInfra / Venice / Mistral / Groq / Perplexity / SAP AI Core
- [x] session_options.py 覆盖 store/enable_thinking/toolStreaming/usage/include 等关键 options
- [x] parseStreamError 返回结构化码 (insufficient_quota/usage_not_included/server_is_overloaded/server_error/invalid_prompt)
- [x] parseAPICallError 返回结构化字段 (overflow/statusCode/isRetryable/responseHeaders)
- [x] opencode_message_normalizer 支持 DeepSeek reasoning_content 注入
- [x] pipeline 无缝接线，原有 41 OpenCode 测试无回归
- [x] VPS 部署后 health 200, 4/4 modules verified

## Notes
- reasoning_variants 直接参考 `opencode-source/packages/opencode/src/provider/transform.ts:614-1025`
- session_options 参考 `opencode-source/packages/opencode/src/provider/transform.ts:1027-1168`
- 所需行数估算: ~900 行 (reasoning 500 + options 150 + adapter 80 + normalizer 40 + stream_error 60 + 接线 40 + config 30)
- 优先保证 reasoning 和 options 两个核心模块，其余按时间裁剪
