# LiMa 记忆

> **更新时间: 2026-06-09（容量感知部署 + 京东云探测 closeout）**
> **分支:** `feat/kilo-provider-probe` - **HEAD:** 待 closeout push
> **最新权威来源:** `STATUS.md`、`progress.md`、`findings.md`、`docs/DOCUMENTATION_STATUS.md`

> **更新时间: 2026-05-26（P2-35 三切片 closeout）**
> **分支:** `codex/free-web-ai-probe` · **HEAD:** `4077588`（已 push）
> **权威状态:** `STATUS.md`、`docs/EXECUTION_PLAN.md`、`docs/NEXT_MILESTONES.md`
> **本文件:** 跨会话 durable 事实；计划 checkbox 以状态文档为准。

---

## 2026-06-09 Prometheus 指标快照

- 代码默认:
  - `LIMA_PROMETHEUS_METRICS` 代码中保持默认关闭;
  - 启用时，缺少 `prometheus_client` 现在会在启动验证或抓取生成时抛出显式 `RuntimeError`。
- 运行时接线:
  - `/v1/ops/metrics/prometheus` 为私有端点，禁用时返回 `404`，启用但损坏时返回 `503`，健康时返回 `200 text/plain`;
  - `routes.request_tracking.record_request()` 在正常 LiMa 内存统计后馈送 `lima_requests_total{backend,status}`;
  - `observability.prometheus_exporter` 通过 `observability.prometheus_metrics` 写入后端健康/分数 Gauge，仅在启用时启动。
- VPS 状态:
  - 当前 VPS `.env` 已设置 `LIMA_PROMETHEUS_METRICS=1`;
  - 回滚备份: `/opt/lima-router/backups/prometheus-metrics-20260609_120036/runtime-before.tgz`;
  - 本地认证抓取返回 `200` 并包含 `lima_backend_health`;
  - 公开 `chat.donglicao.com` 认证抓取返回 `200`;
  - 公开 `api.donglicao.com` 抓取路径保持 `404`。
- 部署工具:
  - `scripts/deploy_unified.py` 健康等待现为 `90s`；此切片显示之前的 `45s` 窗口可能因应用启动刚好在截止时间后完成而产生假阴性。
- 验证:
  - `tests/test_ops_metrics.py` -> `28 passed, 1 warning`;
  - `scripts/run_pre_commit_check.py --full` -> `2067 passed, 10 skipped, 1 warning`;
  - 公开认证 `model=code` 聊天返回标记 `prometheus_smoke_ok`。

## 2026-06-09 Telegram 退役快照

- 当前方向: Telegram Bot/操作员支持已从 LiMa Server 退役。未经显式方向变更，不得恢复 `/telegram/*`、webhook 注册、外发 Bot 投递或 Telegram 专用部署/烟雾脚本。
- 运行时状态:
  - `channel_retirement.py` 在健康输出中标记 `telegram=false`;
  - `server_lifespan.py` 不再启动 Telegram webhook/digest 运行时;
  - `routes/route_registry.py` 不再注册 `routes.telegram`;
  - GitHub/Gitee webhook 保留内部活动记录但不发送 Telegram 消息;
  - Agent Task 审查、Device Gateway 阶段、预算、健康/令牌告警、eval 通知和部署助手现在记录或本地存储。
- 仓库状态:
  - Telegram 根模块、`routes/telegram*.py`、Telegram 测试和 Telegram 部署/烟雾脚本已移除;
  - 活跃文档和环境示例现在将 Telegram 描述为已退役。
- 验证:
  - 聚焦 pytest: `112 passed, 1 warning`;
  - 补充: `tests/test_json_body_contract.py tests/test_channel_retirement.py` -> `9 passed, 1 warning`;
  - py_compile 和聚焦 ruff 通过; pyright `0 errors`（仅依赖解析警告）;
  - CI 风格全量 pytest 尝试: `2046 passed, 10 skipped, 8 unrelated failures`。
- VPS 证据:
  - 回滚备份: `/opt/lima-router/backups/telegram-retirement-20260609_031429/runtime-before.tgz`;
  - 部署了 23 个运行时文件并移除了远程 Telegram 专用文件;
  - VPS 本地 `/health` 报告 `modules.telegram=false`;
  - 公开 `/health=200`，公开 `POST /telegram/webhook=404`，认证公开 `model=code` 聊天 HTTP `200`;
  - 边缘防护跟进: `api.donglicao.com` 和 `chat.donglicao.com` 现对公开 `POST /telegram/webhook` 返回 nginx 级 404；备份: `/etc/nginx/conf.d/donglicao.conf.bak-20260609-040449` 和 `/etc/nginx/conf.d/chat.donglicao.com.conf.bak-20260609-040449`。

## 2026-06-09 京东云运维节点快照

- 京东云 `117.72.118.95` 是真实的 LiMa 二级运维节点，用于提供商探测/监控工作。
- 它不是主要 LiMa 路由器，未经单独设计、认证/防火墙审查、回滚计划和烟雾证据，不得成为新的公开 API 面。
- 持久非密钥来源:
  - `docs/ops/JDCLOUD_RUNTIME_STATUS.md`
  - `deploy/jdcloud/README.md`
  - 已追踪的 `deploy/jdcloud/*.sh` 和 `deploy/jdcloud/*.service` 模板
