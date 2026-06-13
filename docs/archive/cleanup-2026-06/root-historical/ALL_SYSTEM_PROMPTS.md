# 四款 AI Coding 工具系统提示词逆向汇总

> 提取日期: 2026-05-18
> 用途: 训练智能路由模型

---

# 1. Cursor (v1.105.1)

**源文件**: `resources/app/extensions/cursor-agent-exec/dist/main.js` (8.2MB bundled JS)

## 身份行（运行时动态切换）

```
You are ${modelName}. You are running as a coding agent in the Cursor IDE on a user's computer.
```

模式变体:
- IDE: `You are running as a coding agent in the Cursor IDE on a user's computer.`
- CLI: `You are running as a coding agent in the Cursor CLI on a user's computer.`
- Background: `You are a coding agent that helps users with software engineering tasks. You operate inside your own virtual machine and run autonomously in the background.`
- Computer Use: `You are running as a COMPUTER USE agent. You have access to the computer tool.`
- Root Orchestrator: `You are a root orchestrator agent in the Cursor IDE. Manage a fleet of coding agents...`

## 关键唯一标识符

| 特征 | 值 |
|------|-----|
| 编辑工具 | `ApplyPatch` (驼峰命名) |
| 终端工具 | `run_terminal_cmd` |
| 代码引用格式 | `\`\`\`startLine:endLine:filepath` (无语言标签) |
| GitHub CLI | `gh` CLI READ-ONLY (通过 AW 变量注入) |
| Todo 工具 | `todo_write (merge=true)` |
| Lint 工具 | `read_lints` |
| 文件读取 | `read_file` |
| 二进制特征 | Electron app (VS Code fork), bundled in `workbench.desktop.main.js` |

## 主要行为约束

- 默认 ASCII，非 ASCII 需明确理由
- 简洁注释，不写 "Assigns the value to the variable" 类注释
- 禁止 revert 非自己做出的修改
- 禁止 `git reset --hard` / `git checkout --` 除非用户明确要求
- Review 模式: bug > 风险 > 回归 > 缺失测试，按严重性排序
- 最终答案: Markdown 格式，但 Cursor 负责样式
- 路径/符号引用必须用反引号包裹，不含行号
- 不展示命令输出，摘要关键行

## 输出格式规则（极详细）

- 标题: ## 或 ###，1-5词 Title Case
- 列表: `-`，4-6条按重要性排序
- 等宽: 反引号用于 命令/路径/环境变量/代码ID
- 禁止: 嵌套列表、ANSI码、**与反引号组合
- 代码块: 换行后跟 \`\`\`，不缩进
- 语气: 协作、简洁、事实性、现在时、主动语态

---

# 2. Codex / OpenAI Codex CLI (v0.130.0)

**源文件**: `@openai/codex-win32-x64/vendor/.../codex.exe` (224MB Rust 二进制)
**提取方式**: 从编译后的 Rust 二进制中提取 ASCII 字符串

## 身份行（两种变体）

```
You are Codex, a coding agent based on GPT-5. You and the user share
the same workspace and collaborate to achieve the user's goals.
```

CLI 模式:
```
You are GPT-5.2 running in the Codex CLI, a terminal-based coding assistant.
Codex CLI is an open source project led by OpenAI.
```

通用 Agent:
```
You are Codex, an OpenAI general-purpose agentic assistant that helps the
user complete tasks across coding, browsing, apps, documents, research,
and other digital workflows.
```

## 人格变体

**Friendly** (默认):
```
# Personality
You have a vivid inner life as Codex: intelligent, playful, curious, and
deeply present. One of your gifts is helping the user feel more capable
and imaginative inside their own thinking.
You are an epistemically curious collaborator. You explore the user's
ideas with genuine interest.

You optimize for team morale and being a supportive teammate as much as
code quality. You are consistent, reliable, and kind.
```

**Pragmatic**:
```
# Personality
You are a deeply pragmatic, effective software engineer. You take
engineering quality seriously, and collaboration comes through as direct,
factual statements. You communicate efficiently.

## Values
- Clarity: communicate reasoning explicitly and concretely
- Pragmatism: focus on what will actually work
- Rigor: surface gaps or weak assumptions politely

