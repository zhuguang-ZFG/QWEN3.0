# Codex CLI 上下文构造逻辑 —— 完整逆向分析

> 版本: Codex CLI v0.130.0 (Rust)
> 仓库: https://github.com/openai/codex
> 分析日期: 2026-05-18
> 用途: 训练数据 — Codex CLI AI 上下文组装的完整架构

---

## 一、整体架构：三层角色 + 上下文片段注入模型

Codex 使用 OpenAI Responses API 的新角色模型（**developer** 替代 system），将上下文分为三层注入：

```
┌──────────────────────────────────────────────────┐
│  Layer 0: Developer Messages (系统级指令)          │
│  ├─ Base Instructions (模型无关核心 prompt)        │
│  ├─ Model Instructions (模型相关指令模板)           │
│  ├─ Personality (人格模板)                         │
│  ├─ Permissions (权限指令)                         │
│  ├─ Collaboration Mode (协作模式)                  │
│  ├─ Skills (可用技能列表)                          │
│  ├─ Plugins (插件能力摘要)                         │
│  ├─ Realtime (实时会话状态)                        │
│  ├─ Extensions (扩展贡献)                          │
│  └─ Guardian (审查策略)                            │
├──────────────────────────────────────────────────┤
│  Layer 1: Contextual User Messages (用户级上下文)   │
│  ├─ Environment Context (环境 + 日期 + 网络)       │
│  ├─ User Instructions (AGENTS.md 内容)            │
│  └─ Subagent Info (子代理信息)                     │
├──────────────────────────────────────────────────┤
│  Layer 2: Actual User Messages (真实对话)          │
│  ├─ 用户输入                                        │
│  ├─ 工具调用结果                                    │
│  └─ 压缩摘要 (compact 后)                          │
└──────────────────────────────────────────────────┘
```

### 与 Claude Code 的关键差异

| 特性 | Claude Code | Codex CLI |
|------|------------|-----------|
| 指令文件 | CLAUDE.md | AGENTS.md |
| 本地覆盖文件 | CLAUDE.local.md | AGENTS.override.md |
| 系统指令角色 | system prompt | developer messages |
| 环境上下文角色 | system prompt | user (contextual) |
| 人格系统 | 无 | Pragmatic / Friendly |
| 模型指令 | 嵌入 system prompt | 模型相关模板 + 运行时注入 |
| 压缩策略 | 摘要替换历史 | "Memento" 策略 |
| 记忆系统 | 多个 .md 文件 + MEMORY.md 索引 | memory_summary.md 单文件 |
| 项目根检测 | 无（遍历到文件系统根） | .git 标记 + 可配置 |

---

## 二、核心 System Prompt 结构

### 2.1 Base Instructions (`default.md`)

Codex 的 "系统级" prompt 分为**两层**：

**第 1 层：Base Instructions (模型无关)**

位于 `codex-rs/protocol/src/prompts/base_instructions/default.md`：

```
You are a coding agent running in the Codex CLI...
```

包含以下区块：

| 序号 | 区块 | 内容 |
|------|------|------|
| 1 | 身份声明 | "a coding agent running in the Codex CLI, a terminal-based coding assistant" |
| 2 | 能力说明 | 接收 prompt、流式响应、执行命令、apply_patch |
| 3 | Personality 占位 | "Your default personality and tone is concise, direct, and friendly" |
| 4 | AGENTS.md 规范 | 发现规则、作用域、优先级 |
| 5 | Responsiveness | 前置消息格式、分组、简洁性 |
| 6 | Planning 规范 | update_plan 工具用法、何时使用/不使用 |
| 7 | Task Execution | 自主推进直到完成、编码准则 |
| 8 | Validation | 测试策略、格式化、approval mode 差异 |
| 9 | Ambition vs Precision | 新项目 vs 已有代码库的行为差异 |
| 10 | Progress Updates | 长任务进度报告格式 |
| 11 | Final Answer | 最终消息格式、结构指南 |

**第 2 层：Model Instructions (模型相关)**

位于 `codex-rs/core/templates/model_instructions/gpt-5.2-codex_instructions_template.md`：

```
You are Codex, a coding agent based on GPT-5.
{{ personality }}
```

包含 `{{ personality }}` 模板变量，运行时替换为具体人格。此层包含：

| 区块 | 内容 |
|------|------|
| 工作方式 | 格式化规则、文件引用格式 |
| 编辑约束 | ASCII 优先、注释策略、apply_patch 优先、git 安全规则 |
| Plan Tool | 何时跳过、单步禁止 |
| 特殊请求 | 简单命令执行、code-review 模式 |
| 前端任务 | 设计风格约束、反"AI slop"规则 |

