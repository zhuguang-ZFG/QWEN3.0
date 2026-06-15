# LiMa 项目开发规范

**战略转型完成**：LiMa 从"个人编码助手后端" → "AI 智能设备统一云端服务"（2026-06-09 启动，阶段 1 设备路由契约已关闭）

AI 绘图机/写字机等智能硬件的云端服务（非商业化开放平台）。完整原则见 `AGENTS.md`。

## Superpowers 原则（摘要）

1. **文档先行**：非 trivial 改动先写设计文档（`docs/`）。
2. **文件小而专注**：单文件目标 ≤300 行；函数目标 ≤50 行。
3. **本地验证再部署**：本地测试通过后再一次性替换 VPS 文件。
4. **永不破坏生产**：可回滚；新模块独立文件，确认后再接入主路径。
5. **参考业界实践**：设计决策尽量有开源参考或实测佐证。
6. **渐进式替换**：新旧并行，小流量验证后再全量。
7. **文档必须中文**：新增或更新文档类产物时默认使用中文；代码标识、命令、API 字段、路径、日志片段和外部专有名词可保留英文。

## 仓库规模（2026-06-15 更新 - 排除 `.venv*` 与 `esp32S_XYZ` 子模块）

由 `python scripts/repo_stats.py` 生成：

| 指标 | 值 |
|------|-----|
| Python 文件 | 805 |
| Python 行数 | ~98,768 |
| `tests/test_*.py` | 231 |
| `routes/*.py` | 43 文件 / ~6,047 行 |
| 顶层目录数 | 50 |

### 关键入口行数

| 文件 | 行数 | 备注 |
|------|-----:|------|
| `server.py` | 124 | FastAPI 入口 |
| `routing_engine.py` | 165 | 五层统一路由（精简后） |
| `routing_intent.py` | 312 | 意图分析（承接已退役 router_classifier） |
| `http_body_limit.py` | 247 | ASGI body 上限 |
| `routes/chat_handler_dispatch.py` | 248 | 非流式分发 |
| `backends.py` | 41 | 后端配置 facade（已拆分为 backends_registry + backends_constants + backend_utils） |
| `backends_registry.py` | 244 | 后端注册表（权威来源） |
| `session_memory/store.py` | 51 | 会话存储 facade |

> 易漂移的完整清单与 P0/P1/P2 切片见
> [`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md)。

## 架构速览

```
server.py → routes/route_registry.py
         → routing_engine.py → routing_intent (意图分析)
                            → routing_classifier (场景分类)
                            → routing_selector (后端排序)
                            → routing_executor (执行+熔断)
                            → http_caller (HTTP 传输)
         → routes/chat_* / device_gateway
         → device_intelligence/ (设备规划/模拟)
         → device_policy/ (策略引擎)
         → device_workflow/ (任务工作流)
         → xiaozhi_drawing/ (绘画引擎)
         → session_memory/ (设备上下文记忆)
```

**已删除模块**（全部已退役）：

| 模块 | 删除时间 | 原因 |
|------|---------|------|
| `agent_runtime/` | Phase 0 (06-09) | 编码助手运行时，已退役 |
| `semantic_cache/` | Phase 0 (06-09) | 语义缓存，已退役 |
| `smart_router.py` | C9 (06-13) | Legacy facade，由 routing_engine 替代 |
| `router_http*.py` | C9 (06-13) | Legacy urllib，由 http_caller 替代 |
| `router_circuit_breaker.py` | C9 (06-13) | 由 health_tracker 替代 |
| `router_classifier.py` | C10 (06-13) | 由 routing_intent.py 替代 |
| `router_local.py` | C10 (06-13) | 编排入口已迁移到 routing_intent |
| `routes/quality_gate.py` | C9 (06-13) | 临时 stub，已移除 |
| `routes/anthropic_messages_handler.py` | C9 (06-13) | 临时 stub，已移除 |
| `routes/anthropic_vision_sse.py` | C9 (06-13) | 临时 stub，已移除 |
| `routes/anthropic_stream.py` | Phase 0 (06-09) | Anthropic 流式，已退役 |
| `routes/tool_forward.py` + `tool_forward_stream.py` | Phase 0 (06-09) | 工具转发，已退役 |
| `routes/quality_gate_tiers.py` + `quality_gate_direct.py` | Phase 0 (06-09) | 质量门控子模块，已退役 |
| `auto_distill_main.py` + `distill_scheduler.py` + `auto_trainer.py` | 06-13 | 无人引用的自训练子系统 |

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
- SQLite（设备状态、任务队列、用户数据、语义缓存）
- Redis（设备任务队列）
- OpenCV（图像矢量化）
- dashscope（AI 图像生成）

## 代码质量红线

- **禁止降级处理**：所有功能必须在正确配置下运行，不允许静默降级或跳过（详见 AGENTS.md Superpowers 原则 #0）
- 禁止裸 `except Exception: pass`（至少 `logger.warning` + 类型名）
- 禁止在生产路径硬编码密钥
- 新模块超过 300 行必须拆分
- 可选子系统：`ImportError` 时 `logger.debug` 说明未安装，勿静默吞掉未知异常
- `.env` 必须设置 `LIMA_API_KEY`，否则启动报错

## 关键文档

| 文档 | 内容 |
|------|------|
| `STATUS.md` | 当前项目状态（必读） |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 活跃路线图与阶段目标（必读） |
| `docs/LIMA_MEMORY_CN.md` | 长期记忆 |
| `docs/ARCHITECTURE.md` | 系统架构与模块边界 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 请求处理管线权威说明 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署与发布硬规则 |
| `findings.md` / `progress.md` | 证据与执行日志 |

## 统计刷新命令

```powershell
python scripts/repo_stats.py
```

## Milestone Collaboration Protocol

见 `AGENTS.md`：Owner 实现 → Agent 审查/修复/全量测试 → 更新 progress/findings → 仅 stage 相关文件 → commit → push → 下一里程碑计划。

全局 closeout 默认包含：本地门禁通过、VPS 自动部署与 health/smoke 验证、失败时记录调试和 rollback 证据、仅 stage 本轮相关文件、无凭据检查后提交，并优先上传 GitHub (`origin`) 再同步 Gitee。完整硬规则以 `AGENTS.md` 的“自动部署、VPS 验证调试与 GitHub 上传（项目全局）”为准。

## CodeGraph 代码智能（本仓库首选，不用 GitNexus）

本仓库以 **CodeGraph** 为权威代码图工具（MCP + CLI），索引位于 `.codegraph/codegraph.db`。GitNexus 自动注入块已移除；勿在本仓启用 `gitnexus_*` MCP 或 `npx gitnexus analyze`。

### 常用命令

```powershell
codegraph index .          # 首次建索引
codegraph sync .           # 拉代码或大改后同步
codegraph status           # 检查索引新鲜度
codegraph impact <symbol>  # 改动前看调用方
python scripts/codegraph_orphans.py --fanin   # 删模块前：图 + ripgrep 交叉
```

### 装机脚本

| 场景 | 命令 |
|------|------|
| 多 Agent 写入 codegraph MCP | `pwsh -File scripts/setup_codegraph_agents.ps1` |
| LiMa 推荐 MCP 包（含 codegraph） | `pwsh -File scripts/setup_lima_mcps.ps1` |

详见 `.agents/PROJECT_MAP.md` 与 `progress.md`（2026-06-15 CodeGraph 瘦身记录）。
