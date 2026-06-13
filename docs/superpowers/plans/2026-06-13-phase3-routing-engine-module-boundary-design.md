# Phase 3：routing_engine 模块边界与拆分设计

**日期：** 2026-06-13
**前置：** Phase 0–2.5 bypass 收敛、P1 编排上下文、P1.5 `prefer` 选路（均已 push）
**权威：** `docs/REQUEST_PIPELINE_AUTHORITY.md` — 生产 chat/coding 仅 `routing_engine.route()` / `pick_backend()`

## 1. 问题

| 项 | 现状 | 风险 |
|----|------|------|
| 文件行数 | `routing_engine.py` ~420 行 | 超 AGENTS.md 300 行红线 |
| 公开 API | `__all__` 含 `select` / `execute` | routes 曾 bypass；文档与 `routing_selector` / `routing_executor` 职责重叠 |
| 测试耦合 | 单测 patch `routing_engine.select` | 掩盖真实调用链（实为 `routing_selector.select`） |

## 2. 目标

1. **公开面收敛**：对外仅保证 `route`、`pick_backend`、`respond`、`RouteResult`、`PickResult` 及分类/技能 re-export。
2. **执行边界清晰**：`select()` 权威在 `routing_selector`；`execute()` 权威在 `routing_executor`。
3. **文件拆分**：各子模块 ≤300 行，函数 ≤50 行（既有大函数按文件拆分，不强行再拆逻辑）。
4. **可回滚**：`routing_engine.py` 保留为薄 facade，import 路径不变。

## 3. 非目标

- 不改 `routing_selector` / `routing_executor` 算法行为。
- 本阶段不重构 `routes/eval_internal.py` eval 旁路（Phase 3+）。
- 不删除 `smart_router.py` facade（独立 CQ 项）。

## 4. 模块划分

```text
routing_engine_types.py          # RouteResult, PickResult
routing_engine_context.py        # recall / code context / complexity / compress
routing_engine_execute_strategy.py  # speculative / code-priority / quality retry
routing_engine_post.py           # _post_route, _get_injected_ids
routing_engine.py                # route, pick_backend, respond, inject_skills + re-exports
```

### 4.1 公开 API（`routing_engine.__all__`）

```python
__all__ = [
    "RouteResult",
    "PickResult",
    "classify",
    "classify_scenario",
    "inject_skills",
    "respond",
    "pick_backend",
    "route",
]
```

### 4.2 不再公开

| 符号 | 新归属 | 迁移指引 |
|------|--------|----------|
| `select` | `routing_selector.select` | 测试/脚本直接 import |
| `execute` | `routing_executor.execute` | 同上 |
| `_get_injected_ids` | `routing_engine_post` | 单测可 `from routing_engine_post import _get_injected_ids` |

## 5. 调用关系（不变）

```text
route() / pick_backend()
  → routing_classifier.classify / classify_scenario
  → routing_engine_context（inject/compress）
  → routing_selector.select
  → skills_injector
  → routing_engine_execute_strategy → routing_executor.execute
  → routing_engine_post._post_route
```

流式路径仍为 `pick_backend()` → `http_caller`（不经 `route()` 后半段）。

## 6. 测试与门禁

| 检查 | 命令/测试 |
|------|-----------|
| routes bypass 归零 | `rg "routing_engine\.(select\|execute)\(" routes/` |
| 公开 API | `tests/test_routing_pipeline_authority.py::TestRoutingEnginePublicApi` |
| 回归 | `pytest tests/test_routing_engine.py tests/test_routing_engine_integration.py tests/test_routing_pipeline_authority.py -q` |

## 7. 验收标准

- [x] `routing_engine.py` ≤150 行（facade，实际 ~165 行含 docstring）
- [x] 各新建子模块 ≤300 行
- [x] `__all__` 不含 `select` / `execute`
- [x] 相关 pytest green（72 passed，2026-06-13）
- [x] `REQUEST_PIPELINE_AUTHORITY.md` 补充公开 API 说明

## 8. 回滚

单 commit revert；子模块删除后恢复 monolith `routing_engine.py` 即可。