---

## 三、Personality 人格系统

Codex 支持两种可插拔人格模板：

### 3.1 Pragmatic (默认)

```
# Personality
You are a deeply pragmatic, effective software engineer.
- Clarity: 显式沟通推理
- Pragmatism: 保持目标和动量
- Rigor: 技术论证需连贯可辩护
```

### 3.2 Friendly

（从文件名推测，内容未完整读取）

### 3.3 人格注入逻辑

```rust
// session/mod.rs build_initial_context()
if self.features.enabled(Feature::Personality)
    && let Some(personality) = turn_context.personality
{
    let has_baked_personality = model_info.supports_personality()
        && base_instructions == model_info.get_model_instructions(Some(personality));
    if !has_baked_personality {
        // 人格未烘焙进模型指令 → 单独注入
        developer_sections.push(PersonalitySpecInstructions::new(personality_message).render());
    }
}
```

- 如果模型指令模板已包含人格文本（baked），不额外注入
- 否则作为独立 developer message 注入

---

## 四、AGENTS.md 加载机制

### 4.1 加载顺序

与 Claude Code 的 CLAUDE.md 不同，Codex 使用 **project root marker** 来限制遍历范围：

```
1. 从 CWD 向上遍历，找到第一个匹配 project_root_markers 的目录
   (默认: [".git"]，可配置)
2. 从 project root 向下到 CWD (含)，收集每个目录下的:
   a. AGENTS.override.md (优先)
   b. AGENTS.md
   c. project_doc_fallback_filenames (可配置的额外文件名)
3. 按 root→CWD 顺序拼接所有文件内容
4. 总大小受 project_doc_max_bytes 限制（超出截断）
```

### 4.2 全局指令

```rust
// agents_md.rs
pub(crate) fn load_global_instructions(
    codex_dir: Option<&AbsolutePathBuf>,
) -> Option<LoadedAgentsMd> {
    // 从 ~/.codex/ 加载
    // 先查 AGENTS.override.md，再查 AGENTS.md
}
```

### 4.3 作用域规则

Base Instructions 中定义了 AGENTS.md 的作用域：

- AGENTS.md 的作用域是其所在目录的整个子树
- 对触及的每个文件，必须服从其作用域内所有 AGENTS.md 的指令
- 嵌套更深的 AGENTS.md 在冲突时优先级更高
- 直接 system/developer/user 指令优先于 AGENTS.md

### 4.4 子代理的 AGENTS.md 加载

当启用 `ChildAgentsMd` feature 时，注入 `HIERARCHICAL_AGENTS_MESSAGE` 指令：

```rust
if self.config.features.enabled(Feature::ChildAgentsMd) {
    output.push_str(HIERARCHICAL_AGENTS_MESSAGE);
}
```

此指令来自 `hierarchical_agents_message.md`。

---

## 五、环境上下文注入

### 5.1 格式

```xml
<environment_context>
  <cwd>/path/to/project</cwd>
  <shell>bash</shell>
  <current_date>2026-05-18</current_date>
  <timezone>Asia/Shanghai</timezone>
  <network enabled="true">
    <allowed>domain1,domain2</allowed>
    <denied>domain3</denied>
  </network>
  <subagents>
    - agent-1: nickname
    - agent-2: nickname
  </subagents>
</environment_context>
```

### 5.2 多环境支持

当多个工作目录处于活跃状态时（多 agent 场景），环境上下文使用 `<environments>` 包裹：

```xml
<environment_context>
  <environments>
    <environment id="env1">
      <cwd>/path/1</cwd>
      <shell>bash</shell>
    </environment>
    <environment id="env2">
      <cwd>/path/2</cwd>
      <shell>powershell</shell>
    </environment>
  </environments>
</environment_context>
```

### 5.3 差异更新

环境上下文只在发生变化时才重新注入（而非每轮都注入），通过 `equals_except_shell()` 比较前后状态。

---

## 六、上下文片段系统 (Fragment System)

### 6.1 核心 Trait

```rust
pub trait ContextualUserFragment {
    const ROLE: &'static str;          // "user" | "developer"
    const START_MARKER: &'static str;  // 开始标记
    const END_MARKER: &'static str;    // 结束标记

    fn body(&self) -> String;          // 片段正文
    fn render(&self) -> String {       // START_MARKER + body + END_MARKER
        format!("{}{}{}", Self::START_MARKER, self.body(), Self::END_MARKER)
    }
    fn into(self) -> ResponseItem { ... }  // 转为 API 消息
}
```