- 本地密码助手、生成的京东云报告、命令记录、cookies/sessions 和临时脚本均被忽略且不得暂存。
- `.codegraph/daemon.pid` 不再追踪；CodeGraph PID/数据库/日志文件为本地运行时状态。
- 新增只读烟雾:
  - `scripts/check_jdcloud_node.py --json` 报告脱敏容量/服务状态和主要 `chat.donglicao.com/health` 可达性;
  - 基于密钥的京东云 SSH 尚未从此工作站配置，因此在密钥认证设置完成前，脚本需要操作员提供的 `JDCLOUD_SSH_PASSWORD`。
- 运行时激活证据:
  - `lima-probe.timer` 手动启动后处于活跃状态;
  - 手动 `lima-probe.service` 退出 `status=0/SUCCESS`;
  - 发现报告 `37 new, 37 total known`;
  - 最新跟进烟雾返回 `ok=true`、`chat_health_http_code=200`、`prometheus_service=active`、`lima_probe_timer=active`、`disk_free_mb=41266`、`mem_available_mb=1761`。
- 残余京东云问题: 浏览器支持的发现调用至 loopback `127.0.0.1:8092/render` 返回 HTTP `500`；调试助手期间不要暴露该端口。

## 2026-06-09 容量感知部署快照

- `scripts/deploy_unified.py` 现于非 dry-run 上传前检查主 VPS 磁盘和内存。
- 默认值: `LIMA_DEPLOY_MIN_FREE_MB=512`; `LIMA_DEPLOY_MIN_MEM_MB=128`。
- 非 dry-run 部署在上传前于 `/opt/lima-router/backups/<label>-YYYYMMDD_HHMMSS/runtime-before.tgz` 创建 tar 备份。
- 最终助手上传证据:
  - 备份: `/opt/lima-router/backups/unified-files-20260609_130457/runtime-before.tgz`;
  - 容量: `disk_free_mb=13685`, `mem_available_mb=488`;
  - 结果: `2 uploaded, 0 failed, 0 skipped`;
  - 公开 `chat.donglicao.com/health` 返回 HTTP `200`。
- 验证:
  - 聚焦 deploy/JDCloud pytest: `10 passed`;
  - `scripts/run_pre_commit_check.py --full`: `2074 passed, 10 skipped, 1 warning`。

## 2026-06-09 Pre-Commit Hook 快照

- 本地 `.git/hooks/pre-commit.ps1` 现委托给已追踪的 `scripts/run_pre_commit_check.py`。
- 快速默认门禁:
  - 通过 `scripts/run_ruff_check.py` 检查已追踪文件的 ruff;
  - 通过 `git diff --cached --check` 检查暂存空白;
  - 对暂存 `.py` 文件执行 `py_compile`。
- 全部门禁: `python scripts/run_pre_commit_check.py --full`，使用文档化的 long/external pytest 忽略列表及唯一 `--basetemp`。
- 验证:
  - 聚焦 CI 门禁测试: `8 passed`;
  - 快速包装器和本地 hook: 通过;
  - 全量包装器: `2060 passed, 10 skipped, 1 warning`。
- 此 hook 变更不涉及 VPS 部署。

## 2026-06-09 LiMa Code 退役快照

- 当前方向: LiMa Server 保持为私有编码助手后端；`deepcode-cli` / LiMa Code CLI 已从主仓库退役。
- 仓库状态:
  - `deepcode-cli` 不再是被追踪的子模块;
  - 已追踪的 `.lima-code` 示例和 LiMa Code 专用启动器/烟雾已移除;
  - 历史 LiMa Code 文档仅作为历史证据保留在旧日志中。
- 运行时状态:
  - 通用 Agent Task / Agent Worker 服务端点保持活跃;
  - `model="code"` 保持为编码路由;
  - `model="lima-code"` 不再是编码路由别名;
  - 新学习/结果记录使用 `agent_worker`; `limacode_worker` 仅为历史 DB 兼容接受。
- 验证:
  - 本地聚焦退役 pytest: `116 passed, 1 warning`;
  - 聚焦 pyright 检查修改文件: `0 errors`;
  - 活跃追踪 ruff: 通过;
  - 公开烟雾: `/health=200`，认证 `model=code` 聊天返回 `agent-worker-retirement-ok`，`/agent/worker/preflight` 返回 `ready=true`、`contract_version=agent-task-v1+prompt-contract-v0.1`。
- VPS 回滚: `/opt/lima-router/backups/lima-code-retirement-20260609_020314/runtime-before.tgz`。
- 已知残余门禁: 不相关的 admin 重构类型错误阻塞全量 pyright，且在此脏工作区中全量 pytest 当前并非干净信号。

## 2026-05-31 Closeout 快照

