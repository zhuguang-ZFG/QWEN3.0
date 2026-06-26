# P4-3 后续：Instructor 意图回退结构化输出设计

> 状态：设计文档待审阅
> 相关计划：`docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 步骤 P4-3
> 作者：Kimi Code
> 日期：2026-06-27

## 1. 背景

P4-3 基座已完成：

- `models/structured_outputs/schemas.py` 定义了 `ClassifyResult`、`ScenarioResult`、`IntentResult`、`BackendScore`。
- `models/structured_outputs/validator.py` 提供运行时校验与安全回退。
- `models/structured_outputs/instructor_client.py` 已预留 Instructor patch，但尚未接入任何生产路径。
- `routing_intent.py::analyze_intent()` 目前完全基于规则/信号启发式，对边界 query 容易落入 `default_fallback`（confidence=0.5）。

本设计选择 **最小侵入、可回滚** 的方式，把 Instructor 结构化输出能力接入意图分析链路。

## 2. 目标

- 在规则分类置信度不足时，可选地通过 Instructor 调用一次小模型，返回符合 `IntentResult` 的结构化结果。
- 默认关闭；开启前不影响现有性能与成本。
- 任何失败（依赖缺失、无 key、超时、格式错误）都记录 warning 并回退到规则结果，不阻塞请求。

## 3. 方案对比

| 方案 | 范围 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| A. 意图回退 | `routing_intent.py` | 改动最小；直接复用现有 `IntentResult`；仅对低置信度 query 触发 | 仅覆盖意图分析 | **推荐** |
| B. 请求类型 LLM 化 | `routing_classifier.py` | 与 v3 方案字面一致 | 当前分类器已是确定性规则，改 LLM 会增加所有请求延迟/成本，收益不明确 | 不推荐 |
| C. 复杂度评估 LLM 化 | `speculative_policy.py` | 可能改善投机执行池选择 | 投机路径对延迟敏感，LLM 调用与目标冲突 | 不推荐 |

## 4. 推荐方案 A 详细设计

### 4.1 触发条件

在 `routing_intent.py` 的 `analyze_intent()` 中：

1. 先执行现有规则/信号分类，得到 `result`。
2. 若 `LIMA_INSTRUCTOR_INTENT_ENABLED=1` 且 `result["confidence"] < LIMA_INSTRUCTOR_INTENT_THRESHOLD`（默认 `0.70`），则进入 Instructor 回退。
3. 否则直接返回规则结果。

### 4.2 Instructor 客户端扩展

扩展 `models/structured_outputs/instructor_client.py`，新增：

```python
def create_structured_completion(
    messages: list[dict],
    response_model: type[T],
    *,
    provider: str = "groq",
    model: str = "llama-3.1-8b-instant",
    max_retries: int = 2,
    timeout: float = 10.0,
) -> T | None:
    """Use Instructor to get a structured output from a small backend."""
```

实现要点：

- 通过 `key_pool.get_key(provider)` 获取可用 key；无 key 返回 `None`。
- 根据 provider 选择 base_url：
  - `groq` → `https://api.groq.com/openai/v1`
  - `openrouter` → `https://openrouter.ai/api/v1`
  - `cerebras` → `https://api.cerebras.ai/v1`
- 构造 `openai.OpenAI(base_url=..., api_key=key, timeout=timeout)`。
- 使用 `instructor.from_openai()` patch；若 `instructor` 未安装，返回 `None`。
- 调用 `client.chat.completions.create(..., response_model=response_model, max_retries=max_retries)`。
- 所有异常捕获并记录 warning，返回 `None`。

### 4.3 Prompt 设计

系统提示要求模型按 `IntentResult` schema 输出 JSON，并给出字段含义：

```text
You are an intent classifier for an AI assistant. Analyze the user query and output a JSON object matching this schema:
- intent: one of [chat, code_generation, debugging, explanation, hardware, image_gen, device_draw, device_write, device_control, thinking, trivial, architecture, tool_task, grbl_config, cnc_trouble, embedded_dev, general_cnc, complex_theory]
- confidence: float 0.0-1.0
- complexity: float 0.0-1.0
- needs_code: boolean
- domain_keywords: list of relevant keywords
- cnc_subdomain: "grbl" or "general"
- entities: dict of detected entities
```

用户消息仅包含原始 query。

### 4.4 回退与合并策略

- Instructor 返回 `None`：使用规则结果。
- Instructor 返回 `IntentResult`：
  - 若 `confidence >= threshold`，直接采用。
  - 否则与规则结果比较 confidence，取高者。
- 始终通过 `validate_value()` 再次校验，保持与现有路径一致。

### 4.5 配置项

在 `.env.example` 中增加：

```bash
# Instructor 意图回退（默认关闭）
LIMA_INSTRUCTOR_INTENT_ENABLED=0
LIMA_INSTRUCTOR_INTENT_THRESHOLD=0.70
LIMA_INSTRUCTOR_INTENT_PROVIDER=groq
LIMA_INSTRUCTOR_INTENT_MODEL=llama-3.1-8b-instant
LIMA_INSTRUCTOR_INTENT_TIMEOUT=10
LIMA_INSTRUCTOR_INTENT_MAX_RETRIES=2
```

在 `config/env.py` 增加读取函数（若该文件负责环境变量）。

### 4.6 可观测性

新增 Prometheus 计数器：

- `instructor_intent_calls_total{provider, model}`
- `instructor_intent_failures_total{provider, model, reason}`
- `instructor_intent_fallback_used_total`（规则结果采用次数）

### 4.7 测试策略

- 单元测试 `tests/test_instructor_intent_fallback.py`：
  - 关闭时规则结果直接通过。
  - 低置信度 + mock `create_structured_completion` 返回 `IntentResult`。
  - Instructor 失败时回退到规则结果。
  - 未安装 instructor 时优雅回退。
- 聚焦测试：`tests/test_routing_intent.py` + `tests/test_route_pipeline.py` 回归通过。

## 5. 数据流

```text
analyze_intent(query)
  ├─ 规则/信号分类 → result + confidence
  ├─ confidence < threshold 且 enabled?
  │    └─ instructor_client.create_structured_completion(messages, IntentResult)
  │         ├─ 成功 → validated IntentResult
  │         └─ 失败 → warning，保持规则结果
  └─ validate_value(result, IntentResult) → dict
```

## 6. 验收标准

- [ ] `models/structured_outputs/instructor_client.py` 提供 `create_structured_completion`。
- [ ] `routing_intent.py` 在规则置信度低时可调用 Instructor，默认关闭。
- [ ] 失败时记录 warning 并回退，无静默降级。
- [ ] `.env.example` 与 `config/env.py` 增加配置项。
- [ ] 新增 ≥5 个单元测试覆盖开关/成功/失败/阈值/未安装依赖。
- [ ] 聚焦测试 + 全量 pytest 通过；`ruff` / `pyright` / `check_code_size` 通过。
- [ ] 灰度开启后观测到 `instructor_intent_*` 指标。

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Instructor 依赖未安装 | 运行时 `try/except ImportError`，返回 `None`，记录 warning |
| 小模型输出不符合 schema | Instructor `max_retries` + 最终 `validate_value()` 兜底 |
| 增加请求延迟 | 仅低置信度触发；配置超时 10s；默认关闭 |
| key 池耗尽 | `key_pool.get_key` 返回 `None` 时直接回退 |
| 成本不可控 | 仅对少数边界 query 调用；可通过指标观察调用量 |
