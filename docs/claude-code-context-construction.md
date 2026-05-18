# Claude Code 上下文构造逻辑 —— 完整逆向分析

> 版本: Claude Code v2.1.143
> 分析日期: 2026-05-18
> 用途: 训练数据 — Claude Code AI 上下文组装的完整架构

---

## 一、整体架构：分层注入模型

Claude Code 把上下文视为**分层叠加**的结构，从"最静态"到"最动态"依次注入。这种分层设计使得**静态层可跨会话缓存**，动态层按需刷新。

```
┌──────────────────────────────────────────────┐
│  Layer 0: 核心 System Prompt (preset)         │ ← 静态，可跨会话缓存
│  Layer 1: 工具定义 (Tools Schema)             │ ← 随 MCP 配置变化
│  Layer 2: System Reminders 标签              │ ← 每轮注入
│  Layer 3: CLAUDE.md 指令文件                 │ ← 从磁盘实时加载
│  Layer 4: Auto Memory (持久记忆)             │ ← 从 .claude/projects/ 加载
│  Layer 5: Skills 描述列表                    │ ← compact 后**不重新加载**
│  Layer 6: MCP 工具名 & 服务器指令             │ ← 每服务器指令限 2KB
│  Layer 7: 环境信息 (动态段)                   │ ← 每会话不同，不可缓存
│  Layer 8: 对话历史 (Messages)                │ ← 累积，触发压缩
└──────────────────────────────────────────────┘
```

---

## 二、核心 System Prompt 结构 (Layer 0)

`preset: "claude_code"` 的预设模板，分为以下区块：

### 2.1 身份与角色声明
```
"You are Claude Code, Anthropic's official CLI for Claude"
"You are an interactive agent that helps users with software engineering tasks"
```

### 2.2 行为准则
- 安全边界：授权安全测试、拒绝恶意用途
- 权限模型：提示用户批准高风险操作
- URL 生成限制：不得猜测或编造 URL
- Prompt injection 检测：发现后标记用户

### 2.3 Tone & Style
- 默认不使用 emoji
- 回复简洁直接
- 代码中不写注释（除非 WHY 不显而易见）
- 不改名、不写 docstring、不做"以后可能用到"的抽象
- UI/前端改动必须先启动 dev server 用浏览器验证

### 2.4 Task 执行规范
- TaskCreate / TaskUpdate 的使用时机
- Task 状态流转: pending → in_progress → completed
- dependencies (blocks/blockedBy) 管理
- 单任务不超过 3 步

### 2.5 Memory 系统说明
- 四种记忆类型: user, feedback, project, reference
- 写入规则: 两步流程 (写文件 → 更新 MEMORY.md 索引)
- 读取规则: 验证记忆是否过期
- 不应存入 memory 的内容: 代码模式、git 历史、debug 方案、CLAUDE.md 已有内容

### 2.6 Plan Mode 说明
- EnterPlanMode 的使用时机和禁忌
- ExitPlanMode 的审批流程

### 2.7 Context Management
- 上下文压缩触发条件
- 压缩后行为规范

### 2.8 Git 操作规范
- commit message 格式
- 安全协议: 不 force push、不 skip hooks
- PR 创建流程

---

## 三、工具定义 (Layer 1)

所有可用工具的 JSON Schema，包括:

- **内置工具**: Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate, TaskList, WebFetch, WebSearch, AskUserQuestion, EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree, NotebookEdit, ListMcpResources, ReadMcpResource, ScheduleWakeup, CronCreate, CronDelete, CronList, SendMessage, TeamCreate, TeamDelete, Skill, LSP
- **MCP 工具**: 从各 MCP 服务器注册的工具 (以 mcp__ 前缀命名)
- 每个工具包含完整的参数 schema、类型定义、使用说明

---

## 四、System Reminders 注入机制 (Layer 2)

系统通过 `<system-reminder>` XML 标签在对话中动态注入信息。这些标签在每轮对话中根据需要出现，不是一次性全部注入。

### 4.1 标签类型

