# LiMa 项目开发规范

**⚠️ 战略转型中**：LiMa 从"个人编码助手后端" → "AI 智能设备统一云端服务"（2026-06-09 启动）

AI 绘图机/写字机等智能硬件的云端服务（非商业化开放平台）。完整原则见 `AGENTS.md`。

## Superpowers 原则（摘要）

1. **文档先行**：非 trivial 改动先写设计文档（`docs/`）。
2. **文件小而专注**：单文件目标 ≤300 行；函数目标 ≤50 行。
3. **本地验证再部署**：本地测试通过后再一次性替换 VPS 文件。
4. **永不破坏生产**：可回滚；新模块独立文件，确认后再接入主路径。
5. **参考业界实践**：设计决策尽量有开源参考或实测佐证。
6. **渐进式替换**：新旧并行，小流量验证后再全量。

## 仓库规模（2026-06-09 更新 - Phase 0 精简后）

由 `python scripts/repo_stats.py` 生成：

| 指标 | 值 |
|------|-----|
| Python 文件 | 5,103 |
| Python 行数 | ~1,926,992 |
| `tests/test_*.py` | 201 |
| `routes/*.py` | 43 文件 / ~6,680 行 |
| 顶层目录数 | 47 |

### 关键入口行数

| 文件 | 行数 | 备注 |
|------|-----:|------|
| `server.py` | 128 | FastAPI 入口 |
| `routing_engine.py` | 328 | 五层统一路由（已移除 semantic_cache） |
| `smart_router.py` | 241 | 兼容层（分类/熔断/调用） |
| `http_body_limit.py` | 247 | ASGI body 上限 |
| `routes/quality_gate.py` | 89 | **临时 stub**（Phase 2 移除） |
| `routes/chat_handler_dispatch.py` | 338 | 非流式分发 |
| `backends.py` | 136 | 后端配置 facade |
| `session_memory/store.py` | 51 | 会话存储 facade |

> 易漂移的完整清单与 P0/P1/P2 切片见
> [`docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`](docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md)。

## 架构速览（战略转型后）

```
server.py → routes/route_registry.py
         → routing_engine → device_llm_router (简化)
         → routes/chat_* / device_gateway
         → xiaozhi_device/ (设备管理)
         → xiaozhi_drawing/ (绘画引擎)
         → session_memory/ (简化为设备上下文)
```

**已删除模块**（Phase 0 完成）：
- `agent_runtime/` (编码助手运行时) ✅
- `semantic_cache/` (语义缓存) ✅
- `routes/anthropic_stream.py` (Anthropic 流式) ✅
- `routes/tool_forward.py` + `tool_forward_stream.py` (工具转发) ✅
- `routes/quality_gate_tiers.py` + `quality_gate_direct.py` (质量门控子模块) ✅

**临时 Stub**（Phase 2 移除）：
- `routes/quality_gate.py` (89 行简化实现)
- `routes/anthropic_messages_handler.py` (75 行 stub)
- `routes/anthropic_vision_sse.py` (33 行 stub)

详见 `docs/superpowers/plans/2026-06-09-code-simplification-verification.md`

## 开发流程

```text
1. 设计文档 (docs/*.md)
2. 本地编码 (D:/GIT)
3. pytest
4. VPS 部署 + health/smoke 验证（详见 docs/DEPLOY_AND_RELEASE_CONVENTION.md）
5. 更新 STATUS.md / progress.md / findings.md
6. git commit（仅里程碑相关文件）→ push origin → push gitee
```

## 技术栈

- Python 3.10 + FastAPI + uvicorn
- httpx（异步 HTTP 调用）
- SQLite（设备状态、任务队列、用户数据）
- **新增（Phase 1）**：svgpathtools, shapely, pypotrace, dashscope, Pillow

## 代码质量红线

- **禁止降级处理**：所有功能必须在正确配置下运行，不允许静默降级或跳过（详见 AGENTS.md Superpowers 原则 #0）
- 禁止裸 `except Exception: pass`（至少 `logger.warning` + 类型名）
- 禁止在生产路径硬编码密钥
- 新模块超过 300 行必须拆分
- 可选子系统：`ImportError` 时 `logger.debug` 说明未安装，勿静默吞掉未知异常
- `.env` 必须设置 `LIMA_API_KEY`，否则启动报错

### 近期已关闭（CQ-085）

- ASGI body 分块上限、`/api/live-key` 不返回原始密钥、`key_rotation` 退役
- semantic cache 写库失败可观测、admin 登录常量时间比较

### 已关闭（CQ-097）

- ~~略超 300 行~~：`orchestrator_queue.py` 已拆分/移除；`routes/agent_tasks.py` 已降至 ~260 行
- 路由权威边界：`docs/REQUEST_PIPELINE_AUTHORITY.md` 已更新，含 18 步管线图 + 21 模块所有权表

## 关键文档

| 文档 | 内容 |
|------|------|
| `STATUS.md` | 项目状态 |
| `docs/LIMA_MEMORY.md` | 长期记忆 |
| `task_plan.md` | 当前任务计划 |
| `docs/superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md` | 战略转型计划 |
| `docs/superpowers/plans/2026-06-09-phase0-strategic-confirmation.md` | Phase 0 启动文档 |
| `findings.md` / `progress.md` | 证据与执行日志 |

## 统计刷新命令

```powershell
python scripts/repo_stats.py
```

## Milestone Collaboration Protocol

见 `AGENTS.md`：Owner 实现 → Agent 审查/修复/全量测试 → 更新 progress/findings → 仅 stage 相关文件 → commit → push → 下一里程碑计划。

全局 closeout 默认包含：本地门禁通过、VPS 自动部署与 health/smoke 验证、失败时记录调试和 rollback 证据、仅 stage 本轮相关文件、无凭据检查后提交，并优先上传 GitHub (`origin`) 再同步 Gitee。完整硬规则以 `AGENTS.md` 的“自动部署、VPS 验证调试与 GitHub 上传（项目全局）”为准。