- 运行时治理 closeout:
  - 已追踪的运行时 JSON 脏文件已从 Git 索引移除并忽略: `data/lima_routing_weights.json`、`data/routing_model.json`、`data/webhook_activity.json`、`data/webhook_push_dedupe.json`;
  - 本地 Git 远程已清理为纯 HTTPS URL;
  - VPS `lima-router.service` 已备份至 `/etc/systemd/system/lima-router.service.bak.20260531015530`，且不再包含硬编码的 `LIMA_API_KEY` 环境行。
- Webhook 和遥测:
  - 已禁用的 GitHub/Gitee webhook 路径现在返回 `200 ignored`，停止 503 重试噪音，同时无效签名在启用时保持 403;
  - `/agent/learn/outcome` 记录脱敏的 LiMa Code 遥测，`/v1/ops/metrics` 暴露 `cli_telemetry` 加 `backends.recovery`。
- VPS 可复现性:
  - `scripts/check_vps_environment.py` 检查所需导入和脱敏环境变量存在性;
  - 取消过期代理环境变量后安装了缺失包；最终 VPS 检查为 `ok=true`、`missing_required=[]`;
  - 可选的 `transformers` 保持缺失并显式报告为可选。
- 验证:
  - LiMa Server 全量 pytest: `2151 passed, 10 skipped in 190.58s`;
  - LiMa Code `npm.cmd test`: `476 pass, 6 skipped, 0 fail`;
  - VPS 公开 `/health` 在部署、依赖安装、unit 清理和最终重启后返回 200。

- LiMa Code headless JSON 现在包含面向操作员的显式模型遥测: 超时、重试次数、每次调用延迟/状态/错误/内容/工具计数、工具协议、工具能力和结果报告结果。
- LiMa Code 子模块已推送: `3cae0bc fix: expose headless model telemetry`。
- 真实公开工具烟雾发现并修复了服务端协议缺口: `/v1/chat/completions` 在 `tools` 分支之前构建 `ChatRequest`，因此 OpenAI `assistant.content:null` 工具历史验证失败。
- 服务端修复:
  - 在普通聊天验证之前路由 `tools` 请求;
  - 将 OpenAI `assistant.tool_calls` 和 `role:"tool"` 历史转换为 Anthropic `tool_use` / `tool_result` 块以适应现有工具管线。
- 验证:
  - LiMa Code `npm.cmd test`: `475 pass, 7 skipped, 0 fail`;
  - LiMa Code `npm.cmd run check` 和 `npm.cmd run build`: 通过;
  - LiMa Server 全量 `pytest -q`: `2143 passed, 10 skipped in 255.41s`;
  - 聚焦 chat/tool 测试: `15 passed`; 聚焦 ruff: 通过。
- VPS 证据:
  - 备份 `/opt/lima-router/routes/chat_endpoints.py.bak.20260531010857`;
  - 部署 `routes/chat_endpoints.py`，健康 OK;
  - 公开基础 CLI 烟雾返回 `lima_code_cli_smoke_ok`;
  - 公开 bash tool-call 烟雾返回 `lima_tool_call_ok`，含观察到的一次 OpenAI 工具调用和成功的 tool-result 跟进。

---

## 2026-05-30 Closeout 快照

- 全项目质量审计已关闭: 清理了未使用的导入/变量和重复的命令流代码，同时保留了兼容性导出。
- 本地验证证据:
  - `python -m ruff check --select F401,F841,F811,F821 --output-format concise .`: 通过;
  - `python -m ruff check .`: 通过;
  - `git diff --check`: 通过;
  - `python -m pytest`: `2130 passed, 10 skipped in 211.72s`。
- VPS 证据:
  - 备份 `/opt/lima-router/backups/quality-audit-20260530_201229/runtime-before.tgz`;
  - 126 个变更的生产文件已上传，0 失败，0 跳过;
  - VPS 本地 `/health` 和公开 `https://chat.donglicao.com/health` 返回 200;
  - 认证公开聊天烟雾经后端 `cerebras_gptoss` 返回 HTTP 200。
- 部署工具已加固并被回归测试覆盖:
  - `deploy_unified.py` 使用 SFTP 目录创建替代每次文件的 SSH exec 通道;
  - 上传失败返回非零并跳过重启;
  - 重启使用 `systemctl restart lima-router` 并轮询 `/health`;
  - `python -m pytest tests\test_deploy_unified.py tests\test_deploy_common.py tests\test_deploy_v3_security.py`: `11 passed`。

---

## 2026-05-26 会话交接（重开窗口必读）

### Git

- 分支: `codex/free-web-ai-probe`
- 已 push: `96b8ffc`（/chat 修复）+ `d3c5e47`（本记忆）
- 近序: `d4604b0` PE 基建 · `36b4c59` TG 流式 · `ef4b536` TG B2B · `96b8ffc` /chat fallback

### 测试

- **1672 passed, 10 skipped**（`pytest -q --ignore=active_model`）
- deepcode-cli B2B notifier: `dafe70f` on submodule `main`

### Telegram（已手机验收 12:07）

| 能力 | 状态 |
|------|------|
| 多命令同行 `/github` + `/device` | ✅ |
| 纯文字对话（无需 `/chat`） | ✅ FastAPI Depends |
| 流式 `sendMessageDraft` | 已部署 `TELEGRAM_STREAM_CHAT=1` |
| 空流 fallback | `routing_engine` + `last_resort`（`96b8ffc`） |
| B2B Code→Server | 代码✅；BotFather + 真实 username 待 E2E |