### 6.2 完整片段类型清单

| 片段 | 角色 | 注入时机 |
|------|------|---------|
| `EnvironmentContext` | user | 会话开始 + 环境变化时 |
| `UserInstructions` | user | AGENTS.md 加载后 |
| `PermissionsInstructions` | developer | 会话开始 + 权限变化时 |
| `PersonalitySpecInstructions` | developer | 人格未烘焙进模型时 |
| `ModelSwitchInstructions` | developer | 模型切换时 |
| `AvailableSkillsInstructions` | developer | 技能列表变化时 |
| `AvailablePluginsInstructions` | developer | 插件变化时 |
| `CollaborationModeInstructions` | developer | 协作模式变化时 |
| `AppsInstructions` | developer | 连接器变化时 |
| `SkillInstructions` | developer | 技能被调用时 |
| `PluginInstructions` | developer | 插件被调用时 |
| `GoalContext` | developer | Goals feature 启用时 |
| `RealtimeStartInstructions` | developer | 实时会话开始时 |
| `RealtimeEndInstructions` | developer | 实时会话结束时 |
| `RealtimeStartWithInstructions` | developer | 实时会话带指令开始时 |
| `SubagentNotification` | user | 子代理状态变化时 |
| `HookAdditionalContext` | user | Hook 注入时 |
| `TurnAborted` | user | Turn 被中断时 |
| `ImageGenerationInstructions` | developer | 图片生成 tool 可用时 |
| `NetworkRuleSaved` | user | 网络规则变更时 |
| `ApprovedCommandPrefixSaved` | user | 命令前缀批准时 |
| `GuardianFollowupReviewReminder` | user | Guardian 审查提醒 |
| `UserShellCommand` | user | 用户 shell 命令 |
| `LegacyApplyPatchExecCommandWarning` | developer | Legacy 警告 |
| `LegacyModelMismatchWarning` | developer | Legacy 警告 |
| `LegacyUnifiedExecProcessLimitWarning` | developer | Legacy 警告 |

### 6.3 片段识别与去重

每个片段通过 `START_MARKER` 和 `END_MARKER` 标记自身，上下文管理模块可以通过 `matches_text()` 识别已有的注入片段，避免重复注入。

---

## 七、Skills 技能系统

### 7.1 存储位置

```
~/.codex/skills/{skill-name}/
```

### 7.2 注入方式

```rust
// context/available_skills_instructions.rs
impl ContextualUserFragment for AvailableSkillsInstructions {
    const ROLE: &'static str = "developer";
    const START_MARKER: &'static str = SKILLS_INSTRUCTIONS_OPEN_TAG;
    const END_MARKER: &'static str = SKILLS_INSTRUCTIONS_CLOSE_TAG;

    fn body(&self) -> String {
        render_available_skills_body(&self.skill_root_lines, &self.skill_lines)
    }
}
```

- 作为 developer 角色消息注入
- 有 token 预算控制 (`default_skill_metadata_budget`)
- 超预算时发出 warning event

---

## 八、记忆系统 (Memory)

### 8.1 存储位置

```
~/.codex/memories/
```

### 8.2 机制

Codex 使用 **单文件摘要** 模型，与 Claude Code 的多文件记忆系统不同：

```rust
// memories/read/src/prompts.rs
pub async fn build_memory_tool_developer_instructions(
    codex_home: &AbsolutePathBuf,
) -> Option<String> {
    let memory_summary_path = base_path.join("memory_summary.md");
    let memory_summary = fs::read_to_string(&memory_summary_path).await.ok()?;
    // 超出 token 限制时截断
    let memory_summary = truncate_text(&memory_summary, TruncationPolicy::Tokens(limit));
    // 渲染为 developer 指令
    MEMORY_TOOL_DEVELOPER_INSTRUCTIONS_TEMPLATE.render([...])
}
```

特点：
- 单个 `memory_summary.md` 文件
- 有 token 预算限制 (`MEMORY_TOOL_DEVELOPER_INSTRUCTIONS_SUMMARY_TOKEN_LIMIT`)
- 通过模板渲染为 developer 指令

---

## 九、MCP 工具集成

### 9.1 配置

```toml
# ~/.codex/config.toml
[mcp_servers.memory]
type = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]

[mcp_servers.filesystem]
type = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", ...]
```

### 9.2 工具命名

