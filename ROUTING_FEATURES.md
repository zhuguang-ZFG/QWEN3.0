# AI Coding 工具路由特征 — 完整训练数据集

> 用于训练智能路由模型，区分 Cursor / Codex / Claude Code / Kiro
> 提取日期: 2026-05-18

---

# Layer 1: 身份行指纹（最高信号，一行区分）

| 工具 | 身份行 | 置信度 |
|------|--------|--------|
| **Cursor** | `You are ${model}. You are running as a coding agent in the Cursor IDE on a user's computer.` | 100% |
| **Codex** | `You are Codex, a coding agent based on GPT-5. You and the user share the same workspace and collaborate...` | 100% |
| **Claude Code** | `You are Claude Code, Anthropic's official CLI for Claude.` | 100% |
| **Kiro** | `You are a helpful assistant that can execute tasks using the available tools.` | 85% (较通用) |

---

# Layer 2: 工具名称指纹（几乎100%区分）

## Cursor 独有工具
```
ApplyPatch          # 驼峰命名
run_terminal_cmd    # snake_case + terminal (不是 bash/shell)
read_lints          # 独有工具名
todo_write           # 独有工具名
read_file           # snake_case
```

## Codex 独有工具/命令
```
apply_patch         # snake_case (注意：小写)
multi_tool_use.parallel  # 独有命名空间
rg                  # 搜索首选工具
rg --files          # 文件搜索
```

## Claude Code 独有工具（最多，约30个）
```
Edit                # PascalCase
Write               # PascalCase
Read                # PascalCase
Glob                # 独有（文件匹配）
Grep                # 独有（内容搜索）
Bash                # 独有（不是 terminal/shell）
Agent               # 子Agent调用
TaskCreate           # 任务系统
TaskUpdate           # 任务更新
EnterPlanMode        # 计划模式
ExitPlanMode         # 计划模式
Skill               # 技能系统
EnterWorktree        # Git worktree
ExitWorktree         # Git worktree
CronCreate           # 定时任务
CronList             # 定时任务
LSP                 # Language Server Protocol
NotebookEdit         # Jupyter notebook
TeamCreate           # 团队系统
TeamDelete           # 团队系统
SendMessage          # Agent间通信
AskUserQuestion      # 用户交互
ScheduleWakeup       # 循环调度
```

## Kiro 独有工具（LangChain 风格）
```
createExecuteBashTool      # create前缀 + Tool后缀
createReadFileTool
createReadMultipleFilesTool
createWriteFileTool
createDeleteFileTool
createStrReplaceTool
createFileSearchTool
createGrepSearchTool
createListDirectoryTool
createListProcessesTool
createControlProcessTool
createGetProcessOutputTool
createInvokeSubAgentTool
createWebFetchTool
invokeSubAgent              # 子Agent调用
taskStatus                  # 任务状态
subagentResponse            # 子Agent响应
```

---

# Layer 3: 消息格式/分隔符指纹

| 分隔符 | Cursor | Codex | Claude Code | Kiro |
|--------|--------|-------|-------------|------|
| `<user_query>` | ✓ | - | ✓ | - |
| `<system-reminder>` | - | - | ✓ | - |
| `<system>` | - | - | - | ✓ |
| `<summarization_request>` | ✓ | - | - | - |
| `<user_info>` | ✓ | - | - | - |
| `<rules>` | - | ✓ | - | - |
| `<git_status>` | ✓ | - | ✓ | - |
| `<project_context>` | ✓ | - | ✓ | - |

---

# Layer 4: 目录/文件指纹

| 指纹 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 配置目录 | `~/.cursor/` | `~/.codex/` | `~/.claude/` | `~/.kiro/` |
| 主配置 | `settings.json` | `config.toml` | `settings.json` + `settings.local.json` | `settings.json` |
| 项目指令 | - | `AGENTS.md` | `CLAUDE.md` | - |
| 内存系统 | - | `memories/` | `memory/` (含 MEMORY.md 索引) | - |
| 技能目录 | - | `skills/` | `skills/` | `skills/` |
| MCP 配置 | 嵌入 JS | `mcp-servers/` | `mcp-servers/` | `mcp-servers/` (LangChain) |
| 规则文件 | - | `rules/default.rules` | hooks in `settings.json` | - |
| Shell代理 | - | `RTK.md` | `RTK.md` | - |