**用法:** 直接发文字；或 `/chat 问题`；空 `/chat` 有中文说明。可能穿插 `deepseek_free degraded` 告警，一般不挡回答。

**VPS `.env` 要点:** `TELEGRAM_STREAM_CHAT=1`、`TELEGRAM_B2B_ENABLED=1`、`TELEGRAM_CODE_BOT_USERNAMES=`（改真实）、`OPENOBSERVE_PASSWORD=change-me-local`、`SEARXNG_ENABLED=1`。

**文档:** `docs/TELEGRAM_BOT_DESIGN.md`、`docs/TELEGRAM_B2B_SETUP.md`。

### 生产力基建（同日）

- Netdata loopback · OpenObserve export · codesearch 本机 · SearXNG ghcr（阿里云引擎走 TinyFish fallback）· `DEVICE_PLATFORM_REFERENCE.md`

### 下一刀建议

1. 按 `docs/NEXT_MILESTONES.md` 四线选下一切片（LiMa Code worker / Device Gateway / 代码质量）
2. B2B / SafeMCP — **暂停**（等 Telegram / 站点可用）

---

## Agent 记忆文件索引（读顺序）

| 文件 | 用途 |
|------|------|
| `docs/LIMA_MEMORY.md` | **本文件** — 拓扑、证据、运维、决策原因 |
| `STATUS.md` | 一页式运行快照与 P0 全景 |
| `docs/EXECUTION_PLAN.md` | Phase 完成度与全局 Next Order |
| `docs/NEXT_MILESTONES.md` | 四线优先级：编码后端 / LiMa Code / ESP32 / 代码质量 |
| `findings.md` | 里程碑证据表（WX/CQ/PROD ID） |
| `progress.md` | 按日执行日志与测试数字 |
| `docs/WECHAT_RETIRED.md` | 微信全线退役（产品决策） |
| `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` | 质量 backlog 与 P0 状态表 |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | 请求管线权威模块归属 |
| `docs/WORKSPACE_HYGIENE.md` | 仓库外置与 `.gitignore` 本地垃圾 |
| `task_plan.md` | 用户契约；M0–M11 complete，**M12 pending**（勿与 EXECUTION_PLAN 冲突项混读） |

---

## 2026-05-26 consolidated state（优先阅读）

### 1. 产品方向（未变）

- LiMa = **私人编码助手后端**，不是商业化开放平台。
- **主推入口:** `https://chat.donglicao.com`（访客与 IDE 私用）。
- **暂停:** 支付、公共注册、商业 billing、商业 dashboard、微信真机/机器人全路线。

### 2. 微信通道：已全部退役（2026-05-25）

**决定:** 放弃 GeWe、OpenClaw 扫码、iLink/Hermes 本机桥、WCF 小号、liteapp 访客等一切微信产品方案。

| 层面 | 状态 |
|------|------|
| 访客入口 | 仅网页 `https://chat.donglicao.com`；`channel_gateway/invite.py` 只推网页 |
| 仓库 | `wechat_bridge/`、Hermes/WCF 脚本 → `scripts/archive/wechat_retired/` |
| 文档 | `docs/WECHAT_RETIRED.md`；stub 见 `docs/WECHAT_*.md` |
| VPS 服务 | `lima-weixin-ilink`、`lima-wechat-sidecar` unit 已移除；**stop + disable** |
| VPS 文件 | `scripts/cleanup_wechat_vps.py` 已执行；`find` 无 `wechat`/`weixin` 路径 |
| 环境 | `/opt/lima-router/.env` → `WECHAT_BRIDGE_ENABLED=0`；保留 `LIMA_WECHAT_SIDECAR_TOKEN` 仅供 `/channel` 契约 smoke |
| 本地卫生 | 删除 `data/wechat_install/`、`.geweapi_browser_profile/`、登录 QR；`.gitignore` 加固 |

**仍保留（非微信产品）:**

- `routes/channel_gateway.py` + `channel_gateway/`: 斜杠命令、G3 会话、公开 API 工具。
- `/channel/v1/wechat/message` 等路径名保留（sidecar 契约），默认不启用真机桥。

**Git:** `c5511fb` retire · `e09e971` hygiene · `8a7a622` VPS 记录 · `04d192d` 文档对齐。

### 3. 代码质量（2026-05-26 启动）

**计划:** `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`

| ID | 内容 | 状态 |
|----|------|------|
| P0.1 | `BodySizeLimitMiddleware`（ASGI receive 缓冲 + chunked 413） | **Done** — `server.py` 已挂载 |
| P0.2 | `/api/live-key` 仅元数据，不返回 `GOOGLE_AI_KEY` | **Done** — `routes/system_endpoints.py` |
| P0.3 | `deploy/key_rotation.py` 退役 stub；legacy → `scripts/archive/key_rotation_legacy.py` | **Done** |
| P1.1 | `semantic_cache` 写失败 `warning` + `db_write_errors` | **Done** |
| P1.2 | admin 登录 `constant_time_equals` | **Done** |
| P1.3 | 生产路径 `except: pass` → 日志 | **进行中** — 首批：`media_inbound`、`health_recorder`、`chat_post_closeout`、`admin_api` |
| P2+ | 超 300 行文件拆分、`router_http` 迁移 | Backlog |