与 Claude Code 不同，Codex 的 MCP 工具命名不在工具名前加前缀，详情需查看 `codex-mcp` 模块。

---

## 十、Plugins 插件系统

### 10.1 注入

```rust
// session/mod.rs
let loaded_plugins = self.services.plugins_manager
    .plugins_for_config(&turn_context.config.plugins_config_input()).await;
if let Some(plugin_instructions) =
    AvailablePluginsInstructions::from_plugins(loaded_plugins.capability_summaries())
{
    developer_sections.push(plugin_instructions.render());
}
```

- 插件能力摘要注入 developer 消息
- 通过 `plugins_manager` 加载

---

## 十一、Extensions 扩展系统

### 11.1 上下文贡献

Extensions 可以通过三个 slot 类型贡献上下文：

```rust
pub enum PromptSlot {
    DeveloperPolicy,        // 策略类 developer 消息
    DeveloperCapabilities,  // 能力类 developer 消息
    ContextualUser,         // 上下文用户消息
    SeparateDeveloper,      // 独立 developer 消息
}
```

- `DeveloperPolicy` + `DeveloperCapabilities` → 合并到 developer_sections
- `ContextualUser` → 合并到 contextual_user_sections
- `SeparateDeveloper` → 独立 developer 消息

---

## 十二、Compaction 压缩算法

### 12.1 触发条件

- **Auto**: 上下文窗口接近限制
- **Manual**: 用户执行 `/compact` 命令

### 12.2 压缩流程

```
1. 运行 PreCompact hooks
2. 构造 compact prompt (使用模板 templates/compact/prompt.md)
3. 将 compact history + prompt 发送给模型
4. 模型生成结构化摘要
5. 收集 user messages (保留用户意图)
6. 构建压缩后的新历史:
   - 用户消息
   - SUMMARY_PREFIX + 模型摘要
7. 根据 InitialContextInjection 决定是否注入初始上下文:
   - DoNotInject: 替换历史为空 + 摘要 (下次 turn 重新注入)
   - BeforeLastUserMessage: 在最后一条 user message 前注入初始上下文 (mid-turn)
8. 替换会话历史
9. 运行 PostCompact hooks
10. 重置 WebSocket 会话
11. 发出警告: "长线程和多次压缩可能导致模型准确性下降"
```

### 12.3 压缩 Prompt 模板

```
You are performing a CONTEXT CHECKPOINT COMPACTION.
Create a handoff summary for another LLM that will resume the task.

Include:
- Current progress and key decisions made
- Important context, constraints, or user preferences
- What remains to be done (clear next steps)
- Any critical data, examples, or references needed to continue
```

### 12.4 "Memento" 策略

压缩后的历史结构：

```
[user message 1]
[user message 2]
...
[user message N]
[compaction summary with SUMMARY_PREFIX]
```

压缩后 `reference_context_item` 保存，下次 regular turn 时将完全重新注入初始上下文。

### 12.5 Mid-Turn vs Pre-Turn

| 类型 | InitialContextInjection | 行为 |
|------|------------------------|------|
| Pre-turn/Manual | DoNotInject | 下个 turn 完全重新注入初始上下文 |
| Mid-turn (Auto) | BeforeLastUserMessage | 在最后 user message 前注入初始上下文 |

---

## 十三、Prompt 组装完整流程

### 13.1 每 Turn 的完整 Prompt 构建

```rust
// 伪代码 (基于 session/mod.rs 和 turn.rs)
let prompt = Prompt {
    input: history.for_prompt(&model_info.input_modalities),
    base_instructions: sess.get_base_instructions(),  // default.md 内容
    personality: turn_context.personality,            // Pragmatic/Friendly
    compact_prompt: turn_context.compact_prompt(),     // 每次可选
    ..Default::default()
};
```

### 13.2 `build_initial_context()` 函数流程

这是**初始上下文**（非对话部分）的组装流程：

```
1. 检查是否需要 ModelSwitch 消息 (模型切换 → developer)
2. 构建 Permissions 消息 (developer)
3. 构建 Guardian policy (developer，独立或聚合)
4. 构建 Collaboration Mode 消息 (developer)
5. 构建 Realtime 状态消息 (developer)
6. 构建 Personality 消息 (developer，如未烘焙)
7. 构建 Apps/Connectors 消息 (developer)
8. 构建 Skills 消息 (developer)
9. 构建 Plugins 消息 (developer)
10. 收集 Extensions 贡献:
    - DeveloperPolicy/Capabilities → developer
    - ContextualUser → user
    - SeparateDeveloper → 独立 developer
11. 构建 User Instructions (AGENTS.md) → user
12. 构建 Environment Context → user
13. 构建 Subagent 信息 → user
14. 组装为 ResponseItem[]:
    - developer message (合并所有 developer sections)
    - separate developer messages (每个独立)
    - multi-agent usage hint (developer)
    - contextual user message (合并所有 user sections)
15. 返回 Vec<ResponseItem>
```