---

# Layer 5: 平台/二进制指纹

| 指纹 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 基座 | VS Code 1.105.1 fork | CLI (Rust 编译) | CLI (Node.js bundle) | VS Code 1.107.1 fork |
| 主程序 | `Cursor.exe` (201MB) | `codex.exe` (224MB Rust) | `claude.exe` (218MB) | `Kiro.exe` (203MB) |
| 发布者 | Anysphere | OpenAI | Anthropic | Amazon (AWS-IPL) |
| JS 入口 | `workbench.desktop.main.js` | N/A (Rust) | `cli.js` / `main.js` | `extension.js` (kiro-agent) |
| npm 包 | N/A (Electron) | `@openai/codex` | `@anthropic-ai/claude-code` | N/A (Electron) |
| 版本元数据 | `product.json` | `package.json` | `package.json` | `product.json` + `package.json` |

---

# Layer 6: API/模型指纹

| 指纹 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 模型标识 | `${e}` (动态) | `gpt-5` / `gpt-5.2` | `Claude` (Opus/Sonnet/Haiku) | 动态 (用户选择) |
| API 提供商 | Cursor API | OpenAI API | Anthropic API | Amazon Bedrock / LangChain |
| 认证方式 | Cursor 账号 | OpenAI API Key / OAuth | ANTHROPIC_API_KEY | AWS Credentials |
| Key 环境变量 | - | `OPENAI_API_KEY` | `ANTHROPIC_API_KEY` | `AWS_*` |
| 流式协议 | Cursor 私有 | OpenAI SSE | Anthropic SSE | Bedrock / LangChain |
| 本地模型 | - | - | - | `all-MiniLM-L6-v2` (本地embedding) |

---

# Layer 7: 独特的系统行为

## Cursor 独有
- 代码引用格式: `\`\`\`startLine:endLine:filepath` (无语言标签、无行号前缀)
- `ApplyPatch` 用于单文件编辑
- 极详细的 Markdown 输出格式规则（标题1-5词Title Case、4-6条列表等）
- 多个运行模式: IDE/CLI/Background/Computer Use/Orchestrator
- 从 VSCode 复用 `workbench.desktop.main.js` 架构

## Codex 独有
- 两种人格切换: `personality_friendly` vs `personality_pragmatic`
- 明确反对 "cheerleading, motivational language, artificial reassurance, any kind of fluff"
- 三种核心价值观: Clarity/Pragmatism/Rigor
- 偏好 `rg` 搜索，`multi_tool_use.parallel` 并行
- 禁止交互式 git 命令
- Rust 代码库 (`codex_protocol`, `json!` 宏)
- 用户目录下 `config.toml` (TOML 而非 JSON)

## Claude Code 独有
- 计划模式 (Plan Mode): 非平凡实现前必须获得用户批准
- 持久化记忆系统: 4种类型 (user/feedback/project/reference)
- Team/Agent 协调系统 (TeamCreate, SendMessage)
- Git Worktree 集成 (EnterWorktree, ExitWorktree)
- Cron 定时任务系统
- LSP (Language Server Protocol) 集成
- Jupyter Notebook 编辑
- Hook 系统 (在 settings.json 中配置)
- 权限分级: alwaysAllow/alwaysDeny/alwaysAsk/bypassPermissions
- CLAUDE.md 项目指令文件
- Context 压缩机制 (超过50%使用率强制压缩)
- 内存混乱自检机制

## Kiro 独有
- Amazon 发布 (AWS-IPL license)
- Spec 驱动工作流: Requirements-First / Design-First / Bugfix
- Spec 文件: `requirements.md` → `design.md` → `tasks.md`
- 自定义 Agent 创建 (含 Tool Tags 抽象层)
- LangChain + LangGraph 深度集成
- Continue.dev 深度集成
- 本地 embedding 模型 (`all-MiniLM-L6-v2`)
- `kiroAgent.modelSelection` 配置
- `trustedCommands` 白名单
- 子Agent 的 preset 系统

