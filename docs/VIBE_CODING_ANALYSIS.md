# LiMa Vibe Coding — MiMo-Reasonix 参考分析

> 2026-06-01 · 对比 MiMo-Reasonix v0.1.1 与 LiMa 当前状态

## MiMo-Reasonix 架构速览

```
CLI (Commander + Ink TUI)
  └─ code.tsx / chat.tsx           ← 两条主命令
  └─ CacheFirstLoop                ← 核心循环（1080 行）
       ├─ ContextManager           ← 三区域上下文划分（系统/项目/本轮）
       ├─ ToolCallRepair           ← 四道修复工序
       ├─ ToolRegistry             ← 工具注册+分发
       ├─ ReadTracker              ← 读文件追踪（防幻觉编辑）
       └─ SessionStats             ← 成本/延迟统计
  └─ tools/
       ├─ filesystem.ts            ← read/write/edit/glob/grep
       ├─ shell.ts                 ← 沙箱 shell
       ├─ plan.ts                  ← 任务规划
       ├─ subagent.ts              ← 子智能体隔离
       └─ web.ts                   ← web_search/fetch
```

## 关键差距对照表

| 维度 | MiMo-Reasonix | LiMa 当前 | 差距 |
|------|-------------|----------|------|
| **CLI 入口** | `mimo-reasonix code .` 一键启动 | 无（需通过 IDE proxy） | 🔴 |
| **TUI** | Ink + React 18 终端 UI，19 种卡片 | 无 TUI | 🔴 |
| **工具调用修复** | Flatten→Scavenge→Truncation→Storm 四道 | `text_tool_extractor.py` 仅文本解析 | 🟡 |
| **编辑门控** | SEARCH 必须字节精确匹配，ReadTracker 追踪 | `agent_runtime/workspace_sandbox.py` 存在但 dry-run | 🟡 |
| **会话管理** | 持久化 session JSON，可 resume/replay/diff | SQLite 会话存储但无交互式 resume | 🟡 |
| **MCP 集成** | stdio + SSE 双传输，内置 catalog + marketplace | `lima_mcp/` 存在但未深度集成 | 🟢 |
| **成本控制** | budgetUsd 软上限，80% 警告，100% 拒绝 | `budget_manager.py` 后端级别预算 | 🟢 |
| **子智能体** | `subagent.ts` 隔离子循环，独立上下文 | `agent_runtime/` 有 queue+worker，但无隔离子循环 | 🟡 |
| **prompt 缓存** | 三区域前缀缓存 99%+ 命中率 | 无显式缓存策略 | 🟢 |
| **多语言** | i18n (zh-CN/EN/JA/DE/RU) | 无 | 🟢 |

## 可以从 MiMo-Reasonix 直接借鉴的模式

### 1. 编辑门控（最优先）

`src/code/edit-blocks.ts` 的设计：
- SEARCH 文本必须字节精确匹配文件内容 → `not-found` 拒绝编辑
- `ReadTracker` 追踪模型读过的文件 → 未读过的文件拒绝编辑
- `write_file` 计数为读操作（刚写的内容模型已知）
- fold/truncate 时清空 ReadTracker

**LiMa 对应**：`agent_runtime/workspace_sandbox.py` 可参考此模式升级。

### 2. 工具调用修复管线

```
Flatten → 展平 OpenAI tool_calls 格式（免除 DSML 清洗）
Scavenge → 从 reasoning body 中捡回遗漏的 JSON tool call
Truncation → 修复截断的 JSON 参数
Storm → 检测重复 tool call 循环并打断
```

**LiMa 对应**：`text_tool_extractor.py` 只处理文本→JSON 的解析，可扩展为完整管线。

### 3. 缓存优先循环

三区域上下文分区：
- **ImmutablePrefix** — 系统 prompt + REASONIX.md（永不改变，前缀缓存命中）
- **ProjectContext** — 项目级记忆（偶尔改变）
- **TurnMessages** — 本轮消息（频繁改变）

**LiMa 对应**：`context_pipeline/` 有层次化内存但未用于前缀缓存优化。

### 4. Ink TUI 卡片系统

19 种 UI 卡片实时展示 Agent 行为：
`ToolCard`, `DiffCard`, `PlanCard`, `ReasoningCard`, `StreamingCard`,
`ApprovalCard`, `CompactionCard`, `ErrorCard`, `UsageCard`, `SubAgentCard`...

**LiMa 对应**：Telegram bot 有基础卡片，CLI 侧完全缺失。

## 推荐执行路线（结合两个项目）

### 第 1 步：打通 CLI 入口（本周末）

```bash
# 方案 A：初始化 deepcode-cli 子模块
git submodule update --init deepcode-cli
cd deepcode-cli && npm install && npm test

# 方案 B：直接用 MiMo-Reasonix 的架构作为参考重写 LiMa CLI
# （更彻底，但成本更高）
```

推荐方案 A：先让现有 CLI 跑起来，再渐进改进。

### 第 2 步：移植关键模式到 LiMa 服务端

| 模式 | 来源 | 目标文件 | 预计工时 |
|------|------|----------|----------|
| 编辑门控 ReadTracker | `edit-blocks.ts` | `agent_runtime/workspace_sandbox.py` | 2h |
| 工具修复 Scavenge | `repair/scavenge.ts` | `text_tool_extractor.py` | 1h |
| 工具修复 Truncation | `repair/truncation.ts` | `text_tool_extractor.py` | 30min |
| Storm breaker | `repair/storm.ts` | 新建 `routes/tool_storm.py` | 1h |

### 第 3 步：LiMa CLI 体验升级

- 添加 Ink 风格的进度指示器（当前 Telegram bot 有，CLI 侧无）
- `/lima plan|test|review|ship` 命令 → 结构化 artifact bundle
- 成本实时显示

### 跳过（不适用于 LiMa）

- i18n 多语言（LiMa 仅中文用户）
- Ink TUI 完整重写（Telegram bot 已覆盖移动场景）
- MCP marketplace（LiMa 有自建后端池，不需要第三方 marketplace）