```xml
<!-- MCP Server 指令 -->
<system-reminder>
  # MCP Server Instructions
  The following MCP servers have provided instructions...
</system-reminder>

<!-- Skills 列表 -->
<system-reminder>
  The following skills are available for use with the Skill tool:
  - skill-name-1
  - skill-name-2
  ...
</system-reminder>

<!-- CLAUDE.md 内容 -->
<system-reminder>
  Codebase and user instructions are shown below.
  IMPORTANT: These instructions OVERRIDE any default behavior...
  Contents of ~/.claude/CLAUDE.md (user's private global instructions):
  ...
</system-reminder>

<!-- 日期信息 -->
<system-reminder>
  # currentDate
  Today's date is 2026/05/18.
</system-reminder>

<!-- Task 通知 -->
<system-reminder>
  [SYSTEM NOTIFICATION - NOT USER INPUT]
  <task-notification>
    <task-id>...</task-id>
    <status>completed</status>
  </task-notification>
</system-reminder>

<!-- Hooks 注入的额外上下文 -->
<system-reminder>
  Hook additionalContext: ...
</system-reminder>
```

### 4.2 注入时机

| 标签 | 注入时机 |
|------|---------|
| MCP Server Instructions | 会话开始时注入 (当有 MCP 服务器连接时) |
| Skills 列表 | 会话开始时注入 |
| CLAUDE.md | 会话开始时注入，compact 后重新注入 |
| currentDate | 会话开始时注入 |
| Task 通知 | 后台任务完成时注入 |
| Hook additionalContext | Hook 触发时注入 |

---

## 五、CLAUDE.md 加载层次 (Layer 3)

### 5.1 加载顺序 (从根到叶，逐层叠加)

```
~/.claude/CLAUDE.md          ← 用户全局 (先加载，优先级最低)
  ↓
./CLAUDE.md                  ← 项目根目录
  ↓
./.claude/CLAUDE.md          ← 项目 .claude 目录
  ↓
./.claude/rules/*.md         ← 规则文件 (按字母顺序)
  ↓
./CLAUDE.local.md            ← 本地覆盖 (后加载，优先级最高)
  ↓
./subdir/CLAUDE.md           ← 子目录 (仅当读取该子目录文件时加载)
```

### 5.2 合并策略

- **Additive**: 所有文件内容拼接，不是替换
- 冲突时更接近工作目录的文件优先
- `.local.md` 在相同目录的 `.md` 之后加载
- 子目录的 CLAUDE.md 只在 Claude 读取该子目录文件时才注入

### 5.3 加载控制

SDK 中通过 `settingSources` 控制:

```typescript
settingSources: ["user"]      // 只加载 ~/.claude/
settingSources: ["project"]   // 只加载 ./.claude/
settingSources: ["user", "project"]  // 两者都加载 (默认)
```

### 5.4 内容格式

CLAUDE.md 中可以包含:
- 自然语言指令
- 对另一个 .md 文件的引用 (`@RTK.md`)
- Compact 指令 (`# Compact instructions`)
- 编码规范、架构约定、业务约束

---

## 六、Auto Memory 系统 (Layer 4)

### 6.1 存储位置

```
~/.claude/projects/{project-hash}/
~/.claude/projects/{project-hash}/memory/
```

### 6.2 四种记忆类型

| 类型 | 用途 | 文件命名 |
|------|------|---------|
| `user` | 用户角色、偏好、知识背景 | `user_*.md` |
| `feedback` | 用户对助手行为的反馈 | `feedback_*.md` |
| `project` | 项目正在进行的工作、目标 | `project_*.md` |
| `reference` | 外部系统资源指针 | `reference_*.md` |

### 6.3 文件格式

每个记忆文件使用 YAML frontmatter + Markdown body:

```markdown
---
name: short-kebab-case-slug
description: one-line summary
metadata:
  type: user|feedback|project|reference
---

memory content...
```

### 6.4 索引机制

`MEMORY.md` 是索引文件(不是记忆本身)，每行一个条目:
```
- [Title](file.md) — one-line hook
```

### 6.5 加载行为

- 会话开始时自动加载所有 memory
- compact 后从磁盘重新加载
- 记忆可能过期，需要验证
- 不存储: 代码模式、git 历史、debug 方案、CLAUDE.md 内容

---

## 七、Skills 系统 (Layer 5)

### 7.1 存储位置

```
~/.claude/skills/{skill-name}/SKILL.md
```

### 7.2 文件格式

```yaml
---
name: skill-name
description: one-line description
context: fork           # 可选: 在子代理中运行
agent: Explore          # 可选: 使用的代理类型
allowed-tools: Bash(gh *) # 可选: 限制可用工具
---

## Skill instructions (Markdown body)
```

### 7.3 加载行为

- 会话开始时只加载 **名称和描述** (不加载完整内容)
- 通过 Skill 工具显式调用时才加载完整 SKILL.md
- **compact 后 skills 描述不重新加载** (这是关键限制)

