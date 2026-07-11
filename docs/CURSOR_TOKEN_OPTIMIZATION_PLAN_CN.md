# Cursor / Agent Token 节约计划

> 目标：Pro 额度不白烧。优先 **稳定前缀（prompt cache）** + **减少每轮固定注入** + **按需启用 MCP**。
>
> 不适用：为 Cursor IDE 主路径再套一层 LiteLLM（已退役，见 Phase 5b）。

---

## 原则（按优先级）

1. **前缀稳定 > 模型花样** — 同一会话、同一模型、少改 MCP/规则。
2. **固定注入越少越好** — `alwaysApply` 规则、MCP tool schema、skill 列表都是「每轮税」。
3. **检索/记忆/委托各留一个** — 代码图、记忆、子 Agent 各一套，禁止三套并行。
4. **重活用 Agent，轻问答用 Chat** — Agent 带工具才值得开 MCP。
5. **LiteLLM 已退役** — 2026-07-10 归档 `~/.whetstone/litellm-proxy`；Kimi 走官方/newapi 直连，Cursor 不绕代理。

---

## Phase 0 — 已完成（2026-07-10）

| 项 | 动作 |
|----|------|
| MCP lean 档 | 27 → **4 全局** + **项目** `.cursor/mcp.json`（lima-codegraph） |
| 有害规则 | 全局 `orchestrator.mdc` → `alwaysApply: false` |
| 退役文档 | `lima-routing-system`、`lima-architecture-deep` → `alwaysApply: false` |
| claude-mem 规则 | `claude-mem-context.mdc` → `alwaysApply: false` |
| 脚本 | `scripts/cursor_mcp_tiers.ps1`、`scripts/migrate_kimi_to_cursor.ps1` |
| 备份 | `~/.cursor/backups/mcp.json.*.bak` |

**立刻做**：Cursor → Settings → MCP → **Refresh**（若尚未刷新）。

---

## Phase 1 — MCP 分档策略（日常执行）

### 三档定义

| 档位 | 命令 | 适用场景 | MCP 数量 |
|------|------|----------|----------|
| **lean** | `cursor_mcp_tiers.ps1 -Tier lean` | 日常改 DLC/ESP32、单文件修 bug | **4 全局 + 1 项目** |
| **default** | `cursor_mcp_tiers.ps1 -Tier default` | 要 E2E、部署、a2a 委托、压缩上下文 | lean + playwright, a2a-bridge, fetch-mcp, lima-ops, limaguard, headroom, prompt-compress |
| **full** | `cursor_mcp_tiers.ps1 -Tier full` | 排障日、一次性审计 | 全部 |

### 硬规则

- **默认 lean**；任务结束或次日开机后切回 lean。
- **禁止** 长期 full（tool schema 是最大固定税）。
- **禁止** 同时启用：`gitnexus` + `lima-codegraph`（项目权威：CodeGraph / lima-codegraph）。
- **禁止** 同时启用：`agentmemory` + `kimi-mneme` + claude-mem 全功率注入。
- 需要 **a2a-bridge** 时：先 `start-a2a-bridge.ps1`，再 `-Tier default`，用完切回 lean。

```powershell
powershell -File D:\QWEN3.0\scripts\cursor_mcp_tiers.ps1 -Tier lean
powershell -File D:\QWEN3.0\scripts\setup_a2a_bridge_cursor.ps1   # 仅 default 前
```

---

## Phase 2 — 规则与 Skills 瘦身

### 2.1 项目规则（`D:\QWEN3.0\.cursor\rules\`）