**本次提交 `57ea35a`:** P1.3 首批 + `voice_call_live.html` fail-closed（禁止浏览器用 `/api/live-key` 拼 `?key=`）+ `test_channel_gateway_integrations` 中文文案对齐。

**全量测试（2026-05-26）:** `1530 passed, 10 skipped`（`pytest -q --ignore=active_model`）。

### 4. 文档与里程碑对齐（2026-05-26）

- 新增 **`docs/NEXT_MILESTONES.md`**: 四线并行优先级 + 文档漂移对照表。
- 修正 `findings.md` WX-088/089「Pending」→ Superseded（CQ-090 已覆盖）。
- `PERSONAL_CODING_ASSISTANT_PLAN` Next Steps 1–3 标为已完成（检索/MCP 见 EXECUTION_PLAN Phase 6–8）。
- `task_plan.md` 中 server 拆分/BACKENDS 合并 → **已由 2026-05-24 Runtime Closure 关闭**（勿重复开工）。

**提交:** `04d192d` docs reconcile milestones.

### 5. VPS 生产快照（`47.112.162.80` / `/opt/lima-router`）

| 项 | 值 |
|----|-----|
| 主服务 | `lima-router` **active**，`:8080` `/health` ok |
| Device Gateway | 公开 `https://chat.donglicao.com/device/v1/*`；Redis task store + session bus（HA 已部署） |
| Channel 部署 | `deploy_channel_gateway.py` 上传 `channel_gateway/`；`.env` 补丁 |
| FRP | `8088` → Windows LiMa `8080`（见 `local_router_start.bat`） |
| 在线 smoke | `scripts/smoke_online_distributions.py` 曾 `12/12` |
| Worker | LiMa Code 公开任务 `cfcd3f2b` → `needs_review` 已验证 |

**未做 / 延后:** Postgres 设备审计库；Gemini Live 服务端 WebSocket 代理（`/api/live-key` 已 metadata-only）。

### 6. 四线「未完成」摘要（详见 NEXT_MILESTONES）

1. **编码后端:** Kimi `4504` quota/refresh；TheOldLLM 超时；page-only Web AI 仅 sandbox；周期性 `eval_coding_backends.py`。
2. **LiMa Code:** Task Prompt Contract v0.1 → Hooks v0.1；always-on daemon **gated**；artifact ↔ learning loop 端到端证据。
3. **ESP32 / Device Gateway:** PROD-003 **真机烧录 + 运动 smoke**；M12 Hardware Companion **pending**；`esp32S_XYZ` 协议缺口（PAUSE/ESTOP 等）。
4. **代码质量:** P1.3 续扫；P2 拆 `agent_tasks.py` / `session_memory/store.py` 等。

### 7. 请求管线（新代码必读）

权威文档: **`docs/REQUEST_PIPELINE_AUTHORITY.md`**

要点:

- 生产聊天: **`routing_engine.route()`** 选路与执行；**`http_caller`** 统一 HTTP。
- 边缘: **`BodySizeLimitMiddleware`** + `access_guard` 私有 key。
- **`context_pipeline.factory`** 仅 lab，非生产 sole pipeline。
- **`deploy/key_rotation.py`** 已退役。

`server.py` 现为薄入口（~百行级）：注册路由、中间件、lifespan；chat/Anthropic/system 在 `routes/`。

### 8. 子模块与版本锚点

| 子模块 | 路径 | 锚点 / 说明 |
|--------|------|-------------|
| LiMa Code | `deepcode-cli/` | `8e680ea` — `/lima plan|test|review|ship` artifact bundle |
| ESP32 产品 | `esp32S_XYZ/` | `160e526` — fake-U8、固件 compile 已过，**真机 flash pending** |
| 官网 demo | `donglicao-site/` | tracked；`lima-demo.js` 等 |

### 9. 运维脚本速查

| 脚本 | 作用 |
|------|------|
| `scripts/deploy_channel_gateway.py` | 上传 channel + 路由；默认 `WECHAT_BRIDGE_ENABLED=0` |
| `scripts/cleanup_wechat_vps.py` | VPS 删除微信残留目录与 unit |
| `scripts/cleanup_gewe_vps.py` | GeWe 栈清理（更早） |
| `scripts/cleanup_openclaw_vps.py` | OpenClaw 退役 |
| `scripts/smoke_online_distributions.py` | 公开分发 smoke |
| `local_router_start.bat` | Windows `8080` + FRP |

### 10. 常见误判（避免重复踩坑）

- VPS `localhost:4504/4505` **不是** SCNet/Kimi 健康信号；本机代理经 **Windows 8080** 或 **FRP 8088**。
- `docs/superpowers/plans/` 未勾 checkbox **≠** 未完成；看 `PLAN_CLOSURE_STATUS.md`。
- `/channel` 契约测试名含 wechat **≠** 要恢复微信真机。
- `TECHNICAL_ARCHITECTURE.md` 含 2026-05-20 商业平台图，**部分过时**；见该文顶部「当前架构」节。

