# DREAM_MODE 文档勘误与未解谜题（2026-06-16）

> 针对 `DREAM_MODE_SUBSYSTEM_ANALYSIS_CN.md`、`DREAM_MODE_ALL_SUBSYSTEMS_CN.md`、`DREAM_MODE_PROMPT_ENGINEERING_CN.md` 的事实校正。
> 做梦模式产出为**架构隐喻草稿**，非 SSOT；权威状态见 [`STATUS.md`](../STATUS.md)、[`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md)。

## 1. 文档分工（解决重复/目录漂移）

| 文件 | 应读范围 | 问题（已修） |
|------|----------|--------------|
| `DREAM_MODE_SUBSYSTEM_ANALYSIS_CN.md` | 子系统 **1–9** 深度隐喻 | 目录曾列出 10–15 但正文缺失 → 已改指向补充文档 |
| `DREAM_MODE_ALL_SUBSYSTEMS_CN.md` | 子系统 **10–15**（及 1–6 另一视角） | 与主文档编号重叠 → 以本表为准 |
| `DREAM_MODE_PROMPT_ENGINEERING_CN.md` | Prompt + Skills Injector 细节 | Layer 3 实现路径需与代码对齐 |

## 2. 战略定位勘误

| 做梦模式表述 | 当前事实（2026-06-09 转型后） |
|--------------|-------------------------------|
| 「智能编程助手」单一叙事 | **主轨**：AI 绘图/写字设备云端；**副轨**：OpenAI 兼容聊天/编码 API 仍在线 |
| Context Pipeline = 前额叶唯一核心 | 设备热路径核心是 `device_gateway` + `route_policy`；`context_pipeline` 仅 **Hot 五文件**在聊天路由主链 |
| Channel Gateway 含 Telegram | **Telegram 已退役**（AGENTS.md）；渠道示例勿再写 telegram |
| draw_generated 走 render_text_task | **已修正（2026-06-18）**：自然语言经 `task_draw_params` → `handle_device_draw`；见 `DREAM_MODE_FIRMWARE_SERVER_INTERACTION_CN.md` 流程图 |

## 3. CP-1 / CP-2 已退役模块（勿再写入架构图）

以下在做梦模式 Layer 图中出现，**已于 2026-06-16 删除**：

| 模块 | 原描述位置 | 现状 |
|------|------------|------|
| `evolution.py` / `signal_extraction.py` | Routing Layer 6；Context Layer 4 | 已删；`routing_selector` 无进化重排 |
| `reflection.py` | Context Layer 3 精炼 | 已删 |
| `hierarchical_memory.py` / `memory_persistence.py` | Context Layer 4；Routing memory_boost | 已删 |
| `retrieval_eval*.py` | 离线评测 | 已删 |

**仍有效（Warm/Hot）**：`routing_weights`、`skill_store`、`entity_extraction`、`graph_retrieval`、`production_index`、`complexity`（lazy）。

## 4. Routing Selector 现行分层（替代做梦模式七层图）

```
池选择 (router_v3) → 退役过滤 → 工具能力 → 预算 → routing_guard 隔离
→ 多维评分 (健康/延迟/权重/ML/编码质量) → 排序与冷却过滤
→ sticky / preferred / recalled 绑定
```

已移除：进化策略层、hierarchical_memory 1.15 加成。

## 5. 模块规模校正（`scripts/repo_stats.py` 2026-06-16）

| 子系统 | 做梦模式约数 | 当前约数 | 备注 |
|--------|--------------|----------|------|
| context_pipeline | 38 文件 | ~33 py（CP-1/2 后） | 仅 5 个 Hot |
| device_gateway | 32 | 见仓库 | 设备主轨 |
| session_memory | 19 | 见仓库 | 聊天/学习副轨 |
| Python 总行 | — | ~93k（排除 .venv*） | 非百万行 |

## 6. Prompt Engineering 代码对齐

| 文档声称 | 代码事实 |
|----------|----------|
| Layer 3 = `skills_injector` + `code_context` | `build_*` 在 `prompt_engineering/layers.py`；**skills 注入**在 `skills_injector.py`（路由内）；**代码上下文**在 `context_pipeline/code_context_injection.py` |
| 仅 coding/chat/vision 角色 | **缺口**：无 `device_draw` / `device_write` 专用 ROLE_MAP（设备侧走 `device_gateway/model_routing.py`） |

## 7. 未解谜题（待路线图关闭）

1. **设备 Prompt 层**：是否在 `prompt_engineering/` 增加 device 场景角色，或坚持 device 仅 route_policy 不经聊天 prompt 栈？
2. **Context Pipeline 继续瘦身**：`production_index` / `graph_retrieval` 能否与设备路径完全解耦（CP-4 `lab/` 搬迁）？
3. **provider_automation 与设备准入**：`docs/model_admission/` 8 角色评测 vs `provider_automation` 聊天后端探测 — 双轨证据如何统一索引？
4. **Channel Gateway 去留**：G3/渠道是否仍活跃产品面，或标 Cold 仅保留 store？
5. **做梦模式隐喻文档**：是否迁入 `docs/archive/` 仅留本勘误表 + `ARCHITECTURE.md` 为 SSOT？

## 8. 验证命令

```powershell
python scripts/codegraph_orphans.py --fanin
python -m pytest tests/test_provider_automation_admission.py tests/test_routing_engine.py tests/test_device_gateway_model_routing.py -q
```