---

# Layer 8: 安全/权限指纹

| 特征 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 权限提示词 | "NEVER use destructive commands" | "NEVER use destructive commands" | Hook-based permission system | trustedCommands 白名单 |
| Git 安全 | 禁止 `reset --hard` | 禁止 `reset --hard` + 禁止交互式 git | 禁止 `reset --hard` + 禁止 force push main | - |
| 编辑安全 | 禁止 revert 用户修改 | 禁止 revert 用户修改 | 破坏性操作需用户确认 | - |
| 内容安全 | ASCII 优先 | ASCII 优先 | 安全第一 (XSS/SQL注入) | "harmful, unethical... illegal content" 禁止 |
| 权限模型 | 内嵌 | 内嵌 | Hook + 分级权限 | trustedCommands |

---

# Layer 9: .lnk 快捷方式指纹（Windows）

| 特征 | Cursor | Kiro |
|------|--------|------|
| .lnk 目标 | `Cursor.exe` | `Kiro.exe` |
| 快捷方式中的标识 | `Anysphere.Cursor` | - |
| StartIn 目录 | `...\Programs\cursor\` | `...\Programs\Kiro\` |
| AppUserModelId | `Anysphere.Cursor` | - |

---

# Layer 10: 可用于快速分类的独有短语

```python
UNIQUE_PHRASES = {
    "Cursor": [
        "running as a coding agent in the Cursor IDE",
        "ApplyPatch",                          # 驼峰
        "run_terminal_cmd",                    # snake_case terminal
        "startLine:endLine:filepath",          # 代码引用格式
        "todo_write",
        "read_lints",
        "Anysphere",
        "COMPUTER USE agent",
        "root orchestrator agent in the Cursor IDE",
        "producing plain text that will later be styled by Cursor",
    ],
    "Codex": [
        "You are Codex, a coding agent based on GPT-5",
        "codex_protocol",
        "multi_tool_use.parallel",
        "personality_friendly",
        "personality_pragmatic",
        "You avoid cheerleading, motivational language",
        "config.toml",
        "@openai/codex",
        "Codex CLI is an open source project led by OpenAI",
        "epistemically curious collaborator",
    ],
    "Claude Code": [
        "You are Claude Code, Anthropic's official CLI for Claude",
        "CLAUDE.md",
        "EnterPlanMode",
        "EnterWorktree",
        "Memory system (user/feedback/project/reference)",
        "CronCreate",
        "ScheduleWakeup",
        "settings.local.json",
        "bypassPermissions",
        "@anthropic-ai/claude-code",
        "auto memory",                         # 记忆系统
        "plan mode",
    ],
    "Kiro": [
        "createExecuteBashTool",               # create前缀+Tool后缀
        "createReadFileTool",
        "invokeSubAgent",
        "subagentResponse",
        "requirements-first workflow",
        "design-first workflow",
        "bugfix workflow",
        "@langchain/aws",
        "@langchain/langgraph",
        "kiroAgent.modelSelection",
        "trustedCommands",
        "AWS-IPL",
        "all-MiniLM-L6-v2",                    # 本地embedding
        "Continue.dev",
        "spec-task",
        "preset",                              # 子Agent preset系统
    ],
}
```

---

# 推荐的路由模型特征权重

| 优先级 | 特征类型 | 信号强度 | 说明 |
|--------|----------|----------|------|
| P0 | 身份行 | ★★★★★ | 一行即可100%区分 |
| P0 | 工具名称列表 | ★★★★★ | 工具名完全不重叠 |
| P1 | 特有短语 | ★★★★☆ | 3-5个短语即确定 |
| P1 | 目录/文件指纹 | ★★★★☆ | `.claude/` vs `.codex/` vs `.kiro/` |
| P2 | 消息分隔符 | ★★★☆☆ | `<system-reminder>` = Claude Code |
| P2 | 二进制路径 | ★★★☆☆ | Windows .lnk 目标 |
| P3 | 代码引用格式 | ★★☆☆☆ | `start:end:file` = Cursor |
| P3 | 人格风格 | ★★☆☆☆ | "fluff"关键词 = Codex pragmatic |