| 文件 | 目标 | 说明 |
|------|------|------|
| `dlc-core-brief.mdc` | ✅ `alwaysApply: true`（~35 行） | 唯一常驻短规则，替代长 codegraph 常驻 |
| `lima-codegraph-deep.mdc` | ✅ glob 按需 | `dlc_*/**`、`device_gateway/**` 等 |
| `lima-context-injection` / `lima-auto-fix` / `lima-feature-generator` | ✅ **仅 @ 手动** | 禁止全仓 glob 强制多步 MCP |
| `lima-device-gateway.mdc` | ✅ `alwaysApply: false`，glob `device_gateway/**` | 非设备任务不注入 |
| `lima-testing-conventions.mdc` | ✅ `alwaysApply: false`，glob `tests/**` | 写测试时再加载 |
| `lima-routing-system.mdc` | 已 off | 仅 glob 命中旧文件时加载 |
| `lima-architecture-deep.mdc` | ✅ glob 收窄 | 仅 `dlc_*` / `server_dlc` / `device_gateway` |

### 2.2 全局规则（`~/.cursor/rules/`）

| 文件 | 建议 |
|------|------|
| `ponytail.mdc` | 保留 `alwaysApply: true`（短、高价值） |
| `ecc-workflow.mdc` | ✅ `alwaysApply: false`，glob `D:/QWEN3.0/**` |
| `karpathy-guidelines.mdc` | ✅ `alwaysApply: false`，需要时 @ 引用 |
| `orchestrator.mdc` | 保持 off（禁止纯 Task 委托模式） |

### 2.3 Skills 归档

- ✅ **保留 24 个**于 `~/.cursor/skills/`（清单见 `~/.cursor/skills-archive/KEEP_MANIFEST.txt`）
- ✅ **已归档 66 个**至 `~/.cursor/skills-archive/`
- 恢复：`Move-Item ~/.cursor/skills-archive/<name> ~/.cursor/skills/`
- 脚本：`powershell -File D:\QWEN3.0\scripts\cursor_archive_skills.ps1`

---

## Phase 3 — Hooks / 记忆（保护 cache 前缀）

### claude-mem（`~/.cursor/hooks.json`）

| Hook | 建议 |
|------|------|
| `session-init` | 保留 — 仅会话开始注入一次 |
| `context`（beforeSubmitPrompt） | ✅ **已关闭** — 每轮变化内容会打碎 prompt cache |
| `observation`（MCP/Shell 后） | ✅ **已关闭** — 减少每工具调用注入 |

### 记忆单一来源（三选一）

| 选项 | 适合 |
|------|------|
| **agentmemory**（当前 lean） | Cursor 内轻量跨会话 |
| kimi-mneme | 主要用 Kimi CLI 时 |
| claude-mem | 需要观测流水时（配合关 context hook） |

**不要三个全开。**

---

## Phase 4 — 会话习惯（人工纪律）

### 开新对话前

- [ ] 明确范围：1 个模块 / ≤5 个文件
- [ ] 确认 MCP 档位（默认 lean）
- [ ] 用 `@文件` 指向上下文，避免「帮我扫全仓」

### 同一会话内

- [ ] **不换模型**（Auto ↔ 指定模型会重置缓存前缀）
- [ ] 长任务续聊，少开第 2、3 个 Chat 平行烧额度
- [ ] 大 diff 分步：计划 → 实现 → 测试，每步新消息但**同线程**
- [ ] 简单问题用 **Chat**（无 MCP tool schema）

### 子 Agent / 委托

- [ ] Cursor 内优先自己做小改；仅大任务用 `a2a-bridge` → MiMo/CodeBuddy
- [ ] **禁止** a2a 路由回 Cursor Agent（:4937）除非明确要第二个 cursor-agent 进程
- [ ] Kimi `kimi-code` MCP 仅在大仓分析时开（default/full 档）

---

## Phase 5 — 项目级 Cursor 优化（2026-07-10）

### 5.1 项目 MCP（`.cursor/mcp.json`）