---

## 2026-05-25 Joint Debug Memory

- 截至 2026-05-25 的 P0 全景: PROD-003 ESP32 固件编译通过，下一门禁为硬件烧录；PROD-004~008 已实现或本地完成。
- 2026-05-25 LiMa Code 推进至 `8e680ea`，添加结构化 artifact bundle。
- 2026-05-25 P0.4/P0.5/P0.7 审查修复部署至 VPS。`routes/ops_metrics.py` 标准化数据。烟雾 `12/12`。
- 2026-05-25 `e3dbb9b` 修复三个 Device Gateway 生产缺口。`shaxiu/XianyuAutoAgent` 被审为参考（GPL-3.0）。
- VPS 基线部署至 `ad7cab5`。fake U8 WebSocket 失败因过期进程未加载 `routes.device_gateway`。
- nginx 快照含 `/device/v1/ws` 和 `/device/` 代理。Redis HA 模式默认为关闭。P0.1 ESP32 运动合约部署至 `4a7faed`。

> 目的: 为未来 LiMa 编码助手会话提供持久工作记忆。

## Current Direction

LiMa 现为私人编码助手后端。首要目标: 让 Cursor/Continue/Claude Code 使用最佳编码后端；优先证据支持路由；VPS 简洁。暂停: 公开注册、支付、计费、商业 dashboard。

## Production Topology

| 组件 | 当前角色 |
|---|---|
| `chat.donglicao.com` | 私有聊天和 `/v1/*` HTTPS 入口 |
| `api.donglicao.com` | 兼容 API 面，暂停 |
| `JDCloud 117.72.118.95` | 辅助探测/监控节点 |
| `lima-router` | FastAPI `:8080` |
| New API / 语音网关 | 保留但非主要方向 |

内部端口公开访问被阻断，nginx 保持外部边界。在线分布权威来源: `docs/ONLINE_DISTRIBUTIONS.md`。

## Client Configuration

```text
Primary base URL: https://chat.donglicao.com/v1
FRP base URL:     http://47.112.162.80:8088/v1
API key:          lima-local  |  Model: lima-1.3
```

使用 `chat.donglicao.com/v1` 进行 IDE 验证。

## Local Proxy And FRP Closure

闭环: IDE → VPS frps:8088 → Windows frpc → 127.0.0.1:8080 → 本地 4504/4505。FRP 注册成功、`8088/tcp` 开放。`4505` SCNet-large 兼容，`4504` Kimi 配额耗尽。

## Active Runtime Files

核心: `server.py`(薄入口)、`routing_engine.py`(场景分类/路由)、`router_v3.py`(后端池)、`code_orchestrator.py`(编码上下文)、`http_caller.py`(统一 HTTP)、`health_tracker.py`(健康/冷却)、`budget_manager.py`(预算)、`backends.py`(清单)、`mastery_loop/`、`agent_evolution/`。

## Coding Backend Evidence

85 候选、16 通过。优胜者: `scnet_large_ds_flash`、`github_gpt4o`、`github_gpt4o_mini`、`or_gptoss_120b`。快速层: `cerebras_gptoss`、`groq_gptoss`。Cloudflare: `cf_qwen_coder`、`cfai_qwen_coder` 进回退窗口。

## Free Model Status

一级 SCNet（三用例通过）: `scnet_ds_flash`、`scnet_ds_pro`、`scnet_qwen235b`、`scnet_qwen30b`。不活跃: `scnet_minimax`、`scnet_large_*`(需代理)、`kimi_*`(配额耗尽)。

## Claude Code / Anthropic Tool Route

工具请求进入 `/v1/messages`。`TOOL_TIER1_BACKENDS` 从快速后端开始，重试迭代不同后端。公开烟雾: `200`。Context Preflight 从请求数据提取 IDE 源/工作区提示。验证: `70 passed`。

## Deployment Practice

计划 → 本地测试 → 备份 → 上传 → 远程编译 → 重启 → 烟雾 → 更新文档。重启: `systemctl kill -s SIGKILL lima-router`。

## Current Risks

部分后端需 Windows 代理、Kimi 需重登录、SCNet 需持续监控、免费 Web AI 需沙盒。

## 2026-05-23 Codebase Calibration

分支 `codex/free-web-ai-probe`，`382 passed, 8 skipped`。集成: Session Memory SQLite、Memory 召回一级阶段（仅元数据）、daemon lifespan 启动、图谱检索共享注入。架构关闭项 3/4 完成。

## Next Phase

下阶段: 更多免费 Web AI、后端稳定性（令牌刷新/配额/速率冷却）、配额感知路由。已实施: 候选注册、探测 6 候选 HTTP 200、失败类别（`manual_refresh_required` 等）、`http_caller.py` 错误分类。验证: `72 passed`。

## 2026-05-24 VPS + FRP + LiMa Code Worker Closure

