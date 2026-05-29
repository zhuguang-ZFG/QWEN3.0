# LiMa 项目开发规范

个人编码助手后端（非商业化开放平台）。完整原则见 `AGENTS.md`。

## Superpowers 原则（摘要）

1. **文档先行**：非 trivial 改动先写设计文档（`docs/`）。
2. **文件小而专注**：单文件目标 ≤300 行；函数目标 ≤50 行。
3. **本地验证再部署**：本地测试通过后再一次性替换 VPS 文件。
4. **永不破坏生产**：可回滚；新模块独立文件，确认后再接入主路径。
5. **参考业界实践**：设计决策尽量有开源参考或实测佐证。
6. **渐进式替换**：新旧并行，小流量验证后再全量。

## 仓库规模（2026-05-25 实测）

由 `python scripts/repo_stats.py` 生成（排除 venv/deepcode-cli/esp32S_XYZ 等）：

| 指标 | 值 |
|------|-----|
| Python 文件 | 516 |
| Python 行数 | ~66,842 |
| `tests/test_*.py` | 135 |
| `routes/*.py` | 35 文件 / ~6,087 行 |
| 顶层目录数 | 40 |

### 关键入口行数

| 文件 | 行数 | 备注 |
|------|-----:|------|
| `server.py` | 124 | FastAPI 入口 + `BodySizeLimitMiddleware` |
| `routing_engine.py` | 222 | 五层统一路由 |
| `smart_router.py` | 228 | 兼容层（分类/熔断/调用） |
| `http_body_limit.py` | 236 | ASGI body 上限 |
| `routes/quality_gate.py` | ~230 | 质量门控（已拆 tier/direct 子模块） |
| `routes/chat_handler_dispatch.py` | ~318 | 非流式分发（待继续拆） |
| `backends.py` | 417 | 后端配置（待拆 registry） |
| `routes/agent_tasks.py` | ~260 | Agent 任务路由（已拆 store/service/schemas/evolution） |
| `session_memory/store.py` | facade | 会话存储（已拆 db/crud/promote/admin） |
| `agent_runtime/orchestrator.py` | facade | 编排器（已拆 queue/worker/models/io） |
| `backends.py` | ~135 | 后端 facade（registry/constants 已拆） |

> 易漂移的完整清单与 P0/P1/P2 切片见
> [`docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`](docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md)。

## 架构速览

```
server.py → routes/route_registry.py
         → routing_engine / smart_router → http_caller
         → routes/chat_* / anthropic_* / tool_forward
         → session_memory / agent_runtime / device_gateway（可选）
```

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
- httpx（逐步替换 `router_http.py` 中 urllib）
- pybreaker、SQLite（语义缓存/会话记忆）

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
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | 主线计划 |
| `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` | 代码质量 backlog |
| `findings.md` / `progress.md` | 证据与执行日志 |

## 统计刷新命令

```powershell
python scripts/repo_stats.py
```

## Milestone Collaboration Protocol

见 `AGENTS.md`：Owner 实现 → Agent 审查/修复/全量测试 → 更新 progress/findings → 仅 stage 相关文件 → commit → push → 下一里程碑计划。

全局 closeout 默认包含：本地门禁通过、VPS 自动部署与 health/smoke 验证、失败时记录调试和 rollback 证据、仅 stage 本轮相关文件、无凭据检查后提交，并优先上传 GitHub (`origin`) 再同步 Gitee。完整硬规则以 `AGENTS.md` 的“自动部署、VPS 验证调试与 GitHub 上传（项目全局）”为准。
