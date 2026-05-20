# IDE 上下文模式 — LiMa 路由参考

> 来源: Claude Code / Codex CLI / Cursor Auto Mode 逆向分析 (2026-05-20)
> 用途: 指导 IDE 指纹检测、Skills 补缺、格式兼容

## 一、IDE 指纹特征（用于 router_v3.py 检测）

| IDE | System Prompt 大小 | 必中关键词 | 格式 |
|-----|-------------------|-----------|------|
| Claude Code | ~8000 tok | `CLAUDE.md`, `EnterPlanMode`, `Claude Code` | Anthropic |
| Cursor | ~642 tok | `You are Auto`, `<user_query>`, `Cursor` | OpenAI |
| Codex CLI | ~4000 tok | `You are Codex`, `commentary`, `GPT-5` | OpenAI |
| Aider | ~2000 tok | `SEARCH/REPLACE`, `RepoMap` | OpenAI |
| Cline | ~4000 tok | `<environment_details>`, `Cline` | Anthropic |
| Continue | ~1500 tok | `continue.dev`, `Continue` | OpenAI |

## 二、各 IDE 已覆盖的 Skills（不需要重复注入）

### Claude Code (已有 ~8000 tok 指令)
- 编程规范 ✅ (详尽的 coding style)
- 安全检查 ✅ (OWASP top 10)
- 错误处理 ✅ (explicit error handling)
- Git 工作流 ✅ (commit conventions)
- 文件组织 ✅ (small files, high cohesion)
- **缺失**: 项目专属上下文 (LiMa 约定)

### Cursor (极简 642 tok，大量缺失)
- 基本通信规范 ✅
- 代码引用格式 ✅
- **缺失**: 编程规范、安全、错误处理、语言规则 — 全靠 Rules 注入

### Codex CLI (4000 tok，personality 为主)
- 温暖人格 ✅ (30% 占比)
- 前端反 AI-slop ✅
- apply_patch 编辑规则 ✅
- **缺失**: 安全检查、语言规范、项目约定

## 三、Skills 注入决策矩阵

根据 IDE 已有内容决定注入什么：

| Skill 类别 | Claude Code | Cursor | Codex | Aider | Cline | 无 IDE |
|-----------|:-----------:|:------:|:-----:|:-----:|:-----:|:------:|
| safety (不幻觉) | ❌ 已有 | ✅ 注入 | ✅ 注入 | ✅ 注入 | ❌ 已有 | ✅ 注入 |
| lang (语言规范) | ❌ 已有 | ✅ 注入 | ✅ 注入 | ❌ 已有 | ✅ 注入 | ✅ 注入 |
| style (简洁回复) | ❌ 已有 | ❌ 已有 | ❌ 已有 | ✅ 注入 | ✅ 注入 | ✅ 注入 |
| project (LiMa约定) | ✅ 注入 | ✅ 注入 | ✅ 注入 | ✅ 注入 | ✅ 注入 | ✅ 注入 |

## 四、格式兼容要点

### 请求格式
| IDE | API 格式 | 端点 | 特殊字段 |
|-----|---------|------|---------|
| Claude Code | Anthropic | /v1/messages | system (str/list), tools, tool_use blocks |
| Cursor | OpenAI | /v1/chat/completions | 无特殊 |
| Codex | OpenAI | /v1/chat/completions | 无特殊 |
| Aider | OpenAI | /v1/chat/completions | 无特殊 |
| Cline | Anthropic | /v1/messages | system, tools |

### 响应格式
| IDE | 流式协议 | Tool Call 格式 | 编辑格式 |
|-----|---------|---------------|---------|
| Claude Code | Anthropic SSE (event: content_block_delta) | tool_use block | Edit (字符串替换) |
| Cursor | OpenAI SSE (data: {...}) | — (服务端处理) | Patch-based |
| Codex | OpenAI SSE | function calling | apply_patch |

## 五、上下文预算参考

| IDE | 总 Context | System 占用 | 留给代码 | LiMa 可注入上限 |
|-----|-----------|------------|---------|---------------|
| Claude Code | 200K | ~8K (4%) | ~180K | 200 tok (极少) |
| Cursor | 100K | ~5K (5%) | ~60K | 200 tok |
| Codex | 128K | ~4K (3%) | ~100K | 200 tok |
| 无 IDE (聊天) | 32K | 0 | ~30K | 500 tok (可多注入) |

## 六、Speculative Streaming 优化

基于逆向发现的关键洞察：

1. **Cursor 不需要 footer** — 它自己管理 UI，不要追加 `[LiMa → backend]`
2. **Claude Code 需要完整 SSE** — 严格遵循 Anthropic event 格式，缺任何 event 会断流
3. **Codex 双通道** — commentary 通道可用于发送路由元信息（未来可利用）

## 七、对 LiMa 的行动项

1. `router_v3.py` — 更新 `_IDE_FINGERPRINTS` 加入更精确的检测词
2. `skills_injector.py` — 按第三节矩阵实现 per-IDE 注入策略
3. `server.py` — Cursor 请求不追加 footer；Claude Code 严格 SSE 格式
4. 未来 — Codex commentary 通道利用、Cursor Rules 动态注入