公开端到端 worker 烟雾已建立。分支 `codex/free-web-ai-probe`、`4e7d4a7`。HTTPS 聊天 `lima-postdeploy-ok`、Worker preflight `ready=true`、真实 worker 任务 `needs_review`。`local_router_start.bat` 默认密钥 `lima-local`。剩余门控: Kimi/TheOldLLM/MiMo/page-only 保持门控、always-on worker daemon 在门禁后。

## 2026-05-22 本地反向 AI 清单

本地审计确认: `D:\duckai` DuckAI 反向桥（`:4500`）、`:4505` SCNet-large（兼容）、`:4504` Kimi（配额耗尽）、`:4502` TheOldLLM（超时）、`:4503` g4f wrapper。文档: `docs/LOCAL_REVERSE_AI_STATUS.md`。

## 2026-05-22 DuckAI 和 SCNet-Large 准入

- `http_caller._build_body` 支持 `no_system`（DuckAI 需要）
- DuckAI 注册含 `ddg_gpt5_mini`、`ddg_claude_haiku_45`、`ddg_tinfoil_gptoss_120b`，仅作为后期回退
- DuckAI 本地评估: `ddg_gpt4o_mini` 3/3、`ddg_gpt5_mini` 3/3、`ddg_claude_haiku_45` 2/3
- SCNet-large 本地: `scnet_large_ds_flash` 3/3 (987ms)、`scnet_large_ds_pro` 3/3 (3899ms)
- Kimi 仍 `anonymous_usage_exceeded`，TheOldLLM 仍超时

## 2026-05-22 Cloudflare Workers AI 路由

- 添加 `cfai_mistral`、Cloudflare 编码后端至 `router_v3` 和 `code_orchestrator`
- `router_v3.MAX_FALLBACKS` 5→8
- 评估: `cfai_qwen_coder` 1/1 (2166ms)、`cfai_deepseek_r1` 1/1 (6919ms)、`cfai_mistral` 0/1
- VPS 部署: 备份 + 路由顺序 `scnet_ds_flash→qwen235b→qwen30b→ds_pro→github_gpt4o→cf_qwen_coder→cfai_qwen_coder`。公开烟雾: `groq_gptoss_20b` 601ms

## 2026-05-22 Token 安全本地代理路由

- 添加 `runtime_topology.py`: `router_v3.select_backends` 过滤仅本地后端
- Kimi/TheOldLLM 本地脚本脱敏（`secret_redactor.js`）
- 公开烟雾: 精确 `topology-ok`（backend `longcat_chat`）

## 2026-05-22 Phase 完成

- IDE/Agent 验证: `docs/IDE_AGENT_VERIFICATION.md`、OpenAI `phase-complete-ok`（`scnet_ds_flash`）、Anthropic `ide-agent-complete`、Claude Code CLI `claude-cli-ok`
- 免费 Web AI 准入: DuckAI（后期回退）、HeckAI（`adapter_draft_pending`）、page-only（`sandbox_only`）
- 稳定性/路由: `route_scorer.py`（quality 45% + stability 25% + latency 15% + quota 10% + task-fit 5%）、`budget_manager.py` 配额分数
- VPS 部署备份: `complete-open-phases-20260522_214621`。验证: 聚焦 `86 passed`

## 2026-05-22 Claude Code 工具协议加固

Claude Code + LiMa 工具结果后报 `API returned empty or malformed (HTTP 200)`。根因: 上游免费后端返回空/畸形 `choices[0].message`，转换器产生空 Anthropic `content` 数组。修复: `server.py` 保证至少一个 content 块，测试: `4/4`。VPS 部署，Claude Code CLI 大文件工具循环 `deployed-read-ok`。

## 2026-05-22 本地 P0 路由器加固

- `access_guard.py`: 私有 API 通过 `LIMA_API_KEY`/`LIMA_API_KEYS` 认证
- 保护 `/v1/chat`、`/v1/messages`、`/api/live-key`、`/v1/status`、`/v1/images`
- `/health` 和 `/v1/models` 保持公开；admin 路由 503 fail-closed
- 图像尺寸上限 2048x2048；移除 Anthropic 流式后端页脚
- 验证: `112 passed`。VPS 部署，公开无认证 401

## 2026-05-23 代码质量加固

- 修复 vision 路由调用、Anthropic 请求统计时间戳、`_record_request` 锁、跟踪脚本密钥文字
- 拒绝: admin API 路由（P0 后已有防护）、deploy_v3 明文密码（不存在）、streaming 测试（已运行）
- 延期: 拆分 `server.py`、BACKENDS 单一来源、去重响应构建器、迁移 `smart_router.cb_*`
- 验证: 核心 `117 passed`。提交 `e231a5e` 移除剩余跟踪脚本凭证文字

## 2026-05-23 LiMa Code Worker 命令运行器

- `/lima connect`/`status`/`review`/`task <id>`/`next`/`work --once`/`work --loop --max-tasks <n>`
- 重要边界: Server 不执行 shell，LiMa Code 仅在防护本地工作区执行，`plan`/`review` 只读
- 公开端到端烟雾: task `4d6c02b3` → `needs_review`。验证: 全量 `377 passed, 7 skipped`

## 2026-05-23 自主 Worker v0.2 设计方向

