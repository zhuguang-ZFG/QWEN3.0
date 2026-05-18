# GitHub Copilot Chat 上下文构造逻辑 —— 完整逆向分析

> 版本: vscode-copilot-chat (MIT License, latest)
> 仓库: https://github.com/microsoft/vscode-copilot-chat
> 分析日期: 2026-05-18
> 用途: 训练数据 — 行业基准的上下文组装架构

---

## 一、整体架构：JSX 声明式 Prompt 系统 + Model-Family 注册表

Copilot Chat 是唯一使用 **JSX-based 声明式 Prompt 渲染** 的工具：

```tsx
<InstructionMessage>
  <Tag name='instructions'>
    You are a highly sophisticated automated coding agent...
  </Tag>
  <Tag name='toolUseInstructions'>
    When using a tool, follow the JSON schema very carefully...
  </Tag>
</InstructionMessage>
```

这带来三个独特优势：
1. **类型安全** — TypeScript 编译期检查 prompt 结构
2. **可组合** — 像 React 组件一样组合 prompt 片段
3. **可测试** — 用 Vitest + SQLite 快照测试 prompt 输出

---

## 二、System Prompt 组装顺序

```
AppendSystemPrompt (agentPrompt.tsx)
├─ 1. CopilotIdentity        — "Your name is GitHub Copilot"
├─ 2. SafetyRules            — 安全约束
├─ 3. CustomInstructions     — 用户自定义指令 (.github/copilot-instructions.md)
├─ 4. UserPreferences        — 用户偏好 (语言、缩进、行尾)
├─ 5. AgentMultirootWorkspace — 多根工作区结构
├─ 6. TerminalState          — 终端运行状态
├─ 7. WorkspaceStructure     — 工作区文件结构
├─ 8. ChatVariables          — 对话变量 (#file, #selection, #terminal)
├─ 9. AgentPrompt (模型特定)  — 核心指令 + 工具说明
│     ├─ DefaultAgentPrompt     (通用模型)
│     ├─ AlternateGPTPrompt     (GPT-5+)
│     ├─ AnthropicPrompts       (Claude)
│     ├─ GeminiPrompts          (Gemini)
│     └─ familyHPrompts         (各模型家族)
├─ 10. CodeBlockFormatting    — 代码块格式规则
├─ 11. NotebookInstructions   — Jupyter Notebook 特殊指令
├─ 12. ApplyPatchInstructions — Patch-based 编辑指令
├─ 13. McpToolInstructions    — MCP 工具描述和指令
├─ 14. ResponseTranslationRules — 输出翻译规则
├─ 15. MathIntegrationRules   — 数学公式渲染
└─ 16. ReminderInstructions   — 模型特定的编辑提醒 (reminder message)
```

---

## 三、核心 Agent 指令结构

### 3.1 DefaultAgentPrompt (通用)

```
<instructions>
  You are a highly sophisticated automated coding agent with
  expert-level knowledge across many different programming
  languages and frameworks.
</instructions>

<toolUseInstructions>
  When using a tool, follow the JSON schema very carefully...
  NEVER say the name of a tool to a user...
  Prefer calling tools in parallel whenever possible...
</toolUseInstructions>

<editFileInstructions>       (有条件: EditFile 可用)
  Before you edit, make sure you have the file in context...
  Use ReplaceString for single replacements...
  Use MultiReplaceString for bulk edits...
  NEVER show the changes to the user, just call the tool...
</editFileInstructions>

<applyPatchInstructions>      (有条件: ApplyPatch 可用)
<notebookInstructions>        (有条件: Notebook 上下文)
<outputFormatting>
  Use proper Markdown formatting. Wrap filenames in backticks.
</outputFormatting>
```

### 3.2 AlternateGPTPrompt (GPT-5+ 专用)

GPT-5+ 额外包含完整的工作流：

```
# Workflow
1. Understand the problem deeply.
2. Investigate the codebase.
3. Develop a clear, step-by-step plan. Display in todo list.
4. Implement the fix incrementally.
5. Debug as needed.
6. Test frequently.
7. Iterate until the root cause is fixed.
8. Reflect and validate comprehensively.

**CRITICAL - Before ending your turn:**
- Review and update the todo list, marking completed/skipped/blocked.
- Display the updated todo list.
- Never leave items unchecked, unmarked, or ambiguous.

## 1. Deeply Understand the Problem
- Carefully read the issue and think hard about a plan before coding.
- Break down the problem. What is expected? What are edge cases?
...
```

---

## 四、Tool 工具系统

### 4.1 完整工具清单

