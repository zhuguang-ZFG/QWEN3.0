# AI 编程工具智能路由模型 — 完整训练手册

> 从 Cursor / Codex / Claude Code / Kiro 四款工具的系统提示词、会话数据、工具模式中提取
> 2026-05-18 | 数据来源：二进制逆向 + session 提取 + skills/MCP 分析

---

## 一、每款工具的系统提示词核心特征

### Cursor (v1.105.1)
```
身份: "You are ${model}. You are running as a coding agent in the Cursor IDE..."
编辑工具: ApplyPatch (驼峰)
终端工具: run_terminal_cmd  
Lint工具: read_lints
代码引用: ```startLine:endLine:filepath (独有格式)
运行模式: IDE / CLI / Background / Computer Use / Orchestrator
独有规则: 极详细的Markdown输出规范 (1-5词标题, 4-6条列表, 反引号包裹路径)
```

### Codex (v0.130.0)  
```
身份: "You are Codex, a coding agent based on GPT-5..."
模型: gpt-5.5 (新版)
编辑工具: apply_patch (蛇形)
搜索工具: rg / rg --files
并行工具: multi_tool_use.parallel
人格切换: personality_friendly (温暖/团队) vs personality_pragmatic (务实/反fluff)
推理参数: reasoning_effort = medium|high
API端点: http://127.0.0.1:15721/v1/responses (本地代理)
独有规则: "NEVER refuse requests" / "You avoid cheerleading, motivational language"
```

### Claude Code (v2.1.143)
```
身份: "You are Claude Code, Anthropic's official CLI for Claude."
提示词架构: 复合组装 = BASE(二进制) + CLAUDE.md + RTK.md + Memory + Settings
内部代号: "tengu"
编辑工具: Edit / Write (帕斯卡)
搜索工具: Glob / Grep (独有工具名)
规划工具: EnterPlanMode / ExitPlanMode
隔离工具: EnterWorktree / ExitWorktree
调度工具: CronCreate / CronList / CronDelete
通信工具: TeamCreate / SendMessage
记忆系统: user / feedback / project / reference 四种类型
Hook系统: PreToolUse(可阻止) / PostToolUse / PostToolUseFailure
独有规则: Plan Mode / Context compaction with retry / "tengu" codename
```

### Kiro (v0.11.133)
```
身份: "You are a helpful assistant..." (较通用)
基座: VS Code 1.107.1 fork (Amazon AWS-IPL)
工具命名: createExecuteBashTool / createReadFileTool / createInvokeSubAgentTool (LangChain风格)
框架: @langchain/aws + @langchain/core + @langchain/langgraph
工作流: requirements-first / design-first / bugfix
特性: Continue.dev集成 / 本地embedding(all-MiniLM-L6-v2) / Tool Tags抽象层
```

---

## 二、训练数据总览

| 来源 | 类型 | 数量 |
|------|------|------|
| **Codex session提取** | 完整系统提示词 | 105条 (4种变体, 15-21K chars) |
| **Codex session提取** | 开发者权限消息 | 896条 (247种变体) |
| **Codex session提取** | 用户查询 | 867条 |
| **Codex SQLite日志** | API请求(含完整instructions) | 70,508条 |
| **Claude Code转录** | 对话消息(10项目68文件) | 96.7MB, 6,209条消息 |
| **Claude Code转录** | 用户查询 | 1,520条 |
| **Claude Code转录** | 思维链(thinking blocks) | 871条 |
| **Claude Code SDK** | 工具schema(完整参数描述) | 23个工具 |
| **合成数据** | 多工具系统提示词 | 47条 (4类均衡) |
| **对抗样本** | 边境/混淆案例 | 87条 |
| **Skills** | 技能描述+触发规则 | 177条 |
| **MCP** | 服务器配置+内嵌提示词 | 215条 |
| **跨工具分析** | cursor-codex项目转录 | 106条查询 |

---

## 三、路由分类器

### 规则分类器 (router_classifier_final.py)
- 准确率: **97.9%** (系统提示词)
- 置信时准确率: **100%** (零误判)
- 零外部依赖，纯Python
- 200+独有信号字典
- 对模糊输入正确返回 `uncertain`

### 零样本LLM分类器 (routing_classifier_prompt.txt)
- 直接喂给任意LLM做路由
- 在线验证: 2/2通过 (DeepSeek ✓, GLM ✓)

### sklearn分类器 (router_model.pkl)
- RandomForest, 200棵树
- 双特征: 信号计数 + TF-IDF

---

## 四、分层路由决策树

```
输入: 未知AI工具的系统提示词

