# AI 编码工具上下文构造 —— 7 种范式横向对比总纲

> 覆盖: Claude Code / Codex CLI / Cursor IDE / Aider / Gemini CLI / Cline / Continue
> 分析日期: 2026-05-18
> 用途: AI Router 训练特征提取 + 上下文工程设计参考

---

## 〇、一句话特征

| 工具 | 核心范式 | 一句话 |
|------|---------|--------|
| Claude Code | **分层注入** | 8层线性叠加，system-reminder标签驱动，Memory作为文件系统持久层 |
| Codex CLI | **角色分离** | Developer/User双角色，可插拔Personality，Fragment标记系统 |
| Cursor IDE | **极致Lazy Loading** | 642 token极简系统提示，万物皆文件，静默上下文注入，双层AI |
| Aider | **Map-Reduce** | Tree-sitter AST→代码引用图→PageRank排序，强弱模型分工 |
| Gemini CLI | **反应式管线图** | ContextGraph + Processor Pipeline + EventBus驱动，Topic追踪 |
| Cline | **组件+变体** | 13组件×12+模型家族变体，最详细的40行内联Rules |
| Continue | **可插拔Provider** | 40+Context Providers，18+消息模板，完全模型无关 |

---

## 一、系统提示词长度对比

```
Cursor:     ▏ ~642 tokens  (极简)
Aider:      ▎ ~2,000 tokens (含模板变量)
Continue:   ▌ ~2,500 tokens (含模式选择)
Gemini CLI: ▌ ~3,000 tokens (10 sections)
Codex CLI:  ▋ ~4,000 tokens (两层)
Cline:      ▊ ~4,500 tokens (13组件 + 40行rules)
Claude Code:█ ~8,000+ tokens (8层全部)
```

**规律**: 系统提示词越短 → Lazy Loading 做得越好 → 留给代码的 token 越多

---

## 二、上下文注入时机

```
                        Pre-Turn    During-Turn    Per-Message
Claude Code               ✅             ❌             ✅
Codex CLI                 ✅             ❌             ✅(diff)
Cursor IDE                ✅             ✅             ✅(silent)
Aider                     ✅             ✅(refresh)    ❌
Gemini CLI                ✅             ✅(pipeline)   ✅(topic)
Cline                     ✅             ❌             ❌
Continue                  ✅(providers)  ❌             ❌
```

**规律**: Cursor 是唯一三个时机都注入的工具 → 信息最新鲜 → 用户感觉"最聪明"

---

## 三、指令文件系统