| 分类 | 工具名 | 实际名称 |
|------|--------|---------|
| **编辑** | `EditFile` | `insert_edit_into_file` |
| | `ReplaceString` | `replace_string_in_file` |
| | `MultiReplaceString` | `multi_replace_string_in_file` |
| | `CreateFile` | `create_file` |
| | `CreateDirectory` | `create_directory` |
| | `ApplyPatch` | `apply_patch` |
| **搜索** | `Codebase` | `semantic_search` |
| | `FindFiles` | `file_search` |
| | `FindTextInFiles` | `grep_search` |
| | `SearchWorkspaceSymbols` | `search_workspace_symbols` |
| | `SearchViewResults` | `get_search_view_results` |
| **读取** | `ReadFile` | `read_file` |
| | `ListDirectory` | `list_dir` |
| | `ViewImage` | `view_image` |
| | `ReadProjectStructure` | `read_project_structure` |
| **终端** | `CoreRunInTerminal` | `run_in_terminal` |
| | `CoreGetTerminalOutput` | `get_terminal_output` |
| | `CoreTerminalLastCommand` | `terminal_last_command` |
| **VS Code** | `VSCodeAPI` | `get_vscode_api` |
| | `GetErrors` | `get_errors` |
| | `GetScmChanges` | `get_changed_files` |
| | `RunVscodeCmd` | `run_vscode_command` |
| | `InstallExtension` | `install_extension` |
| **Subagent** | `SearchSubagent` | 搜索子代理 |
| | `ExecutionSubagent` | 执行子代理 |
| **其他** | `FetchWebPage` | `fetch_webpage` |
| | `Memory` | `memory` |
| | `CoreManageTodoList` | `manage_todo_list` |
| | `TestFailure` | `test_failure` |
| | `FindTestFiles` | `test_search` |
| | `GetProjectSetupInfo` | `get_project_setup_info` |
| | `GithubRepo` | `github_repo` |

### 4.2 条件工具注入

工具指令根据**可用性动态注入**：

```tsx
{tools[ToolName.SearchSubagent] && <>For any context searching, use SearchSubagent...</>}
{tools[ToolName.ExecutionSubagent] && <>For most terminal commands, use ExecutionSubagent...</>}
{!tools.hasSomeEditTool && <>You don't currently have any editing tools...</>}
```

---

## 五、PromptRegistry — 模型家族注册表

### 5.1 注册机制

```typescript
PromptRegistry.registerPrompt({
    familyPrefixes: ['gpt-5'],      // 模型家族前缀匹配
    matchesModel: async (endpoint) => endpoint.family.startsWith('gpt-5'),
    resolveSystemPrompt: () => AlternateGPTPrompt,       // 覆盖 SystemPrompt
    resolveReminderInstructions: () => GPTReminderInstructions,
    resolveCopilotIdentityRules: () => GPT5CopilotIdentityRule,
    resolveSafetyRules: () => GPT5SafetyRules,
    resolveUserQueryTagName: () => 'gpt5UserQuery',
});
```

### 5.2 模型家族匹配优先级

```
1. matchesModel(endpoint) → 精确匹配 (最高优先级)
2. familyPrefixes 前缀匹配     (次优先级)
3. DefaultAgentPrompt           (通用回退)
```

### 5.3 已知模型家族

| 文件 | 家族前缀 | 说明 |
|------|---------|------|
| `openai/` | gpt-4, gpt-5 | OpenAI 模型 |
| `anthropicPrompts.tsx` | claude- | Anthropic 模型 |
| `geminiPrompts.tsx` | gemini- | Google 模型 |
| `xAIPrompts.tsx` | grok- | xAI 模型 |
| `minimaxPrompts.tsx` | minimax- | MiniMax 模型 |
| `zaiPrompts.tsx` | z- | Z.ai 模型 |
| `vscModelPrompts.tsx` | vscode- | VS Code 内置模型 |

---

## 六、Prompt TSX — 声明式 Prompt 框架

### 6.1 核心 Component

```tsx
// 基础组件
<Tag name='instructions'>...</Tag>          // 命名标签
<InstructionMessage>...</InstructionMessage> // 包裹指令
<SystemMessage>...</SystemMessage>           // 系统消息
<UserMessage>...</UserMessage>               // 用户消息
<Chunk>...</Chunk>                           // 可缓存的块
<TokenLimit max={2000}>...</TokenLimit>      // Token 限制
<Document>...</Document>                     // 文档上下文
```

### 6.2 条件渲染

```tsx
{tools[ToolName.ReadFile] && <>Use ReadFile tool to...</>}
{this.props.codesearchMode && <CodesearchModeInstructions />}
{endpoint.supportsImages && <ImageInstructions />}
```

### 6.3 Dynamic Token Sizing

```tsx
async render(state: void, sizing: PromptSizing) {
    const budget = sizing.availableTokens;
    // 根据剩余 token 动态调整内容
}
```

---

## 七、上下文注入机制

### 7.1 每轮自动注入

```
User messages sent with:
├─ #file:path          — 显式引用文件
├─ #selection          — 当前选中代码
├─ #terminalLastCommand — 终端最后命令
├─ #terminalSelection  — 终端选中内容
├─ #editor             — 活跃编辑器内容
├─ NotebookSummary     — Notebook 摘要
├─ ChatVariables       — 对话变量
├─ attached images     — 截图/图片附件
└─ toolReferences      — 工具引用
```

### 7.2 Custom Instructions

```
.github/copilot-instructions.md  — 仓库级自定义指令
用户设置中的 custom instructions  — 个人指令
```

