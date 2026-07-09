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

**已删除（勿找代码）**：`routing_engine*`、旧 `server.py` 聊天栈、`context_pipeline` 主路径等 — 见 `docs/archive/`。

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

---

## 常用命令

```powershell
python -m pytest tests/ -v -q          # 测试
ruff check .                             # lint
powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean
powershell -File scripts/cursor_rules_audit.ps1
python scripts/deploy_unified.py --target jdcloud   # 默认京东云主生产
$env:LIMA_VOICE_E2E_STRICT='1'; python scripts/run_voice_e2e_production.py  # 语音 strict E2E
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