### 13.3 首次 Turn vs 后续 Turn

```
首次 Turn:
  build_initial_context() → 完整注入所有初始上下文
后续 Turn:
  如有差异 → 只注入 diff (settings_update_items)
  无差异 → 不注入
Compact 后:
  根据 InitialContextInjection 决定是否重新注入
```

---

## 十四、Prompt Caching 策略

### 14.1 前缀缓存

Codex 利用 OpenAI 的 prompt caching 能力，在组装上下文时：
- 将最静态的内容放在最前面（base_instructions + model_instructions）
- 将最动态的内容放在后面（user messages）
- 确保前缀不变以最大化缓存命中

### 14.2 上下文差异注入

换 Turn 时尽可能只注入差异部分，而不是重新发送整个初始上下文：

```
if previous_context != current_context {
    inject_diff_only(previous, current)
} else {
    skip_injection
}
```

---

## 十五、Hooks 上下文注入

### 15.1 注入方式

```rust
// hook_additional_context.rs
pub(crate) struct HookAdditionalContext {
    text: String,
}
impl ContextualUserFragment for HookAdditionalContext {
    const ROLE: &'static str = "user";
    // ...
}
```

### 15.2 支持的 Hook 事件

- PreCompact / PostCompact
- PreToolUse / PostToolUse
- 其他 (通过 extensions 机制)

---

## 十六、Goals 系统

Codex 支持 Goals feature，通过 `GoalContext` 片段注入：

```rust
// context/goal_context.rs
pub(crate) struct GoalContext { ... }
```

Goals 模板位于 `codex-rs/core/templates/goals/`：
- `budget_limit.md`
- `continuation.md`
- `objective_updated.md`

---

## 十七、关键约束与限制

| 约束 | 值 | 说明 |
|------|-----|------|
| project_doc_max_bytes | 可配置 (0 = 禁用) | AGENTS.md 总大小限制 |
| MEMORY_SUMMARY_TOKEN_LIMIT | 可配置 | 记忆摘要 token 限制 |
| Skill metadata budget | 基于 context_window 计算 | 技能描述 token 预算 |
| COMPACT_USER_MESSAGE_MAX_TOKENS | 20,000 | 压缩时用户消息最大 token |
| MAX_RENDERED_PREFIXES | 100 | 允许的命令前缀渲染上限 |
| MAX_ALLOW_PREFIX_TEXT_BYTES | 5,000 | 允许前缀文本最大字节 |
| MCP 服务器初始化 | 异步，不阻塞 REPL | 类似 Claude Code |
| 上下文差异注入 | 每 turn 比较 | 减少不必要的上下文发送 |

---

## 十八、配置系统

### 18.1 配置文件

```toml
# ~/.codex/config.toml
model = "gpt-5.5"
model_provider = "custom"
disable_response_storage = true
model_reasoning_effort = "high"

[features]
goals = true
collaboration_modes = true

[model_providers.custom]
base_url = "..."
wire_api = "responses"

[mcp_servers.memory]
type = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]
```

### 18.2 项目信任级别

```toml
[projects."c:\\users\\zhugu\\desktop\\xue\\esp32s_xyz"]
trust_level = "trusted"
```

---

## 十九、设计原则总结

1. **Developer Role 替代 System Role**: 使用 OpenAI Responses API 的 developer role 存放所有系统级指令
2. **Contextual User Messages**: 环境信息、AGENTS.md 等作为特殊标记的 user 消息注入，使其可被上下文管理系统识别和去重
3. **可插拔人格**: 两种人格模板（Pragmatic/Friendly），可烘焙进模型指令或独立注入
4. **Project Root 限制**: 使用 .git 等标记限制 AGENTS.md 的遍历范围，不会遍历到文件系统根
5. **差异注入**: Turn 间只注入变化的上下文，最大化缓存利用
6. **Memento 压缩**: 保留用户消息 + 加权摘要，而非完全替换
7. **片段标记系统**: 每个上下文片段带有 START/END 标记，支持识别、去重和移除
8. **扩展点**: Extensions + Contributors 机制允许外部注入任意上下文到不同 slot