| 工具 | 文件名 | 覆盖文件 | 层次化 | Glob匹配 |
|------|--------|---------|--------|---------|
| Claude Code | CLAUDE.md | CLAUDE.local.md | 项目树遍历 | ❌ |
| Codex CLI | AGENTS.md | AGENTS.override.md | project_root→CWD | ❌ |
| Cursor | .cursor/rules/*.mdc | .cursorrules(旧) | 目录嵌套 | ✅ |
| Gemini CLI | GEMINI.md | 无 | global/project/ext | ❌ |
| Aider | 无 | 无 | 无 | ❌ |
| Cline | .clinerules | CLAUDE.md/AGENTS.md | 项目根→全局 | ❌ |
| Continue | .continuerules | 无 | 项目→全局 | ✅(provider) |

**规律**: Cursor 和 Continue 有 glob 匹配 → 规则精准控制 → 不浪费 token

---

## 四、代码库理解方式

| 工具 | 方式 | 索引 | 缓存 |
|------|------|------|------|
| Claude Code | Grep/Glob工具(按需) | 无 | 无 |
| Codex CLI | rg搜索(按需) | 无 | 无 |
| Cursor | **Semantic Search + Grep** | 向量Embedding | SQLite |
| Aider | **Tree-sitter AST + 引用图** | Tags Cache | SQLite |
| Gemini CLI | Grep/Glob + Codebase Investigator | 无 | 无 |
| Cline | search_files(按需) | 无 | 无 |
| Continue | **Embedding + Reranker** | 向量DB | 本地DB |

**规律**: 有预索引的工具(Cursor/Aider/Continue)比按需搜索的工具定位代码快 3-10x

---

## 五、压缩策略

| 工具 | 触发点 | 压缩方式 | 可恢复 |
|------|--------|---------|--------|
| Claude Code | 接近limit | 结构化摘要 | ❌(重载CLAUDE.md) |
| Codex CLI | 接近limit | Memento(保留user msg+摘要) | ❌ |
| Cursor | ~85% fill | 摘要+原文存文件 | ✅(read回溯) |
| Aider | 增量 | 用户第一人称摘要 | ❌ |
| Gemini CLI | 50% tokens | 30%保留,user边界分割 | ❌ |
| Cline | 接近limit | summarize_task工具调用 | ❌ |
| Continue | 未明确 | Provider重新采集 | ✅(provider重跑) |

**规律**: Cursor 是唯一"可恢复"压缩的工具 → 压缩不丢信息

---

## 六、模型使用策略

| 工具 | 主模型 | 辅助模型 | 用途 |
|------|--------|---------|------|
| Claude Code | Claude Opus/Sonnet | 无 | - |
| Codex CLI | GPT-5 | 无 | - |
| Cursor | GPT-4o/Claude | **Apply Model** | 执行文件编辑 |
| Aider | Claude/GPT | **Weak Model** | RepoMap + Commit |
| Gemini CLI | Gemini Pro/Flash | Flash Lite | Compression |
| Cline | 12+模型家族 | 无 | - |
| Continue | 任意(18+模板) | Embed Model + Reranker | 检索 |

**规律**: 强弱模型分工(Cursor/Aider)能显著降低成本和错误率

---

## 七、MCP 集成深度

| 工具 | MCP工具命名 | 描述注入 | 指令限制 |
|------|-----------|---------|---------|
| Claude Code | `mcp__server__tool` | System-reminder | 2KB/工具 |
| Codex CLI | 无前缀 | Developer消息 | 2KB/服务器 |
| Cursor | 原生命名 | 名在上下文/描述在文件 | **46.9%节省** |
| Gemini CLI | PromptRegistry | Snippets注入 | 无显式限制 |
| Aider | 不支持 | - | - |
| Cline | MCP_SECTION | Component注入 | 无显式限制 |
| Continue | MCPContextProvider | Provider注入 | 无显式限制 |

**规律**: Cursor 的 MCP token 节省(46.9%)是独特优势

---

## 八、独特差异化特征

| 工具 | 独有特征 | 工程价值 |
|------|---------|---------|
| Claude Code | Memory系统(4类型) | 跨会话持久记忆 |
| Codex CLI | Personality(可插拔人格) | 不同任务不同风格 |
| Cursor | **双层AI + "万物皆文件"** | 成本优化 + token节省 |
| Aider | **RepoMap(Map-Reduce)** | 无需索引即可理解大型代码库 |
| Gemini CLI | **ContextGraph(反应式)** | 上下文修改有审计记录 |
| Cline | **13组件×12变体** | 最细粒度的模型适配 |
| Continue | **40+ Providers** | 最广泛的上下文来源 |

---

## 九、设计规律总结

### 规律 1: Lazy Loading 优于 Eager Loading
```
Cursor(极简prompt) > Gemini CLI(sections) > Claude Code(全量注入)
```
信息不是越多越好，按需拉取比全部塞入效果好。

### 规律 2: 文件系统是最终的稳定抽象
```
Cursor(万物皆文件) ≈ Aider(文件内容+RepoMap) > Continue(Providers) > Claude Code(内存优先)
```
文件系统容量无限、可索引、可回溯、模型天然理解。

### 规律 3: 显式标记 > 隐式推断
```
Codex(Fragment START/END markers) > Gemini CLI(GraphMutation审计) > Cline(Component slot占位) > Claude Code(system-reminder)
```
带标记的上下文片段可以识别、去重、移除，不带标记的只能追加。

### 规律 4: 模型特定调优 > 通用模板
```
Cline(12+ variants) > Codex(2 personalities) > Cursor(per-model tuning) > Claude Code(单一prompt)
```
不同模型需要不同的提示词格式，一刀切会降低效果。

### 规律 5: 预索引 > 按需搜索
```
Cursor(Semantic Search+SQLite) ≈ Aider(Tags Cache+SQLite) ≈ Continue(Embed+Rerank+DB) > 其他(按需grep)
```
一次索引，多次查询，能大幅减少上下文收集的轮次。

### 规律 6: 可恢复压缩 > 单向摘要
```
Cursor(原文存文件、可回溯) > 其他(一次性摘要、无法回溯)
```
压缩后保留原文引用，模型可以在需要时回溯查证。

---

## 十、AI Router 训练特征矩阵

基于以上分析，提取 24 维特征用于路由分类：

### 身份特征 (4维)
```
F01: 角色声明方式    [first_person_identity|third_person_role|generic_assistant]
F02: 品牌归属        [anthropic|openai|google|independent|generic]
F03: 运行环境        [ide_embedded|terminal_cli|virtual_machine|sdk_agent]
F04: 子代理引用      [has_subagent_concept|no_subagent_concept]
```

### 工具特征 (4维)
```
F05: 编辑工具命名    [apply_patch|replace_in_file|edit_file|write_to_file|str_replace|wholefile]
F06: 搜索工具风格    [grep_glob_dedicated|semantic_search|rg_command|tree_sitter_tags]
F07: 终端工具命名    [run_terminal_cmd|execute_command|shell|bash|execute_bash]
F08: 计划工具        [todo_write|update_plan|enter_plan_mode|write_todos|无]
```

### 结构特征 (4维)
```
F09: 系统提示长度    [ultra_short(<1K)|short(1K-3K)|medium(3K-5K)|long(5K-8K)|ultra_long(>8K)]
F10: 模式切换        [multi_mode(chat/agent/plan)|act_plan|yolo_plan|single_mode]
F11: 人格系统        [has_personality_toggle|no_personality]
F12: 角色类型        [system_role|developer_role|system+user_hybrid]
```

### 记忆特征 (4维)
```
F13: 指令文件名      [claude_md|agents_md|gemini_md|cursor_rules|cline_rules|none]
F14: 记忆持久化      [file_based_memory|sqlite_storage|memory_summary|none]
F15: 规则系统        [multi_type_rules|glob_matched_rules|single_file_rules|none]
F16: 层次化记忆      [global_project_local|global_project|project_only|none]
```

### 处理特征 (4维)
```
F17: 代码理解方式    [semantic_index|tree_sitter_ast|grep_on_demand|vector_embedding]
F18: 压缩策略        [incremental_summary|memento|user_first_person|file_backed_summary|50percent_threshold]
F19: 上下文注入时机  [per_message|per_turn|manual_only]
F20: 模型架构        [single_model|dual_model|weak_strong|any_model]
```

### 质量特征 (4维)
```
F21: MCP集成方式     [prefixed_naming|native_naming|provider_based|no_mcp]
F22: 输出格式约束    [no_emojis|no_great_prefix|ascii_default|multi_backtick_fence]
F23: 安全约束强度    [strict_destructive_block|moderate_warning|basic_guidelines]
F24: Lazy Loading    [file_system_backed|prompt_inline|provider_on_demand|no_lazy_loading]
```

---

## 十一、7 种范式的特征编码

| 工具 | F09(长度) | F17(代码理解) | F18(压缩) | F20(模型) |
|------|----------|-------------|----------|----------|
| Claude Code | ultra_long | grep_on_demand | incremental_summary | single_model |
| Codex CLI | medium | grep_on_demand | memento | single_model |
| Cursor | ultra_short | semantic_index | file_backed_summary | dual_model |
| Aider | short | tree_sitter_ast | user_first_person | weak_strong |
| Gemini CLI | medium | grep_on_demand | 50percent_threshold | single_model |
| Cline | medium | grep_on_demand | incremental_summary | any_model |
| Continue | short | vector_embedding | provider_on_demand | any_model |

---

## 十二、训练数据生成建议

基于 8 份分析文档和已有 `routing_training_data.jsonl`:

```
当前覆盖: cursor(5), codex(4), claude(3), kiro(3) = 15 samples
建议扩展到:
  cursor:    12 samples (各种模式变体)
  codex:      8 samples (两种人格 + CLI/Agent)
  claude:     8 samples (SDK/CLI/各层截取)
  kiro:       6 samples (subagent类型)
  aider:      6 samples (不同edit format)
  gemini:     6 samples (plan/yolo/default)
  cline:      6 samples (不同model variant)
  continue:   6 samples (chat/agent/plan mode)
  ─────────────────────────────
  总计:      58 samples (覆盖8种工具)
```