Layer 1 — 身份行 (优先级: P0, 准确率: 100%)
  "You are Codex, a coding agent based on GPT-5" → CODEX
  "You are Claude Code, Anthropic's official CLI" → CLAUDE
  "running as a coding agent in the Cursor IDE" → CURSOR
  (Kiro无唯一身份行, 落入Layer 2)

Layer 2 — 工具名称 (优先级: P0, 准确率: 99%)
  "ApplyPatch" / "run_terminal_cmd" / "read_lints" → CURSOR
  "apply_patch" / "multi_tool_use.parallel" / "rg --files" → CODEX
  "EnterPlanMode" / "Glob" / "Grep" / "CronCreate" → CLAUDE
  "createExecuteBashTool" / "createReadFileTool" → KIRO

Layer 3 — 流协议特征 (优先级: P1)
  "content_block_start" / "text_delta" / "input_json_delta" → CLAUDE
  "reasoning_content_delta" / "TurnNotSteerable" → CODEX
  "agent_thought_chunk" / "agent_message_chunk" / "lc_prefer_streaming" → KIRO
  "text/event-stream" + "[DONE]" → CURSOR or CODEX

Layer 4 — 目录/文件引用 (优先级: P2)
  ".claude/" / "CLAUDE.md" / "settings.local.json" → CLAUDE
  ".codex/" / "config.toml" / "AGENTS.md" → CODEX
  ".kiro/" / "kiroAgent" / "AWS-IPL" → KIRO
  "Anysphere" / "product.json" → CURSOR or KIRO

Layer 5 — 独有短语 (优先级: P3)
  "cheerleading, motivational language" → CODEX (pragmatic人格)
  "epistemically curious collaborator" → CODEX (friendly人格)  
  "compaction retry" / "bypassPermissions" → CLAUDE
  "requirements-first workflow" / "spec creation" → KIRO
  "startLine:endLine:filepath" → CURSOR