### 7.3 Terminal State

自动注入终端状态：
- 正在运行的终端进程
- 最近命令和退出码
- 终端当前工作目录

---

## 八、Memory 记忆系统

```tsx
<MemoryContextPrompt />     // 从持久化存储加载的记忆上下文
<MemoryInstructionsPrompt /> // 如何使用 memory 工具的指令
<TodoListContextPrompt />    // Todo 列表的持久化状态
```

---

## 九、Workspace 代码库理解

### 9.1 多层次搜索

```
Semantic Search (semantic_search)  — 语义向量搜索
  ↓
File Search (file_search)          — 文件名模式匹配
  ↓
Grep Search (grep_search)          — 正则内容搜索
  ↓
Search Subagent                    — 委派给搜索子代理
```

### 9.2 Workspace Structure

自动注入工作区结构：
- 多根工作区目录列表
- 项目根路径
- Workspace folders 的相对路径

---

## 十、Conversation Compression

### 10.1 两种模式

| 模式 | 触发 | 行为 |
|------|------|------|
| `triggerSummarize` | 上下文接近限制 | 独立 LLM 调用生成摘要 |
| `inlineSummarization` | 同上 | 在 agent loop 内生成摘要，不额外调用 |

### 10.2 摘要输出格式

```
TITLE: <对话标题>
USER INTENT: <用户意图>
TASK DESCRIPTION: <任务描述>
EXISTING: <已完成的工作>
PENDING: <待完成>
CODE STATE: <当前代码状态>
RELEVANT CODE/DOCUMENTATION SNIPPETS: <相关代码片段>
OTHER NOTES: <其他备注>
```

### 10.3 Background Summarizer

```typescript
// backgroundSummarizer.ts
// 后台线程定期压缩对话历史
// 不阻塞 Agent 主循环
```

---

## 十一、与 7 工具的对比

| 维度 | Copilot Chat | Claude Code | Codex CLI | Cursor | Cline |
|------|-------------|------------|-----------|--------|-------|
| Prompt 系统 | **JSX 声明式** | 字符串模板 | 字符串模板 | 编译后字符串 | 组件函数 |
| Prompt 测试 | **SQLite 快照** | 无 | 无 | 无 | 无 |
| 模型适配 | **PromptRegistry** | 单一 | 单一人格 | 模型调优 | 12+ Variants |
| 编辑工具 | **MultiReplaceString** | Edit(old/new) | apply_patch | ApplyPatch | replace_in_file |
| 子代理 | Search/Execution | Agent Tool | Subagents | Sub-agents | summarize_task |
| 自定义指令 | **.github/copilot-instructions.md** | CLAUDE.md | AGENTS.md | .cursor/rules/ | .clinerules |
| 工作流 | **GPT-5 有8步完整流程** | Plan Mode | update_plan | Plan/Act | Plan/Act |
| 终端集成 | **terminal_last_command/selection** | bash | shell | run_terminal_cmd | execute_command |
| 开源状态 | **MIT License** | 闭源 | Apache-2.0 | 闭源 | Apache-2.0 |

---

## 十二、关键设计特征

### 12.1 工业级 Prompt 工程

```
- JSX 类型安全 → 重构 prompt 不会意外破坏格式
- SQLite 快照测试 → 可以测试 prompt 输出是否符合预期
- TokenLimit 组件 → 自动截断超预算内容
- 条件渲染 → 工具不存在时不浪费 token 描述它
```

### 12.2 MultiReplaceString — 批量编辑

```
replace_string_in_file:
  单文件单次替换 → 需要多次调用

multi_replace_string_in_file:
  单文件多次替换 → 一次调用完成所有修改
  → "This is significantly more efficient than calling ReplaceString multiple times"
```

### 12.3 Subagent 委派

```
搜索子代理: 委派代码库搜索 → 返回结构化结果
执行子代理: 委派终端命令 → 返回关键输出片段
→ 子代理隔离长输出，保护主 agent 上下文
```

### 12.4 GPT-5 专用的 8 步工作流

这是最详细的模型特定调优——仅对 GPT-5+ 注入：
```
1. Deeply Understand the Problem
2. Investigate the codebase
3. Develop a step-by-step plan (with todo list)
4. Implement incrementally
5. Debug as needed
6. Test frequently
7. Iterate until root cause fixed
8. Reflect and validate comprehensively
```

---

## 十三、设计原则总结

1. **JSX 声明式 > 字符串拼接**: 类型安全、可组合、可测试
2. **模型注册表 > 硬编码**: 每个模型家族独立的 SystemPrompt / Reminder / Identity / Safety
3. **条件注入 > 全量注入**: 工具不存在不描述，避免 token 浪费
4. **子代理委派 > 工具直接调用**: 隔离长输出，保护主 agent 上下文
5. **批量操作 > 逐次操作**: MultiReplaceString 和 SearchSubagent 减少往返
6. **结构化摘要 > 自由文本**: 8 字段摘要格式，信息不丢失
7. **立即行动 > 征询许可**: "NEVER say the name of a tool to a user" — 直接用工具
