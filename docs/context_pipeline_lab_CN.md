# context_pipeline/lab 冷模块搬迁说明

> 版本：2026-06-16
> 关联：[`CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](CODEBASE_COLD_PRUNE_PRIORITY_CN.md) CP-4

## 目的

将 **零生产 fan-in**、仅测试或离线工具使用的 `context_pipeline` 模块迁入 `context_pipeline/lab/`，使根目录文件集更接近 Hot/Warm 生产面，降低新人误判「整包都在热路径」的风险。

## 不变量

1. **`server.py` / `server_lifespan` 不得** import `context_pipeline.lab`。
2. **Hot 五模块**（`retrieval_injection`、`code_context_injection`、`skill_store`、`response_validator`、`routing_weights`）**保留在根目录**，禁止迁入 lab。
3. Warm 模块（含 lazy import：`retrieval_trace`、`graph_context_expander`、`complexity` 等）**暂不搬迁**；搬迁前须 `codegraph_orphans.py --fanin` + 人工核对 lazy 引用。
4. lab 内模块可依赖标准库与仓库内其他 Cold 工具；**禁止**反向被 Hot 模块在模块顶层 import。

## CP-4 首批（2026-06-16）

| 模块 | 原路径 | 证据 |
|------|--------|------|
| `static_analysis.py` | `context_pipeline/static_analysis.py` → `lab/static_analysis.py` | 仅 `tests/test_static_analysis.py`；`LIMA_STATIC_ANALYSIS=1` 可选工具链 |

## 回归门禁

```powershell
python -m pytest tests/test_static_analysis.py tests/test_retrieval_injection.py tests/test_routing_engine.py -q
ruff check context_pipeline/lab tests/test_static_analysis.py
```

## 后续候选（未执行）

需逐文件 fan-in + lazy 审计后再迁：

- 无其他 **纯 TEST-ONLY** 根目录文件（截至 CP-4 审计）；`complexity.py` 等仍有 Warm lazy 生产引用。