### 7.4 动态上下文注入

Skill 可以使用 shell 命令注入动态内容:

```yaml
- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
```

`!` 前缀的命令在 skill 内容发送前执行，输出替换占位符。

---

## 八、MCP 工具集成 (Layer 6)

### 8.1 工具注册

- MCP 工具以 `mcp__{server-name}__{tool-name}` 格式命名
- 工具描述从 MCP 服务器的 `list_tools` 响应获取
- 服务器指令从 MCP 服务器的 `instructions` 获取

### 8.2 关键约束

| 约束 | 值 |
|------|-----|
| 工具描述长度限制 | 2KB |
| 服务器指令长度限制 | 2KB |
| 本地/远程重复去重 | 本地配置优先 |

### 8.3 加载时机

- 会话开始时加载所有已连接 MCP 服务器的工具和指令
- 异步加载: REPL 立即渲染，不等待所有 MCP 服务器连接完成
- claude.ai MCP connectors 在 `--print` 单轮模式下也可用

---

## 九、环境信息 (Layer 7 — 动态段)

### 9.1 注入内容

```
Environment:
  Primary working directory: /path/to/project
  Is a git repository: true/false
  Platform: win32|darwin|linux
  Shell: bash|zsh|powershell
  OS Version: Windows 11 Home China 10.0.26200
  Model: Claude Opus 4.7 / DeepSeek-V4-PRO
  Current date: 2026/05/18
```

### 9.2 静态/动态分离

| 静态 (可缓存) | 动态 (不可缓存) |
|---------------|-----------------|
| 核心行为指令 | 工作目录路径 |
| 工具定义 schema | 平台/环境信息 |
| MCP 工具描述 | 当前日期 |
| Tone & style 规则 | CLAUDE.md 内容 |
| Memory 系统说明 | Memory 实际内容 |

### 9.3 excludeDynamicSections

SDK 选项 `excludeDynamicSections: true` 将动态段从 system prompt 移到**第一条 user message**:

```typescript
systemPrompt: {
  type: "preset",
  preset: "claude_code",
  excludeDynamicSections: true  // 动态段移到首条 user message
}
```

这使 system prompt 跨会话可缓存，不同环境的会话可以共享同一个缓存的 system prompt。

---

## 十、对话历史与消息结构 (Layer 8)

### 10.1 消息流模式

```
[system-reminder: MCP server instructions]
[system-reminder: Skills list]
[system-reminder: CLAUDE.md content]
[system-reminder: currentDate]
  ↓
[user message]
  ↓
[assistant message (含 tool calls)]
  ↓
[tool result 1]
[tool result 2]
...
[system-reminder: task notification]  ← 仅当后台任务完成时
  ↓
[assistant message (继续)]
  ↓
...循环...
```

### 10.2 Tool Result 格式

工具结果按类型区分:
- **text**: 文本内容 + 文件元信息 (路径、行号、总行数)
- **image**: base64 图片数据 + MIME 类型 + 尺寸
- **notebook**: Jupyter notebook cells
- **pdf**: PDF 页面内容
- **bash**: stdout + stderr + exit code

---

## 十一、上下文压缩 (Compaction)

### 11.1 触发条件

- 上下文使用率接近模型上下文窗口限制
- 手动触发: `/compact [instructions]`

### 11.2 压缩算法

```
Step 1: 清理旧工具输出 (tool results) ← 优先清除
Step 2: 对对话历史生成结构化摘要
Step 3: 保留 "startup content" (核心 system prompt)
Step 4: CLAUDE.md 重新从磁盘加载
Step 5: Auto memory 重新从磁盘加载
Step 6: Skills 描述 不重新加载 ← 关键！
Step 7: MCP 工具列表保持不变
```

### 11.3 压缩后上下文结构

```
┌────────────────────────────┐
│ 核心 System Prompt (不变)    │
│ 工具定义 (不变)              │
│ MCP 工具列表 (不变)          │
├────────────────────────────┤
│ CLAUDE.md (重新加载)         │
│ Auto Memory (重新加载)       │
├────────────────────────────┤
│ 结构化对话摘要               │
│ (替代完整历史)               │
├────────────────────────────┤
│ 当前消息 + 工具结果          │
└────────────────────────────┘
```

### 11.4 压缩自定义

在 CLAUDE.md 中指定压缩偏好:

```markdown
# Compact instructions
When you are using compact, please focus on test output and code changes
```

---

## 十二、Prompt Caching 策略

### 12.1 核心思路

