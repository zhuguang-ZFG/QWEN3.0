# context_pipeline

> 更新：2026-06-16
> 权威分层：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](../docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §5

**不要**把整个目录都当成聊天热路径。仅下表 **Hot** 五模块在绝大多数 `/v1/chat` 与路由决策中会同步触及；其余为 Warm（条件/后台）或 Cold（实验/离线评测）。

## Hot（生产主路径）

| 模块 | 职责 | 主要调用方 |
|------|------|------------|
| `retrieval_injection.py` | 路由前上下文注入 | `routing_engine.py`、`request_context_preflight.py` |
| `code_context_injection.py` | 编码场景 tree-sitter 扫描 | `routing_engine_context.py` |
| `skill_store.py` | 技能召回 / 结晶 | `routing_engine_context.py`、`route_post_process.py` |
| `response_validator.py` | 编码响应质量校验与重试 | `routing_engine_execute_strategy.py` |
| `routing_weights.py` | 学习环路权重持久化 | `routing_selector.py`、`routes/ops_metrics` |

## Warm（条件触及）

`auto_indexer.py`、`response_processors.py`、`response_pipeline.py`、`narrative.py`、`routing_bridge.py`、`cache.py`、`semantic_code_retrieval.py`、`event_log.py`、`guardrails.py`、`entity_extraction.py`、`production_index.py`、`retrieval_trace.py` 等——由 env、场景或后处理链触发，非每次请求必经。

## Cold（实验 / 离线）

`lab/` 子目录存放 **零生产 fan-in** 的实验工具（见 [`docs/context_pipeline_lab_CN.md`](../docs/context_pipeline_lab_CN.md)）。

根目录仍可能含 Warm lazy 模块（如 `graph_retrieval.py`、`complexity.py`）——由 env/场景触发，**不得**在 `server.py` 启动默认 import。

**已退役（CodeGraph 瘦身 + CP-1/CP-2 + CP-4 后续）**：`ensemble.py`、`concurrency_pool.py`、`index_protocol.py`、`reranker_protocol.py`、`reflection.py`、`hierarchical_memory.py`、`memory_persistence.py`、`session_memory_enhancer.py`、`artifact.py`、`evolution.py`、`signal_extraction.py`、`retrieval_eval.py`、`retrieval_eval_runner.py`、`local_retrieval/eval_bridge.py`、`lab/static_analysis.py`（`device_artifacts/` 与 `context_pipeline/artifact` 无关；`production_index` / `retrieval_corpus` 仍由 `retrieval_injection` Warm 使用）。

## 维护约定

- 修改 Hot 模块前跑：`python -m pytest tests/test_routing_pipeline_authority.py tests/test_production_retrieval.py -q`
- 新增模块默认标 Warm/Cold，并在本 README 或 `CODEBASE_SUBSYSTEM_TIER_CN.md` 登记
- 单文件目标 ≤300 行；超标 Hot 文件优先拆分