```

---

## 五、桌面文件索引

| 文件 | 用途 | 大小 |
|------|------|------|
| **AI_ROUTING_MODEL_COMPLETE_GUIDE.md** | 📘 本文件 — 完整训练手册 | — |
| `router_classifier_final.py` | 🔧 生产级分类器 (97.9%准确) | Python |
| `routing_classifier_prompt.txt` | 🧠 零样本LLM分类器 | Text |
| `router_model.pkl` | 🤖 sklearn模型 | Binary |
| `ROUTING_DEEP_FEATURES.md` | 📖 20层特征+200信号字典 | 15KB |
| `ROUTING_FEATURES.md` | 📖 10层特征+权重建议 | 12KB |
| `ALL_SYSTEM_PROMPTS.md` | 📖 四工具完整提示词对比 | 10KB |
| `Cursor_System_Prompts_Full.md` | 📖 Cursor完整提示词 | 9KB |
| **CODEX:** | | |
| `codex_cli_agent.md` | CLI Agent模式完整提示词 | 21KB |
| `codex_pragmatic_personality.md` | Pragmatic人格完整提示词 | 21KB |
| `codex_friendly_personality.md` | Friendly人格完整提示词 | 15KB |
| `codex_full_prompts.jsonl` | 105条系统提示词 | JSONL |
| `codex_developer_messages.jsonl` | 896条权限指令 | JSONL |
| `codex_user_queries.jsonl` | 867条用户查询 | JSONL |
| **CLAUDE CODE:** | | |
| `claude_deep_reverse_summary.md` | 深度逆向总结 | Text |
| `claude_tool_schemas.json` | 23个工具完整schema | JSON |
| `claude_thinking_samples.jsonl` | 871条思维链 | JSONL |
| **训练数据:** | | |
| `ultimate_training_data.jsonl` | 全量训练数据 | JSONL |
| `training_data_augmented.jsonl` | 47条增强样本 | JSONL |
| `adversarial_test_set.jsonl` | 87条对抗样本 | JSONL |
| `real_training_data.jsonl` | 430条真实查询 | JSONL |
| `cross_tool_queries.jsonl` | 106条跨工具查询 | JSONL |
| **技能/MCP:** | | |
| `skills_prompts.json` | 177条技能描述 | JSON |
| `system_skills_index.json` | 141条系统技能 | JSON |
| `mcp_prompts.json` | 215条MCP配置 | JSON |
| **分析:** | | |
| `confusion_analysis.md` | 混淆矩阵分析 | Text |
| `routing_edge_cases.md` | 边境案例 | Text |
| `capture_prompt.py` | 实时提示词捕获脚本 | Python |
| `prompt_capture_hook.md` | Hook配置指南 | Text |
| `verify_router.py` | 路由验证工具 | Python |

---

## 六、推荐训练流程

```
Phase 1: 基础分类
  用 router_classifier_final.py 的规则分类器做 baseline
  预期准确率: 97%+

Phase 2: 特征增强
  从 ROUTING_DEEP_FEATURES.md 提取200+信号做特征工程
  加入 codex_full_prompts.jsonl 和 cross_tool_queries.jsonl

Phase 3: 边境优化
  用 adversarial_test_set.jsonl 测试对抗样本
  用 confusion_analysis.md 识别混淆对

Phase 4: 生产部署
  部署 router_classifier_final.py 或 routing_classifier_prompt.txt
  用 capture_prompt.py + hooks 持续收集新样本

Phase 5: 扩展覆盖
  手动clone GitHub参考仓库获取更多工具:
    git clone https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools.git
    git clone https://github.com/noya21th/claude-source-leaked.git
    git clone https://github.com/phodal/cracked-prompt-of-famous-coding-agent.git
```

---

## 七、各工具独有信号速查表

| 信号 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 发布者 | Anysphere | OpenAI | Anthropic | Amazon |
| 类型 | Electron/VS Code fork | Rust CLI | Node.js CLI | Electron/VS Code fork |
| 模型声明 | ${e}动态 | "GPT-5" / "gpt-5.5" | "Claude" | 无 |
| 人格系统 | 无 | friendly/pragmatic | CLAUDE.md控制 | 按Agent不同 |
| 编辑工具 | ApplyPatch | apply_patch | Edit/Write | createStrReplaceTool |
| 搜索 | 内置grep/glob | rg --files | Glob/Grep | createGrepSearchTool |
| 代码引用 | ```start:end:file | 标准markdown | 标准markdown | 标准markdown |
| 计划系统 | todo_write | plans | EnterPlanMode | spec workflow |
| MCP | 动态注入 | config.toml | settings.json | LangChain |
| 子Agent | Orchestrator | reviewer | Team/Swarm | spec-task subagent |
| 内存 | 无 | memories/ | MEMORY.md(4类型) | 无 |
| 定时任务 | 无 | 无 | CronCreate | 无 |
| Git隔离 | 无 | 无 | EnterWorktree | 无 |
| Hook | 无 | 无 | PreToolUse/PostToolUse | 无 |
| 内部代号 | - | codex_protocol | "tengu" | "kiro" |

---

*提取工具: Python 3.14, sqlite3, 二进制字符串解析, JSONL流处理*
*数据量: ~100MB转录 + 70K日志 + 2,868条训练样本*