参考 [Cursor MCP 项目级配置](https://www.cursor-ide.com/blog/cursor-mcp-guide-2025) 与 LinuxDo [#749514](https://linux.do/t/topic/749514)：

| 层级 | 内容 |
|------|------|
| **项目** | `lima-codegraph`（`scripts/run_lima_codegraph_mcp.ps1`） |
| **全局 lean** | `filesystem, context7, agentkey, github`（4 个） |
| **可选项目** | `platformio` — 见 `.cursor/mcp.json.example`，仅固件日启用 |

```powershell
powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean   # 剥离全局里的 codegraph/platformio/agentmemory
# Cursor Settings → MCP → Refresh（合并项目 + 全局）
```

### 5.2 规则预算（GitHub / nedcodes）

- `alwaysApply: true` 合计 **< 2000 token**（约 500 行 prose）
- 项目仅 **`dlc-core-brief.mdc`** 常驻；重 SOP 改 **@ 手动** 或 **Skills**
- 审计：`powershell -File scripts/cursor_rules_audit.ps1`

### 5.3 其它

- ✅ 项目 `hooks.json` 移除已归档的 impeccable hook
- ✅ `CLAUDE.md` 瘦身为指针（完整内容在 `AGENTS.md`）
- ✅ 根 `AGENTS.md` 短摘要 + `docs/AGENTS_REFERENCE_CN.md` 完整版
- ✅ 全局 rules 118→23（`cursor_archive_global_rules.ps1`，impeccable 语言包归档）
- ✅ `.cursorignore` 排除 `esp32S_XYZ/`、`.codegraph/`、`progress.md` 等

### 5.4 MCP 响应纪律（[Token 经济学](https://ouch1978.github.io/docs/ai/vibe-coding/the-tokenomics-of-cursor-ai)）

- 工具返回：摘要 / schema / tail，禁止 MB 级 JSON 进 context
- 本地安装 MCP、去掉 `@latest`（LinuxDo MCP 超时贴）
- 会话内只开 1–2 个真用到的 MCP server

---

## Phase 5b — LiteLLM（已退役，2026-07-10）

> **状态：已归档。** `~/.whetstone/litellm-proxy` 不再维护；Kimi Code CLI 使用 `managed:kimi-code` 与 `config.toml` 内 newapi/100xlabs **直连**；Cursor 主路径为 Pro，禁止再套 LiteLLM。

```powershell
# 一次性归档（停服 + zip + 可选删除目录）
pwsh -File scripts/archive_litellm_proxy.ps1 -RemoveAfterArchive
```

| 曾用于 | 现替代 |
|--------|--------|
| Kimi → labs100x 等上游 | `~/.kimi-code/config.toml` 内 `[providers.newapi]` / `[providers.100xlabs]` |
| orchestrator weak/strong | Cursor 子 Agent / a2a-bridge（default 档按需开） |
| 语义缓存中间件 | 已弃用；勿恢复 Redis exact cache |

---

## Phase 6 — 监控与复盘（每周 5 分钟）

### 自检清单

1. `~/.cursor/mcp.json` 里 MCP 数量 ≤8？（日常）
2. 是否误开 full 档超过 1 天？
3. 全局 `alwaysApply: true` 规则 ≤3 条？
4. 项目 `alwaysApply: true` 规则 ≤2 条？
5. claude-mem `context` hook 是否仍每轮注入？

### 命令

```powershell
powershell -File scripts/cursor_rules_audit.ps1

# MCP 数量（全局 + 项目）
$g = (Get-Content $env:USERPROFILE\.cursor\mcp.json -Raw | ConvertFrom-Json).mcpServers.PSObject.Properties.Name.Count
$p = (Get-Content D:\QWEN3.0\.cursor\mcp.json -Raw | ConvertFrom-Json).mcpServers.PSObject.Properties.Name.Count
Write-Host "MCP global=$g project=$p total=$($g+$p)"
```

### 浪费信号（出现就纠偏）

- 同一问题开 3+ 个 Chat 并行
- Agent 扫全仓 + 27 MCP + gitnexus + codegraph 同时开
- orchestrator 规则误开 → 凡事 Task 委托
- 每轮 claude-mem 注入大段历史

---

## 实施顺序（建议本周）

| 天 | 动作 | 预估节省 |
|----|------|----------|
| D0 | MCP Refresh + 确认 lean 档 | 每轮 -15k~40k tool schema |
| D1 | 项目规则 device/testing 改 glob | ✅ 2026-07-10 |
| D2 | karpathy / ecc 去重 | ✅ karpathy off；ecc glob QWEN3.0 |
| D3 | skills 归档到 skills-archive | ✅ 90→24（`cursor_archive_skills.ps1`） |
| D4 | 关 claude-mem context + observation hooks | ✅ 仅 session-init / file-edit / summarize |
| D5 | 复盘 MCP 数量 + 写一条 progress 备注 | ✅ P5 项目规则/MCP |

---

## 明确不做的事

1. ❌ 为 Cursor Pro 再建 LiteLLM 层
2. ❌ 恢复 `gitnexus` MCP（与仓库 AGENTS 冲突）
3. ❌ 开启 LiteLLM Redis exact cache
4. ❌ 全局 `orchestrator.mdc` alwaysApply
5. ❌ 长期 27 MCP full 档

---

## 相关脚本与文档

| 资源 | 路径 |
|------|------|
| MCP 分档 | `scripts/cursor_mcp_tiers.ps1` |
| 规则审计 | `scripts/cursor_rules_audit.ps1` |
| 全局 rules 归档 | `scripts/cursor_archive_global_rules.ps1` |
| Agent 完整参考 | `docs/AGENTS_REFERENCE_CN.md`（根 `AGENTS.md` 为 Cursor 短摘要） |
| 项目 MCP | `.cursor/mcp.json`、`.cursor/mcp.json.example` |
| Skills 归档 | `scripts/cursor_archive_skills.ps1` |
| Kimi→Cursor 迁移 | `scripts/migrate_kimi_to_cursor.ps1` |
| LiteLLM 归档 | `scripts/archive_litellm_proxy.ps1` |
| A2A 接入 | `scripts/setup_a2a_bridge_cursor.ps1` |
| 项目 Agent 规则 | `AGENTS.md` |
| Ponytail | `docs/AGENTS_PONYTAIL.md` |

---

## 变更记录

| 日期 | 内容 |
|------|------|
| 2026-07-10 | 初版：Phase 0 落地 + Phase 1–6 计划 |
| 2026-07-10 | P2–P4：hooks 瘦身、skills 90→24、karpathy/ecc alwaysApply off |
| 2026-07-10 | P5b：AGENTS 拆分、全局 rules 118→23 |
| 2026-07-10 | P5：项目 MCP、dlc-core-brief、强制注入改 @手动、CLAUDE 瘦身、audit 脚本 |
| 2026-07-10 | LiteLLM 退役：归档脚本 + Phase 5b 标记废弃；Kimi 直连 / Cursor Pro |

---

## §7 外部参考（GitHub / LinuxDo / 社区）

| 来源 | 要点 |
|------|------|
| [Cursor Rules Docs](https://cursor.com/docs/rules) | `alwaysApply` / `globs` / `@` 手动四模式 |
| [nedcodes token budget](https://nedcodes.dev/guides/cursor-token-budget) | alwaysApply < 2000 token；globs 优于全局 |
| [Morph .mdc guide](https://www.morphllm.com/cursor-rules-best-practices) | 单规则 <500 行；示例优于长 prose |
| [awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | 按栈拆分规则，勿 monolithic |
| [Token 经济学 OUCH1978](https://ouch1978.github.io/docs/ai/vibe-coding/the-tokenomics-of-cursor-ai) | MCP 响应截断/摘要 |
| [LinuxDo #749514](https://linux.do/t/topic/749514) | MCP 本地安装、去 `@latest`、防超时 |
| [LinuxDo #695335](https://linux.do/t/topic/695335) | 长期收集 rules/MCP（按需摘取，勿全盘 alwaysApply） |
| [ofox MCP audit](https://ofox.ai/blog/claude-code-token-optimization-2026/) | 每会话只开 1–2 个 MCP server |