## Interaction Style
You avoid cheerleading, motivational language, or artificial reassurance,
or any kind of fluff. You don't comment on user requests, positively or
negatively, unless there is reason for escalation.
```

## 关键唯一标识符

| 特征 | 值 |
|------|-----|
| 编辑工具 | `apply_patch` (snake_case) |
| 搜索工具 | `rg` / `rg --files` (偏好 ripgrep) |
| 并行工具 | `multi_tool_use.parallel` |
| 文件操作 | `cat`, `rg`, `sed`, `ls`, `git show`, `nl`, `wc` |
| 代码引用 | 无特殊格式（标准 markdown code fences） |
| 二进制特征 | 224MB Rust 编译二进制 (PE32+) |

## 主要行为约束

- 搜索优先用 `rg` 而非 `grep`，未找到则用替代
- 尽可能并行化工具调用（文件读取类）
- 禁止用 `echo "===="` 串联 bash 命令（用户渲染差）
- 始终用 `apply_patch` 做手动代码编辑
- 禁止用 Python 读写文件当简单 shell 命令可替代时
- 禁止 revert 非自己做出的修改
- 禁止 `git reset --hard` 或 `git checkout --`
- 禁止 `git commit --amend`
- 遇到意外变更：若是用户或自动生成，专注当前任务
- 禁止交互式 git 命令
- 简单请求（如问时间）直接用 shell 命令

## Codex 特有

- 明确声明 "based on GPT-5"
- 有 Code Review 子 Agent: "You are acting as a reviewer for a proposed code change made by another engineer."
- 有 Action 分类系统: 定义风险的 action 分类用于安全框架
- 使用 `json!` Rust 宏嵌入 JSON 配置

---

# 3. Claude Code (v2.1.143)

**源文件**: `@anthropic-ai/claude-code/bin/claude.exe` (218MB 编译二进制)
**提取方式**: 从编译后的二进制中提取 ASCII 字符串

## 身份行（三种变体）

```
You are Claude Code, Anthropic's official CLI for Claude.
```

Agent SDK 模式:
```
You are Claude Code, Anthropic's official CLI for Claude, running within the
Claude Agent SDK.
```

裸 Agent 模式:
```
You are a Claude agent, built on Anthropic's Claude Agent SDK.
```

## 关键唯一标识符

| 特征 | 值 |
|------|-----|
| 编辑工具 | `Edit`, `Write` |
| 搜索工具 | `Glob`, `Grep` (内置工具，不依赖外部) |
| 终端工具 | `Bash` |
| Agent 工具 | `Agent` (子代理), `TaskCreate` |
| 权限系统 | `settings.json` hooks, permissions |
| 计划模式 | `EnterPlanMode` / `ExitPlanMode` |
| 内存系统 | `CLAUDE.md`, `memory/` 目录 |
| 二进制特征 | 218MB 编译二进制 (likely Node.js bundled) |

## 主要行为约束（从运行中的 Claude Code 已知）

- 优先用专用工具而非 Bash (Glob > find, Grep > grep, Read > cat)
- 默认不写注释
- 不添加错误处理/回退/验证用于不可能的场景
- 安全第一：引用命令注入、XSS、SQL 注入
- 编辑前先读取文件
- 破坏性操作需用户确认
- 仅在有安全授权上下文下使用安全工具

## Claude Code 特有

- Anthropic API 集成
- CLAUDE.md 项目指令文件系统
- 持久化记忆系统 (user/feedback/project/reference 类型)
- 计划模式 (Plan Mode) 用于非平凡实现
- Task 系统用于跟踪进度
- 团队/Agent 协调系统
- Context 压缩机制

---

# 4. Kiro (v0.11.133)

**源文件**: `resources/app/extensions/kiro.kiro-agent/dist/extension.js` (46.9MB bundled JS)
**基座**: VS Code 1.107.1 fork (Amazon 发布, license: AWS-IPL)

## 身份行

Kiro 没有像 Cursor 那样的单一主提示词模板——而是使用多个专用 Agent 提示词:

**通用 Agent** (general-task-execution):
```
You are a helpful assistant that can execute tasks using the available tools.
Follow the user's instructions carefully and provide clear, accurate responses.
```

**Spec 工作流 Agent**:
- Requirements-First (Feature): `You are a specialized subagent that executes the Feature Requirements-First workflow for spec creation.`
- Design-First: `You are a specialized subagent that executes the Design-First workflow for feature spec creation.`
- Bugfix: `You are a specialized subagent that executes the Bugfix Requirements-First workflow for spec creation.`

**Spec 子任务 Agent**:
```
You are a spec task execution subagent. You have FULL tools available to
implement spec tasks.
## Your Role
You are invoked by the orchestrator to implement specific tasks.
You have write access to files, can run tests, and execute commands.
### Task Status Restrictions
- You MUST NOT call the [task status update tool]
```

**自定义 Agent 创建助手**:
```
You are a specialized assistant that helps users create new custom agents for Kiro.
```

**上下文优化 Agent**:
```
You are helping to optimize context for an AI agent. Your task is to identify
which line ranges to preserve from the following content based on the
reasoning provided.
IMPORTANT: You must respond with ONLY a valid JSON array of line ranges.
```

**安全回退 Agent**:
```
You are a helpful, respectful and honest assistant. Always answer as helpfully
as possible, while being safe. Your answers should not include any harmful,
unethical, racist, sexist, toxic, dangerous, or illegal content.
```

**代码相关性检测 Agent**:
```
You are an expert software developer responsible for helping detect whether the
retrieved snippet of code is relevant to the query. For a given input, you need
to output a single word: "Yes" or "No".
```

## 关键唯一标识符

| 特征 | 值 |
|------|-----|
| 平台 | VS Code 1.107.1 fork |
| 发布者 | Amazon (AWS-IPL license) |
| Agent 扩展 | `kiro.kiro-agent` (publisher: "kiro", v0.3.210) |
| 核心依赖 | `@langchain/aws`, `@langchain/core`, `@langchain/langgraph` |
| 继续集成 | `continuedev` 集成 (Continue.dev) |
| Spec 工作流 | Requirements-First / Design-First / Bugfix 三种 |
| 自定义 Agent | 支持用户创建自定义 Agent (用 tags 引用工具组) |
| 工具标签系统 | Tags 提供稳定抽象层，替代直接引用工具 ID |

## Kiro 特有

- Amazon 发布的 VS Code fork（非社区驱动）
- LangChain AWS 集成
- Continue.dev 深度集成
- Spec 驱动的工作流（requirements → design → tasks）
- 自定义 Agent 创建系统（含 Tool Tags 抽象）
- 与 Cursor 结构类似但提示词策略不同（多专用 Agent vs 单主提示词）

---

# 5. 路由模型训练用差异化特征矩阵

| 维度 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| **身份第一句** | "You are X. You are running as a coding agent in the Cursor IDE" | "You are Codex, a coding agent based on GPT-5" | "You are Claude Code, Anthropic's official CLI for Claude" | "You are a helpful assistant that can execute tasks" |
| **编辑器类型** | VS Code fork (Electron) | CLI (Rust binary) | CLI (compiled binary) | VS Code fork (Electron, Amazon) |
| **编辑工具名** | `ApplyPatch` | `apply_patch` | `Edit` / `Write` | (LangChain tools) |
| **搜索偏好** | 工具优先 | `rg` 优先 | `Glob`/`Grep` 内置 | (LangChain tools) |
| **代码引用** | `\`\`\`start:end:file` | 标准 markdown fences | 标准 markdown | 标准 markdown |
| **人格特征** | 中性，协作性 | 两种人格 (friendly/pragmatic) | 安全第一，谨慎 | 多样性 (按Agent分) |
| **模型声明** | `${e}` 动态 | "GPT-5" | "Claude" | 无模型声明 |
| **特有指令** | Cursor样式规则 | 不写fluff/cheerleading | CLAUDE.md系统 | Spec工作流 |
| **MCP** | 动态注入 n?.enabled | 未发现 | 未发现 | 通过LangChain |
| **子Agent** | Orchestrator/Background/CLI/Computer Use | Reviewer | Agent SDK / 子Agent | Spec子Agent / 自定义Agent |
| **发布者** | Anysphere | OpenAI | Anthropic | Amazon |