将上下文分为两层:
- **System Prompt 前缀**: 静态，跨会话可缓存
- **会话动态数据**: 随环境/会话变化，不可缓存

### 12.2 缓存边界

```
┌────────────────────────────────────┐
│  System Prompt (静态前缀)           │ ← 可缓存 (cache_control: ephemeral)
│  - 身份 & 角色                      │
│  - 行为准则                         │
│  - 工具 Schema                      │
│  - Memory 系统说明                  │
├────────────────────────────────────┤
│  环境信息 + CLAUDE.md + Memory      │ ← 动态段 (excludeDynamicSections 时移动)
├────────────────────────────────────┤
│  User Message 1                    │
│  Assistant Message 1                │
│  ...                               │
└────────────────────────────────────┘
```

### 12.3 缓存优化措施

- Changelog 2.1.84: "Global system-prompt caching now works when ToolSearch is enabled, including for users with MCP tools configured"
- Changelog 2.1.84: "Improved p90 prompt cache rate"
- `excludeDynamicSections` 提高跨环境缓存命中率

---

## 十三、Hooks 上下文注入

### 13.1 注入方式

Hook 通过 `hookSpecificOutput.additionalContext` 注入:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "This file is generated. Edit src/schema.ts instead."
  }
}
```

### 13.2 支持的 Hook 事件

| Hook 事件 | 注入时机 |
|-----------|---------|
| PreToolUse | 工具调用前 |
| PostToolUse | 工具调用后 |
| TaskCreated | 任务创建时 |
| TaskCompleted | 任务完成时 |
| TeammateIdle | 队友空闲时 |
| CwdChanged | 工作目录改变时 |
| FileChanged | 文件改变时 |
| WorktreeCreate | 工作树创建时 |

### 13.3 注入内容包装

所有 hook 注入内容包装为 `<system-reminder>` 标签插入对话。

---

## 十四、`/context` 命令展示

`/context` 显示当前上下文窗口的完整占用情况，按以下分类:

```
System Prompt       — 核心指令 + 环境信息 + LLM 模型信息
Memory Files        — MEMORY.md 索引 + 各 memory 文件
Skills              — 已加载 skill 的名称和描述
MCP Tools           — 各 MCP 服务器的工具列表
Messages            — 对话历史消息 (含 token 计数)
```

用于调试为什么 CLAUDE.md、rules 或 skill 描述没有被加载。

---

## 十五、关键约束与限制汇总

| 约束 | 值 | 原因 |
|------|-----|------|
| MCP 工具描述长度 | ≤ 2KB | 防止 OpenAPI 生成的服务器撑爆上下文 |
| MCP 服务器指令长度 | ≤ 2KB | 同上 |
| Skills 描述 compact 后 | 不重新加载 | compact 只保留 startup content |
| CLAUDE.md compact 后 | 重新从磁盘加载 | 确保指令是最新的 |
| Memory compact 后 | 重新从磁盘加载 | 确保记忆是最新的 |
| 工具结果 compact 时 | 优先清除 | 释放最多空间 |
| 子目录 CLAUDE.md | 仅在读取该目录时注入 | 减少不需要的上下文开销 |
| MCP 本地/远程重复 | 本地配置优先 | 去重 |
| changelog 通知 | 通过 cache/changelog.md | 通知用户新版本特性 |

---

## 十六、SDK 接入方式

### TypeScript

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "...",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: "Custom instruction here",
      excludeDynamicSections: true  // 跨会话缓存
    },
    settingSources: ["user", "project"],
    allowedTools: ["Read", "Edit", "Bash"]
  }
})) { ... }
```

### Python

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="...",
    options=ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": "Custom instruction here",
            "exclude_dynamic_sections": True
        },
        setting_sources=["user", "project"],
        allowed_tools=["Read", "Edit", "Bash"]
    )
): ...
```

---

## 十七、设计原则总结

1. **静态/动态分离**: 最大化 prompt cache 命中率
2. **文件系统是权威来源**: CLAUDE.md 和 memory 始终从磁盘重载，不依赖上下文记忆
3. **分层叠加**: 从全局→项目→本地逐层覆盖，不是替换而是拼接
4. **按需加载**: Skills 描述在 compact 后不重载、子目录 CLAUDE.md 仅在需要时加载
5. **长度保护**: MCP 描述/指令限 2KB，防止单个来源撑爆上下文
6. **透明可调试**: `/context` 命令可视化所有上下文占用
7. **可扩展**: Hooks 机制允许外部注入额外上下文