LiMa 应走向 GenericAgent/Evolver/agency-agents 方向的受控自主: 技能增长映射到候选技能提取，进化映射到证据门控提升，角色分解映射到紧凑编码角色集。Server 保持 orchestrator/审计源，LiMa Code 仅接触允许列表仓库。

## 2026-05-23 LiMa Server 控制面 v0.3 / Worker Smoke v0.4

- v0.3: 持久 agent 任务审计摘要、最小管理审计视图、候选技能创建
- v0.4: `/agent/worker/preflight`、`/agent/worker/smoke-task`、`scripts/create_lima_smoke_task.py`
- 边界保留: Server 不执行 shell、不自动部署、不自动提升技能

## 2026-05-23 Web-Reverse 模型准入

- 安全规则: 仅合成公开提示；不得含私有代码/路径/密钥
- 29 个 web-reverse/本地代理后端广泛烟雾
- 结论: `scnet_large_ds_flash`/`scnet_large_ds_pro` `code_medium_candidate`；`kimi*`/`longcat_web` `code_floor_candidate`
- `http_caller._build_body()` 支持 `force_stream_param`

## 2026-05-23/24 后端注册表和密钥池关闭

- `backends.py` 共享能力/代理集源（`GFW_BACKENDS`、`VISION_BACKENDS` 等）
- `key_pool.py` 集成 `http_caller.py`: 提供商推断、成功/失败报告、环境启动 `LIMA_KEY_POOL_<PROVIDER>`
- VPS 部署: 提交 `659f484`。公开烟雾: `backend_registry_https_ok`

## 2026-05-24 端点和密钥池遥测 / LiMa Code 主仓库管理

- `routes/chat_endpoints.py` → `/v1/chat`、`routes/system_endpoints.py` → `/v1/models/health/status`
- `key_pool.pool_snapshot()` 操作遥测（脱敏密钥 ID）
- `deepcode-cli` 一级 Git 子模块，远程 `https://github.com/zhuguang-ZFG/deepcode-cli.git`
- `esp32S_XYZ` 一级 Git 子模块，产品仓库授权

## 2026-05-24 LiMa 直连 Device Gateway 与小智退役计划

- 长期架构: 修改 U8 固件直连 LiMa 原生协议，无小智服务器运行时依赖
- 规划路由: `/device/v1/ws`（WebSocket）、`/device/v1/health`、`/device/v1/events`、`/device/v1/tasks`
- 小智服务器可退役但不等价前不物理删除
- 实现: 首个 Device Gateway 代码切片（协议、认证、会话、意图、安全、任务模块），验证 `15 passed`
- esp32S_XYZ fake LiMa U8 客户端，验证 `5 passed`
- 并发支持: 线程安全会话注册表、任务存储、每设备待处理队列
- HA 存储边界: `DeviceTaskStore` 协议、内存/Redis/Postgres 适配器路径

## 2026-05-24 外部能力雷达（多批次）

多批次外部参考项目审查（Pyrefly、GitNexus、OpenClaw、PersonaPlex、ElatoAI、Qwen3-TTS、Agent-Reach、Quelmap 等），80+ 项目作为能力参考而非运行时依赖。硬规则: Skills 教 LiMa 如何工作，MCP 连接器授权行动地点；MCP 工具默认关闭。AGPL/GPL 代码仅概念参考。

## 2026-05-24 AI 工程能力图谱

12 个核心概念（提示工程、RAG、向量嵌入、Agent/工具调用、推理、记忆管理、流式/异步、推理优化、令牌/成本、微调/PEFT、LLM 评估、MLOps/部署）映射到 LiMa 具体门禁和可测量工程控制。

## 2026-05-30/31 LiMa Code CLI 适配与遥测路由防护

- LiMa Code CLI → Server: 支持 Anthropic SSE 解析、`/agent/learn/outcome` 路由部署
- 遥测驱动路由防护: `observability.routing_guard`（短期隔离、降级、跳过隔离当唯一后端）
- 聊天 JSON 防护: `/v1/chat` 和 `/v1/messages` 畸形 JSON 返回 400
- Tailscale: Windows↔VPS 直连（11ms），服务持久化
- Ops 摘要: `/v1/ops/summary`、`POST /v1/ops/backends/retire|reactivate|probe`
- VPS DNS/代理修复: Tailscale DNS 覆盖和过期代理环境变量导致假阴性提供商探测，修复后恢复 6 个后端

## 2026-06-09/10 设备模型路由与全项目文档刷新

- 显式 AI 绘图/写字机模型路由指南: `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md`
- `device_gateway/model_routing.py`: 云端设备任务路由角色（`device_control/write/draw/vector/unknown`）
- SVG 绘图提示要求路径命令+数值坐标证据
- esp32S_XYZ 提交 `a8d98e3` 添加 `route_policy` 至 Edge-B/Edge-C 模式
- 主仓库提交 `423bf3e` 推进子模块指针
- `docs/PROJECT_OPTIMIZATION_ROADMAP.md` 为活跃全项目优化路线图（智能设备转型后）
- 验证: 设备路由 `4 passed`、聚焦回归 `26 passed`、产品模式树 `validated=62 passed=62`
