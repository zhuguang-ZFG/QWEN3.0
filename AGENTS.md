# AGENTS.md

本文件为 AI Agent 的 **Cursor 精简入口**（控制每轮 token）。完整流程、里程碑、ECC、环境变量见 [`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md)。

---

## 项目

DLC 绘图服务（Python 3.10 + FastAPI）→ ESP32 绘图/写字。公网：`https://chat.donglicao.com/dlc/*`（`:8081`）。

**当前链路：**

```
server_dlc.py → dlc_api/ → dlc_core/ → device_gateway/ → ESP32
小智 MCP → dlc_mcp/     小程序 → /device/v1/app/*
```

**已删除（勿找代码）**：`routing_engine*`、旧 `server.py` 聊天栈、`context_pipeline` 主路径等 — 历史文档已清出仓库，查 git history。

| 模块 | 路径 |
|------|------|
| 入口 | `server_dlc.py` |
| API | `dlc_api/` |
| 核心 | `dlc_core/` |
| 网关 | `device_gateway/` |
| 设备 App | `routes/device_app_*.py` |
| 语音 ASR | `device_voice/`、`routes/device_app_voice*.py`、`voice_app_ws_ticket.py` |

---

## 硬规则（不可省）

1. **Ponytail 第一** — 最小变更；ESP32/小程序先加载对应 skill → [`docs/AGENTS_PONYTAIL.md`](docs/AGENTS_PONYTAIL.md)
2. **无静默降级** — 禁止 `except: pass`；生产必须正确配置
3. **门禁** — `pytest`、`ruff check .`、单文件 ≤300 行
4. **Git** — 禁止 `git add .`；仅 stage 里程碑文件；无密钥入库
5. **CodeGraph** — 用 `lima-codegraph`；**禁止** GitNexus
6. **部署** — `.env` 只合并不覆盖；VPS 真实域名验证 → [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md)
7. **写字机/运动 PC 仿真门禁（必须主动）** — 凡改动会碰到 **G-code / 运动协议 / U1-Grbl / 设备下发路径与 Grbl 命令** 的代码（含 `esp32S_XYZ` 固件运动栈、gateway 组 G 码、FakeDevice 运动契约中与 host SIL 对齐的部分），Agent **必须自己**跑 fz `agent_gate`，**禁止**只 pytest 绿就声称运动/解析已验证、禁止先烧录排 parser：
   ```powershell
   $env:FZ_ROOT = 'D:\Users\zhugu\fz'
   $env:GRBL_ROOT = 'D:\Users\Grbl_Esp32'   # 产品写字机树；无则仅 protocol
   $env:QWEN_ROOT = 'D:\QWEN3.0'
   python $env:FZ_ROOT\scripts\agent_gate.py --profile standard
   # 失败：读 $env:FZ_ROOT\results\agent_gate_last.json
   ```
   - 纯云 API / 小程序 / 语音 / 与 G 码无关的改动：仍用本仓 `pytest`/`ruff`，**不**要求 agent_gate。
   - Host SIL **≠** 纸路/BT/真机；发版仍走清单与部署约定。
   - 仿真实现只在 **fz**（https://github.com/zhuguang-ZFG/fz），勿在 QWEN 堆 grblHAL sim 源码。
8. **主树只读 / 一 Agent 一 worktree（防多会话漂移）** — `D:\QWEN3.0` 的 `main` 工作区是**集成台**，不是并行写盘场：
   - **写代码**（改业务文件、commit）：必须在独立 git worktree（推荐 `C:\Users\zhugu\.a2a-sandboxes\<slug>` 或 `git worktree add`），禁止两个 Agent 同时 `cwd=D:\QWEN3.0` 写。
   - **主树允许**：只读排查、`status`/`log`/`diff`/`fetch`、人工 merge/发版、跑测试；**禁止**在主树对别人的 stash `pop`/`apply`。
   - **A2A 舰队**：依赖 `A2A_AUTO_WORKTREE=1` + `A2A_OWNS_STRICT=1`（bridge 启动默认）；任务声明 `owns:` 路径，重叠硬拒绝。
   - **宣称 commit 成功前**只信：`git rev-parse HEAD` + `git cat-file -t <hash>` + `git log -1`；禁止把过期 shell stdout 当真理。
   - 任务结束：`worktree remove` + 删 `a2a/*` 分支；定期 `git worktree prune`。细节 → [`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md#多-agent-工作区隔离)。

---

## 常用命令

```powershell
python -m pytest tests/ -v -q          # 测试
ruff check .                             # lint
powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean
powershell -File scripts/cursor_rules_audit.ps1
python scripts/deploy_unified.py --target jdcloud   # 默认京东云主生产
$env:LIMA_VOICE_E2E_STRICT='1'; python scripts/run_voice_e2e_production.py  # 语音 strict E2E
# 运动/G-code 相关改动后必须（见硬规则 7）：
# $env:FZ_ROOT='D:\Users\zhugu\fz'; python $env:FZ_ROOT\scripts\agent_gate.py --profile standard
```

小程序上传流程见 [`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md#常用命令)。

---

## Cursor 专项

- 规则：`.cursor/rules/dlc-core-brief.mdc` 常驻；大改 `@lima-context-injection`
- MCP：全局 4 + 项目 `lima-codegraph` → [`docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md`](docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md)
- 状态：`STATUS.md`（与 `docs/PROJECT_STATUS_CN.md` 同步）| 架构：`docs/ARCHITECTURE.md` | 语音 API：`docs-site/api/voice.md`

---

## 里程碑（摘要）

用户实现 → Agent 审查/测试 → 更新 `progress.md`/`findings.md` → 仅 stage 相关文件 → commit/push。**用户未要求时不 commit。**

完整协议、ECC、环境变量 → **`docs/AGENTS_REFERENCE_CN.md`**
