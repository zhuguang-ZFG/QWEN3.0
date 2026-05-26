# Personal Coding Assistant Progress

> Created: 2026-05-22

## 2026-05-26 代码质量 P2 拆分（CQ-099）

- **H1 anthropic_stream**：拆为 `anthropic_stream_sse.py` + `anthropic_stream_branches.py`；facade ~195 行；`inject_deps` → `AnthropicStreamDeps` + `_require_deps()`
- **H2 device_gateway_ws**：拆为 `device_gateway_ws_handlers.py`；主循环 ~91 行
- **H4 streaming**：`bridge_stream` 迁至 `streaming_bridge.py`；`streaming.py` facade ~154 行
- **M1 scnet**：`scnet_send_message()` 模块级函数替代嵌套 `_send()`
- **L2**：`WebSocketDisconnect` 记录 debug 日志
- **已关闭（CQ-097）**：H3 `call_api`→`build_request_body`；L1 legacy print→logging；PLACEHOLDER 标记已移除
- **Deferred**：M2 收窄 `except Exception`；M3 router_http urllib→httpx 迁移
- **测试**：**1547 passed, 10 skipped**（+2 authority tests）

## 2026-05-26 Telegram 出站修复（TG-PROXY-099）

- **根因**：VPS `GFW_PROXY=127.0.0.1:7897` 依赖 FRP 隧道，但 `frpc.toml` 仅有 `redcode-api`，**未映射 7897** → 出站全失败；webhook 入站仍 200
- **修复**：① `telegram_bot` 代理失败回退直连（海外 VPS 场景）；② 补 `frp/frpc.toml` `gfw-proxy` remotePort=7897 并重启 frpc
- **验证**：VPS `getMe ok=True`，`send_message True`（2026-05-26）

## 2026-05-26 安全/质量审查修复（CQ-098）

- **P1 store_promote**：`get_db_path()` / `set_db_path()` 调用时解析 DB 路径；`store_promote` 经 `store_db._get_conn()` 访问，修复 eval apply 测试隔离
- **P1 finance_math**：`lima_fc_tools/safe_math.py` AST 求值（长度/深度/指数上限），替换 `eval()`
- **P1 admin retrain**：异步 job + single-flight lock + `asyncio.wait_for` 超时（默认 600s）
- **P2 Telegram**：operator 命令失败返回稳定错误码消息，详细异常仅写日志
- **P2 admin_stats**：复用 `ops_metrics._backend_call_detail` 兼容整数 legacy 计数
- **P2 debug_routing\***：工作区未找到文件；`.gitignore` 已忽略
- **测试**：**1544 passed, 10 skipped**（含 `test_eval_apply_is_idempotent_*`、`test_safe_math`、`test_admin_stats`）

## 2026-05-26 代码质量审查修复（CQ-097）

- **HIGH**：`router_http.call_api()` 改为复用 `build_request_body()`，消除与 stream 路径的重复 body 构建
- **MEDIUM**：`router_http*` legacy 模块 `print(stderr)` → `logging`；统一 `UNAVAILABLE_USER_MESSAGE` 常量
- **LOW**：移除 `anthropic_stream.py` 中 `PLACEHOLDER_*` 分隔标记
- **Deferred**：`anthropic_stream()` ~170 行拆分（async generator 状态传递，单独切片）
- **测试**：+1 `test_call_api_uses_build_request_body`；全量 **1539 passed, 10 skipped**

## 2026-05-26 CQ-096 拆分代码 VPS 验证（DG-DEPLOY-096）

- **部署**：`scripts/deploy_cq096_split.py` → 7 文件上传 + `systemctl restart lima-router`
- **VPS loopback**：`/health` ok；`/device/v1/health` → `backend=redis`，`listener_alive=True`
- **公网 smoke**：`scripts/smoke_device_gateway_public.py` → **4/4 passed**
  - wss：`drained=1`，full fake-u8 loop
  - tasks：`task_id=task-000015`
- **本地测试**：`test_device_gateway_routes` + `test_request_pipeline_authority` → **29 passed**

## 2026-05-26 Device Gateway 公网 smoke（DG-SMOKE-096）

- **脚本**：`scripts/smoke_device_gateway_public.py`（health → WSS drain+fake-u8 → tasks → events）
- **目标**：`https://chat.donglicao.com/device/v1/*`（未部署 CQ-096 拆分，公网仍跑既有代码）
- **结果**：**4/4 passed**
  - health：`backend=redis`，`listener_alive=True`，`auth_configured=True`
  - wss：`drained=0`，frames=`hello_ack,heartbeat_ack,motion_task,motion_event_ack,motion_event_ack`
  - tasks：`status=queued`，`task_id=task-000013`
  - events：`motion_event_ack`，`phase=progress`
- **修复**：WSS 前 drain 积压 `motion_task`（避免 fake-u8 在 heartbeat 阶段收到历史队列任务）
- **残余**：若 HTTP 先入队再连 WSS 且无 drain，fake-u8 可能因队列积压失败；smoke 顺序已改为 WSS 先于 tasks

## 2026-05-26 项目记忆详细更新（CQ-091）

- **`docs/LIMA_MEMORY.md`：** 顶部 Agent 记忆索引；**2026-05-26 consolidated state**（战略方向、微信退役表、代码质量 P0/P1.3、文档对齐、VPS 快照、四线 backlog、REQUEST_PIPELINE、子模块锚点、运维脚本、常见误判）；Active Runtime Files 增补 `http_body_limit`、`channel_gateway`、cleanup 脚本；PROD-008 表述修正。
- **`docs/TECHNICAL_ARCHITECTURE.md`：** 当前个人助手架构节 + 历史图说明。
- **`STATUS.md` / `findings.md`：** 测试基线 **1530 passed, 10 skipped**；Code quality 行。
- **Tests：** 文档-only；基线证据 commit `57ea35a`。

## 2026-05-26 代码质量 P2（CQ-096）

- **P2.1 device_gateway**：`device_gateway_dispatch.py` + `device_gateway_ws.py`；HTTP 路由 `device_gateway.py` 172 行
- **P2.1 router_http**：`router_http_body/scnet/vision.py` 子模块；facade `router_http.py` ~200 行
- **测试**：+2 authority tests；全量 **1538 passed, 10 skipped**

## 2026-05-26 代码质量 P2（CQ-095）

- **P2.1**：`code_orchestrator_context.py` 拆分上下文/分层/池；`code_orchestrator.py` 保留执行管线（~210 行）
- **P2.1**：`routes/agent_task_evolution.py` 拆分 skill promote 路由；`agent_tasks.py` <300 行
- **P2.2**：`tests/test_request_pipeline_authority.py` 守卫 REF-005 模块权威
- **P2.3**：`tests/README.md` 测试归属索引
- **P1.3 batch4**（CQ-094）同批提交：voice/channel/request 静默 catch
- **测试**：全量 **1536 passed, 10 skipped**（+6 authority tests）

## 2026-05-26 代码质量 P1.3（第四批，CQ-094）

- **范围**：P1.3 剩余项 — voice/approval/channel/request 路径
- **文件**：`voice_gateway.py`, `agent_runtime/approval_session.py`, `channel_gateway/public_apis.py`, `channel_gateway/media_inbound.py`, `routes/request_tracking.py`
- **测试**：focused 41 passed；全量 **1530 passed, 10 skipped**

## 2026-05-26 代码质量 P1.3（第三批，CQ-093）

- **范围**：`agent_runtime/*` audit/emit 路径 + `orchestrate` / `speculative` / `router_http` 静默 catch
- **文件**：`real_executor`, `workspace_sandbox`, `tool_gateway_adapter`, `approval`, `events`, `orchestrate.py`, `speculative.py`, `router_http.py`
- **测试**：全量 **1530 passed, 10 skipped**

## 2026-05-26 代码质量 P1.3（第二批，CQ-092）

- **范围**：生产热路径静默 `except` → 可观测日志（不记录 prompt/token）
- **文件**：`streaming.py`、`routes/anthropic_stream.py`、`routes/chat_post_closeout.py`（补全 `persist_session_memory`）、`tool_gateway/audit.py`、`agent_runtime/feature_flags.py`、`device_gateway/intent.py`、`routes/device_gateway.py`
- **测试**：focused 85 passed；全量 **1530 passed, 10 skipped**

## 2026-05-26 代码质量 P1.3（首批，CQ-090）

- **P0 复核**：body limit / live-key / key_rotation / semantic cache / admin login 已在仓库落地（见 `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` 状态表）
- **P1.3**：`channel_gateway/media_inbound.py`、`health_recorder.py`、`routes/chat_post_closeout.py`、`routes/admin_api.py` 静默 `except` 改为可观测日志
- **前端**：`voice_call_live.html` fail-closed，不再尝试用 `/api/live-key` 拼 `?key=` URL
- **测试**：`pytest -q --ignore=active_model` → **1530 passed, 10 skipped**；Git `57ea35a`

## 2026-05-26 文档清理与四线里程碑

- **新增**：`docs/NEXT_MILESTONES.md`（编码后端 / LiMa Code / ESP32 / 代码质量优先级）
- **对齐**：`EXECUTION_PLAN.md`、`PERSONAL_CODING_ASSISTANT_PLAN.md`、`DOCUMENTATION_STATUS.md`、`STATUS.md`、`findings.md`（WX-088/089 Pending → Superseded）、`PLAN_CLOSURE_STATUS.md`
- **未改**：`task_plan.md`（用户契约；其中 server 拆分/BACKENDS 项已由 EXECUTION_PLAN 标关闭，见 NEXT_MILESTONES 对照表）

## 2026-05-25 微信通道全部退役

- **决定**：放弃所有微信方案（GeWe、OpenClaw、iLink/Hermes、WCF 小号等）
- **访客**：仅 `https://chat.donglicao.com`；`channel_gateway/invite.py` 只推网页
- **仓库**：`wechat_bridge/`、Hermes/WCF 脚本与相关测试迁至 `scripts/archive/wechat_retired/`；`docs/WECHAT_RETIRED.md`
- **部署**：`deploy_channel_gateway.py` 默认 `WECHAT_BRIDGE_ENABLED=0`
- **Git**：`c5511fb` on `codex/free-web-ai-probe`（已 push）
- **测试**：`test_wechat_wave1_ux` + `test_wechat_channel_smoke` + `test_channel_gateway_routes` 共 30 passed（本会话）
- **VPS**：`deploy_channel_gateway.py` 上传 invite/service；`.env` `WECHAT_BRIDGE_ENABLED=0`；`lima-weixin-ilink` stop+disable；`lima-router` active；`/health` ok
- **VPS 清理**：`scripts/cleanup_wechat_vps.py` 删除远程 `wechat_bridge/` 与 ilink 残留
- **仓库卫生**：`.gitignore` 忽略 `data/wechat_install/` 等；删除本地 GeWe/微信安装与登录缓存；微信 superpowers 计划迁至 `scripts/archive/wechat_retired/docs/plans/`

## 2026-05-25 WCF 小号客服（已并入退役，不再推进）

- 脚本与文档已归档至 `scripts/archive/wechat_retired/`

## 2026-05-25 OpenClaw Light Deploy Retired

- **决定**：放弃 VPS `lima-openclaw`（微信多人 ClawBot 扫码方案）
- **VPS 清理**：`scripts/cleanup_openclaw_vps.py` — service 已 disable，`:18789` 释放，`lima-weixin-ilink` / `lima-router` 保持 active
- **仓库**：OpenClaw 脚本与配置迁至 `scripts/archive/openclaw_retired/`
- **访客主推**：`https://chat.donglicao.com`；微信小号 + WCF 见 `docs/WECHAT_REAL_DEVICE_WINDOWS.md`

## 2026-05-25 VPS iLink Bridge Live (LiMa subsystem)

- **服务**：`lima-weixin-ilink` active，`python3.11` + `requirements-weixin-ilink.txt`（无 `[messaging]` 全家桶）
- **资源**：systemd `MemoryMax=384M` `CPUQuota=40%`；大脑仍为 `lima-router` :8080
- **本机**：已 `stop_weixin_lima_ilink.ps1`，避免双实例抢 token
- **部署**：`deploy_channel_gateway.py`（wave1）+ `deploy_weixin_ilink_vps.py`
- **提交**：`cd19648` wave1 UX；`04fcb50` slim deps；`b1d1ee0` py3.11 path fix

## 2026-05-25 GeWe VPS Stack Retired (9919 + 2531)

- **VPS**：`python scripts/cleanup_gewe_vps.py` — stopped `lima-wechat-sidecar`, removed `gewe` Docker, nginx `/gewe/*` unpatch, stripped `GEWECHAT_*` from `.env`（保留 `LIMA_WECHAT_SIDECAR_TOKEN` 供 iLink 桥）
- **仓库**：GeWe 脚本迁至 `scripts/archive/gewe_retired/`；删除生产用 `wechat_bridge/{sidecar_server,gewechat_client,callback_handler}.py`
- **文档**：`docs/WECHAT_CHANNEL_ILINK_ONLY.md`；`WECHAT_SIDECAR_JOINT_DEBUG.md` 标作废
- **生产微信**：仅 iLink 本机桥 + `/channel`

## 2026-05-25 CQ-090: WeChat G3 Session + Extra Tools + Owner Digest

- **新工具**：`/算` `/黄历` `/股票` `/地震`；**G3** `LIMA_CHANNEL_SESSION=1` 保留最近 6 轮（`LIMA_CHANNEL_SESSION_TURNS`）
- **主人**：`/简报`（天气+任务+后端+记忆摘要）、`/github owner/repo path`
- **生产接线**：`routes/channel_gateway` 创建 `ChannelService(wire_integrations=True)`
- **smoke**：`scripts/smoke_wechat_channel_gateway.py` 增加 auto-guest、/menu、/算、session 步骤
- **测试**：channel 套件 **90+ passed**；修复 smoke 测试 `inject_deps` 后被 `_reset_deps_for_test` 清掉的问题
- **VPS**：`python scripts/deploy_channel_gateway.py --smoke` → `channel_smoke_passed`（systemd `lima-router` + `.env` 开关已写入）

## 2026-05-25 CQ-089: WeChat Channel Public Tools (expanded APIs)

- **工具**：`/百科` `/天气` `/搜` `/新闻` `/翻译` `/汇率` `/时间` `/热搜` `/ip` `/读` `/menu`（中英别名）
- **开关**：`LIMA_CHANNEL_TOOLS=1`（默认关）；搜索优先 `TINYFISH_API_KEY`，否则 DuckDuckGo Instant；读链 TinyFish 或简易 HTML 抽取
- **配额**：SQLite `channel_tool_usage` 按日计数；主人 `LIMA_CHANNEL_OWNER_TOOL_MULT`（默认 3×）
- **测试**：`tests/test_channel_tools.py` + channel 套件 **82+ passed**

## 2026-05-25 CQ-088: WeChat Zero-Friction Guest Bind

- **行为**：扫码/加好友后直接发消息即可聊天；`LIMA_CHANNEL_AUTO_GUEST_BIND=1`（默认）自动创建 guest binding；`/bind <code>` 可选（操作员升级主人）
- **实现**：`ChannelStore.ensure_guest_binding()`；revoked 后再次发消息自动 reactivate；`service._auto_guest_bind_enabled()` 运行时读 env
- **文档**：`docs/WECHAT_CHANNEL_TOOLS_PLAN.md`
- **测试**：channel/wechat 相关 **75 passed**（`test_wechat_channel_smoke`、`test_channel_gateway_*`）
- **未做**：G1 访客工具（百科/天气/搜）、主人简报；`LIMA_CHANNEL_TOOLS` 仍默认关

## 2026-05-25 VPS Backups Cleared + No-Backup Deploy Policy

- 清理 `/opt/lima-router/backups/*`：释放 **~11G**，磁盘约 **17G 可用**（56% 使用）
- 部署脚本默认**不再**打 tar/file 备份；回滚走 GitHub
- 新增 `scripts/cleanup_vps_backups.py`

## 2026-05-25 VPS Bundle Deploy (post CQ-080/081/082)

- Deploy: `scripts/deploy_vps_bundle.py --no-backup`（VPS 磁盘曾 100%，清理 `backups/` 保留最近 2 项后可用 ~5.6G）
- Smoke: `prod_retrieval_trace_ok` + `ctx003_messages_ok` + health 8080
- 上传：security body limit、P3 路由拆分、retrieval、tool preflight 共 30+ 文件

## 2026-05-25 Repo Hygiene (CQ-082)

- `tests/test_repo_hygiene.py`：禁止 tracked/untracked 高风险后缀（`.db`/`.log`/`.pkl`/`.zip` 等）
- `deepcode-cli/.gitignore` 增加 `data/`；根 `.gitignore` 增加 `deepcode-cli/data/`、`data/models/*.pkl`
- `git rm --cached data/models/router_ml_model.pkl`（无代码引用）
- `scripts/archive/` + `deploy_cq014_slice11.py` 归档；`scripts/README.md` 标明 active 脚本

## 2026-05-25 CQ-014 Slice 12: P3 Long-Function Split

- `handle_chat` → `routes/chat_handler_dispatch.py`（~63 行入口）
- `anthropic_messages` → `routes/anthropic_messages_handler.py` + `anthropic_vision_sse.py`（~65 行入口）
- `anthropic_native_stream` → `routes/tool_forward_stream.py`（薄包装 ~6 行）
- 保留 `chat_handler` 上 `v3_route`/`quality_check` re-export 供测试 monkeypatch

## 2026-05-25 Review Fixes (CQ-080)

- **P1** `http_body_limit.py`：ASGI `receive` 累计字节硬截断；JSON API 缺 `Content-Length` 且非 chunked 时 400
- **P1** `tool_forward`：Tier1 非流式 `BackendError`/异常写入 `record_failure`
- **P2** `anthropic_format`：user 消息内 `tool_result` + 文本块并存时保留继续指令
- 测试：`test_http_body_limit.py`、`test_anthropic_format_tools.py`、`test_tool_forward_failures.py`

## 2026-05-25 CTX-003 VPS Deploy + /v1/messages Smoke

- Deploy: `scripts/deploy_ctx003.py` → file backup `ctx003-20260525_150658/files/`
- Smoke: `scripts/vps_run_messages_smoke.py` → **`ctx003_messages_ok`**
- Evidence: `preflight_body_ok=True`, `preflight_openai_ok=True`, `messages_status=200`, `stop_reason=tool_use`, `system_chars=340`

## 2026-05-25 CTX-003 Tool Route Preflight (CQ-079)

- `inject_anthropic_body_preflight`：Tier-2 Anthropic-native tool 请求写入 `body.system`
- `tool_call_forward`：与 Tier-1 共用 preflight 注入
- 测试：`tests/test_anthropic_preflight.py` 5 项 + tier2 payload 断言

## 2026-05-25 Admin Portable Paths (CQ-078)

- `routes/admin_state.py`：`FALLBACK_LOG` 复用 `request_tracking` 的 `LIMA_DATA_DIR` 解析
- `routes/admin_api.py`：`/api/retrain` 的 `cwd` 改为 repo root（VPS `/opt/lima-router` 可用）
- 测试：`tests/test_admin_paths.py` 4 项

## 2026-05-25 Deploy Manifest + P2 Cleanup

- **Deploy 清单**：`deploy_prod_retrieval.py` 补全 routing split（`routing_classifier/selector/executor`, `route_post_process`）+ retrieval stack（`entity_extraction`, `graph_retrieval`, `reranking`）；`--smoke` 选项；SSH 后台启动防阻塞
- **小清理**：`response_cleaner.py` 消除 `SyntaxWarning`（together/naga 品牌字面量）；`test_agent_eval.py` 可移植 repo root
- **VPS smoke**：`prod_retrieval_trace_ok`，`injected_chars=380`，entities `[routing_engine.py, health_tracker.py]`
- **Backup**：`prod-retrieval-20260525_145133`

## 2026-05-25 VPS Prod Retrieval Deploy + Trace Smoke

- Deploy: `scripts/deploy_prod_retrieval.py` → backup `prod-retrieval-20260525_143719`
- Smoke: `scripts/vps_run_retrieval_smoke.py` → **prod_retrieval_trace_ok**
- Evidence: admin trace `injected_chars=380`, entities `[health_tracker.py, routing_engine.py]`

## 2026-05-25 Post-RAG Milestone: CI Verify + Prod Retrieval + Server Bootstrap

- **CI 验证**：`gh` 不可用；新增 `scripts/run_ci_local.py` 镜像 `lima-ci.yml`；本地 RAG gate 3/3 PASS
- **生产检索接线**：`retrieval_corpus.py` + `production_index.py`；`retrieval_injection` vector 层走 prod index；`code_scanner.scan_files()` 对齐 prod 语料
- **server 收尾**：`server_bootstrap.py`（fallback/state/constants）；`server.py` ~131 行
- Design: `docs/PRODUCTION_RETRIEVAL_WIRING.md`
- `requirements_server.txt` 补 `pybreaker`、`python-multipart`（CI test job）
- Tests: **1451 passed, 10 skipped**

## 2026-05-25 RAG CI Gate Milestone Closeout

- 方向选择：`server.py` 已 ~181 行，CQ-014 达标；本里程碑接 **prod RAG CI gate**
- 新增 `run_all_fixture_gates()` + `DEFAULT_CI_FIXTURES`（core/routing/prod 三 fixture）
- CLI：`scripts/run_rag_eval_gate.py`（exit 0/1）
- CI：`.github/workflows/lima-ci.yml`（`test` + `rag-gate` jobs）
- pytest marker：`rag_gate`（4 条 gate 测试）
- Design: `docs/RAG_CI_GATE.md`
- Tests: **1447 passed, 10 skipped**; RAG gate **3/3 PASS**

## 2026-05-25 Identity Hardening Closeout

- Admin slice 11: `admin_state.py`, `admin_backends.py`, `admin_api.py`; `admin.py` ~68 lines (was ~330)
- Routing slice 11: `routing_classifier.py`, `routing_selector.py`, `routing_executor.py`; `routing_engine.py` ~215 lines (was ~447)
- Prod RAG: `lima_routing_prod.json` + `corpus_files` in `retrieval_eval_runner.resolve_corpus_files()`
- Design: `docs/CQ014_ADMIN_SLICE11.md`, `docs/CQ014_ROUTING_ENGINE_SLICE11.md`, `docs/RAG_OFFLINE_EVAL_FIXTURE.md` updated
- Tests: **1432 passed, 10 skipped** (+2 prod RAG tests)
- VPS backup: `/opt/lima-router/backups/cq014-slice11-*` (files uploaded + restart)
- Public smoke: **7/7** (health/models; no exact-chat token this session)

## 2026-05-25 RAG Routing Fixture + HTTP/Chat Slice 10 Closeout

- RAG: `lima_routing.json` + `routing_corpus/` stubs; `dual_layer` + `graph_relations` in runner
- HTTP slice 10: `http_sync.py`, `http_async.py`; `http_caller.py` ~38 lines
- Chat slice 10: `routes/chat_preflight.py`, `routes/chat_post_closeout.py`; `chat_handler.py` ~253 lines
- Tests: **1430 passed, 10 skipped** (+2 RAG routing tests)
- VPS backup: `/opt/lima-router/backups/cq014-rag-http-chat-20260525_142244/runtime-before.tgz`
- Public smoke: **12/12** with token `cq014_rag_http_chat_ok`

## 2026-05-25 CQ-014 Health Tracker Slice 9 Closeout

- Design: `docs/CQ014_HEALTH_TRACKER_SLICE.md`
- Extracted `health_failure_classifier.py`, `health_state.py`, `health_recorder.py`, `health_scoring.py`; `health_tracker.py` ~82 lines (was ~472)
- Tests: **1428 passed, 10 skipped**
- VPS backup: `/opt/lima-router/backups/cq014-health-tracker-20260525_141942/runtime-before.tgz`
- Public smoke: **12/12** with token `cq014_health_tracker_ok`
- **CQ-014 file-size targets complete** for smart_router / http_caller / health_tracker

## 2026-05-25 CQ-014 HTTP Caller Slice 8 Closeout

- Design: `docs/CQ014_HTTP_CALLER_SLICE.md`
- Extracted `http_errors.py`, `http_request_builder.py`, `http_response.py`, `http_stream.py`; `http_caller.py` ~390 lines (was ~763)
- Tests: **1428 passed, 10 skipped**
- VPS backup: `/opt/lima-router/backups/cq014-http-caller-20260525_141709/runtime-before.tgz`
- Public smoke: **12/12** with token `cq014_http_caller_ok`
- Residual CQ-014: `health_tracker.py`

## 2026-05-25 CQ-014 Smart Router Slice 7 Closeout

- Design: `docs/CQ014_SMART_ROUTER_SLICE.md` (updated slices 6–7)
- Slice 7: `router_prompt.py`, `router_http.py`, `router_image.py`; vision dedup via `vision_handler.py`; `smart_router.py` ~228 lines
- Slice 6 (prior): `router_circuit_breaker.py`, `router_intent.py`, `router_classifier.py`
- RAG fixture: `tests/fixtures/retrieval_eval/lima_core.json`, `context_pipeline/retrieval_eval_runner.py`
- Tests: **1428 passed, 10 skipped** (+27 vs prior closeout)
- VPS deploy: skipped (no `LIMA_DEPLOY_PASS` / `LIMA_DEPLOY_KEY_PATH` in session)
- Residual CQ-014: `http_caller.py`, `health_tracker.py`

## 2026-05-25 CQ-014 Smart Router Slice 6 + RAG Offline Eval Fixture

- Design: `docs/CQ014_SMART_ROUTER_SLICE.md`, `docs/RAG_OFFLINE_EVAL_FIXTURE.md`
- CQ-014 slice 6: extracted `router_circuit_breaker.py`, `router_intent.py`, `router_classifier.py`; `smart_router.py` ~740 lines (was ~1065)
- RAG fixture: `tests/fixtures/retrieval_eval/lima_core.json` + `context_pipeline/retrieval_eval_runner.py`
- Tests: **1421 passed, 10 skipped** (+18: router CB/classifier 12, retrieval fixture 6)
- Residual CQ-014: `smart_router.py` call_api/stream/vision blocks; `http_caller.py`, `health_tracker.py`

## 2026-05-25 GCP generative-ai Research + CQ-014 Fallback Slice

- Research: `docs/GCP_GENERATIVE_AI_RESEARCH.md` — **reference-only**, no port; llmevalkit/RAG eval patterns for Research Radar
- CQ-014 slice 5: `routes/chat_fallback.py` extracted from `chat_handler.py` (~315 lines)
- Tests: **1403 passed, 10 skipped** (chat_fallback: 2 new)
- VPS deploy backup: `/opt/lima-router/backups/cq014-chat-fallback-20260525_140609/runtime-before.tgz`
- Public smoke: **12/12** with token `cq014_chat_fallback_ok`

## 2026-05-25 CQ-014 Chat Handler Slice Closeout

- Design: `docs/CQ014_CHAT_HANDLER_SLICE.md`
- Extracted chat execution to `routes/chat_handler.py`, `routes/chat_stream.py`,
  `routes/chat_support.py`; `server.py` now ~180 lines (app wiring only)
- Tests: **1401 passed, 10 skipped** (chat handler: 3; prompt memory/stream footer fixes)
- VPS deploy backup: `/opt/lima-router/backups/cq014-chat-handler-20260525_140226/runtime-before.tgz`
- Public smoke: **12/12** with exact chat token `cq014_chat_handler_ok`
- Residual: `routes/chat_handler.py` still ~380 lines (fallback block); CQ-014 open

## 2026-05-25 CQ-014 Server Routes + HTTP Caller Concurrency Closeout

- Design: `docs/CQ014_SERVER_ROUTES_SLICE.md`, `docs/HTTP_CALLER_CONCURRENCY_TESTS.md`
- Extracted all `app.include_router(...)` wiring to `routes/route_registry.py`
- Added `tests/test_route_registry.py` and `tests/test_http_caller_concurrency.py`
- Tests: **1398 passed, 10 skipped** (route registry: 4; http_caller concurrency: 4)
- VPS deploy backup: `/opt/lima-router/backups/cq014-server-routes-20260525_135802/runtime-before.tgz`
- Public smoke: **12/12** with exact chat token `cq014_server_routes_ok`
- Residual: `server.py` still ~611 lines (chat orchestration); CQ-014 open for handler extraction

## 2026-05-25 CQ-014 Admin UI Slice Closeout

- Design: `docs/CQ014_ADMIN_UI_SLICE.md`
- Extracted `ADMIN_HTML`, `ADMIN_BODY`, `ADMIN_JS` from `routes/admin.py` into
  `routes/admin_ui.py` with `render_admin_dashboard()`
- `routes/admin.py` now API/auth only (~330 lines); `routes/admin_ui.py` ~292 lines
- Tests: **1390 passed, 10 skipped** (focused admin UI: 1 passed; admin CSRF/access: 14 passed)
- VPS deploy backup: `/opt/lima-router/backups/cq014-admin-ui-20260525_135412/runtime-before.tgz`
- Public smoke: **12/12** with exact chat token `cq014_admin_ui_ok`
- Residual: CQ-014 still open for `smart_router.py`, `server.py`, `http_caller.py`, `health_tracker.py`

## 2026-05-25 CQ-014 Post-Route Slice Closeout

- Design: `docs/CQ014_POST_ROUTE_SLICE.md`, `docs/REQUEST_PIPELINE_AUTHORITY.md`
- Extracted post-route integrations from `routing_engine.py` into `route_post_process.py`
- Replaced silent broad catches with warning logs in post-route path and `http_caller` prefix cache
- `routing_engine.py` reduced from ~409 to ~372 lines
- Tests: **1389 passed, 10 skipped** (focused post-route: 2 passed; routing_engine: 45 passed)
- VPS deploy backup: `/opt/lima-router/backups/cq014-post-route-20260525_134546/runtime-before.tgz`
- Public smoke: **12/12** with exact chat token `cq014_post_route_ok`
- Residual: CQ-014 still open for `smart_router.py`, `server.py`, `routes/admin.py`, `http_caller.py`, `health_tracker.py`

## 2026-05-25 Workspace Hygiene Cleanup

- Created external workspace `D:\LIMA-external\` for reference clones, hardware
  vendor trees, third-party apps, local runtime DB/tar artifacts, scratch scripts,
  and archives.
- Moved 60+ unrelated directories off `D:\GIT` (reference-repos, inkscape/bCNC,
  litellm-ref, llama.cpp, grblapp, etc.).
- Restored tracked `donglicao-site/` after misclassification.
- Updated `.gitignore` and added `docs/WORKSPACE_HYGIENE.md`.
- Remaining in-repo untracked LiMa work: web-reverse eval docs/scripts/tests.
- Locked at move time: `D:\GIT\frp\frpc.exe`, `data/agent_tasks.db*`,
  `data/semantic_cache.db` (ignored, migrate after stop).

## 2026-05-25 Quality Fix Review Closeout

- Fixed ops metrics `recent_agent_tasks` to read from `routes.agent_tasks._store`
  instead of the nonexistent `_agent_tasks_store.list_recent()`.
- Hardened auth:
  - `access_guard.py` requires strict `Bearer` prefix and constant-time key compare;
  - admin/agent/telegram admin checks share the same helpers;
  - admin mutating routes now use CSRF Origin/Referer hostname checks.
- Hardened admin UI:
  - backend capability badges now use `esc(c)`;
  - backend action buttons use `escJs(name)`.
- Hardened eval promotion:
  - `apply_promotion()` aborts when routing weight writes fail instead of silent pass.
- Channel gateway:
  - guest draw handler uses `device_gateway.path_pipeline.render_text_task()`;
  - owner device queue uses structured `project_to_motion_task()` voice tasks.
- Tests:
  - focused quality/auth/channel/ops tests: `48 passed`;
  - full suite: `1366 passed, 10 skipped`.
- VPS:
  - pre-commit archive deploy kept service healthy (`12/12` public smoke);
  - post-commit redeploy at `62ad977` with backup
    `/opt/lima-router/backups/quality-fix-20260525_133000/runtime-before.tgz`;
  - remote compile passed; `lima-router` active;
  - public online smoke `12/12` with exact token `quality_fix_62ad977_ok`.

## 2026-05-25 Current P0 Panorama

| ID | Status | Next Gate |
|---|---|---|
| PROD-003 | ESP32 firmware compile passed. | Hardware flash and real-device motion smoke. |
| PROD-004 | Path pipeline complete: stroke font, SVG path parser, path preview, safety bounds. | Keep using fake-U8/VPS smoke before hardware execution. |
| PROD-005 | Intent parser upgraded: deterministic regex, confidence, rejection reasons, gated LLM replanner. | Add outcome feedback only after P0.8 learning loop. |
| PROD-006 | LiMa Code artifact bundle complete. | Use `.lima/artifacts/<task_id>/` bundles as review and learning-loop evidence. |
| PROD-007 | Ops metrics endpoint deployed and public/private smoke-verified. | Keep adding correlation detail as real incidents expose gaps. |
| PROD-008 | Learning loop remains architecture-level follow-up. | Promote verified outcomes into memory, prompts, routing, and evals. |

## 2026-05-25 P0.4/P0.5/P0.7 VPS Deploy And Ops Metrics Fix

- Deployed review-fixed Device Gateway productivity slice to VPS
  `/opt/lima-router` from local commit `b22b3bd`, then found one production-only
  `/v1/ops/metrics` failure during authenticated smoke.
- Root cause: production `server._stats["backend_calls"]` stores backend values
  as dictionaries such as `{count, success, total_ms}`, while the new ops
  endpoint sorted them as numeric values and raised `TypeError` on `-dict`.
- Fix:
  - `routes/ops_metrics.py` now normalizes backend call counts for both legacy
    numeric values and production dict values;
  - response keeps `backend_calls` as compact `backend -> count` for dashboards;
  - response adds `backend_call_details` with `{count, success, total_ms}` for
    operator diagnostics.
- Regression tests:
  - `tests/test_ops_metrics.py` covers Starlette `app.state.stats`, server
    state exposure, and production-shaped backend call stats.
- Local verification:
  - `python -m pytest tests/test_ops_metrics.py tests/test_device_gateway_path_validator.py tests/test_device_gateway_protocol.py tests/test_device_gateway_protocol_families.py -q`:
    `31 passed`;
  - `python -m py_compile routes/ops_metrics.py`: passed.
- VPS deployment evidence:
  - full slice backup before archive overlay:
    `/opt/lima-router/backups/p04-review-20260525_080630/runtime-before.tar`;
  - ops metrics hotfix backup:
    `/opt/lima-router/backups/ops-metrics-fix-20260525_081216/runtime-before.tar`;
  - remote compile used `/usr/local/bin/python3.10`;
  - `systemctl is-active lima-router`: `active`;
  - VPS-local `/health`: `status=ok`;
  - VPS-local `/device/v1/health`: Redis task store, Redis session bus,
    `listener_alive=true`;
  - VPS-local `/v1/ops/metrics`: HTTP 200 with `backend_calls` and
    `backend_call_details`.
- Public verification:
  - `python scripts/smoke_online_distributions.py --api-key lima-local --chat-exact p04_review_ok`:
    `12/12 checks passed`;
  - public `/v1/ops/metrics` with private bearer auth returned HTTP 200 and
    live stats;
  - Device Gateway task smoke for `write LiMa` returned `capability=run_path`
    with a complete `preview_svg` ending in `</svg>`;
  - Device Gateway task smoke for `home` returned `capability=home` with no
    task error;
  - temporary Redis queues for `codex-smoke-p04` were deleted afterward
    (`pending_len=0`, `processing_len=0`).
- Residual risk:
  - PROD-003 ESP32 firmware compile has passed; hardware flashing and
    real-device smoke remain pending;
  - Postgres remains deferred for audit/history and is not required for current
    realtime WebSocket task delivery.

## 2026-05-25 PROD-006 LiMa Code Artifact Bundle

- Advanced LiMa Code to `8e680ea` (`feat(lima): add artifact bundle for plan/test/ship/review commands`).
- Artifact output location: `.lima/artifacts/<task_id>/`.
- Command outputs:
  - `/lima plan`: `plan.md`, `context.json`, `risks.md` with git diff,
    recent files, `AGENTS.md` rules, existing risks, and suggested slice;
  - `/lima test`: `tests.json` with command, exit code, duration, stdout, and
    stderr;
  - `/lima review`: `review.md`, `diff.patch` with changed files and findings;
  - `/lima ship`: `ship.md`, `diff.patch` with changed files, test results,
    residual risks, rollback notes, commit summary, and review checklist.
- Outcome:
  - people and LiMa Server can review structured artifacts directly;
  - terminal scrollback is no longer the only source of execution evidence;
  - PROD-006 is complete and becomes the evidence source for PROD-008.
- Verification:
  - LiMa Code: `0 fail, 6 skipped`;
  - LiMa Server: `1240 passed, 8 skipped`.

## 2026-05-25 P0.4/P0.5/P0.7 Review Fixes

- Reviewed `e3dbb9b` (`feat(device-gateway): p0.4 path pipeline + p0.5 intent parser + p0.7 ops metrics`).
- Fixed preview artifact preservation: `preview_svg` is no longer truncated to
  120 chars during Device Gateway validation, so task snapshots retain a
  complete operator/replay SVG.
- Fixed control command projection: `home`, `pause`, `resume`, `stop`, and
  `get_device_info` are now admitted motion-family capabilities and produce
  control `motion_task` payloads instead of failed `run_path` placeholders.
- Fixed `/v1/ops/metrics`: Starlette `app.state` is read correctly, and
  `server.py` exposes the live `_stats` object through `app.state.stats`.
- Added regression coverage in `tests/test_device_gateway_path_validator.py`,
  `tests/test_device_gateway_protocol.py`,
  `tests/test_device_gateway_protocol_families.py`, and
  `tests/test_ops_metrics.py`.
- Verification so far:
  - focused path/protocol/ops suite: `30 passed`;
  - device/agent subset: `80 passed`;
  - touched Python compile passed;
  - full suite: `1239 passed, 8 skipped`.

## 2026-05-25 XianyuAutoAgent Reference Execution Notes

- Reviewed `shaxiu/XianyuAutoAgent` at revision `77b1e4c`.
- Decision: medium-high reference value as a vertical always-on business agent,
  but concept-only for LiMa because the project is GPL-3.0 and its useful
  platform layer depends on cookies/private protocol behavior.
- Added `docs/reference/XIANYU_AUTO_AGENT_EXECUTION_NOTES.md`.
- The execution notes translate the reference into LiMa-owned slices:
  channel connector boundary, session state, intent router, expert agents,
  manual takeover, WebSocket health, prompt profiles, audit events, ops metrics,
  and gated messaging connectors.
- Updated `docs/REFERENCE_IMPLEMENTATION_LEDGER.md` and
  `docs/DOCUMENTATION_STATUS.md` so future sessions can find the reference and
  remember not to copy code or prompts.
- Priority retained: P0.2 real Device Gateway path/text/SVG execution remains
  ahead of WeChat or social-channel connector work.

## 2026-05-25 P0.1 ESP32 Motion Executor Contract — Deployed

- Review fixes applied after the initial implementation summary:
  - `device_gateway.protocol.validate_motion_event()` now preserves nested
    `error` and normalizes ESP32 firmware `error_code`/`error_message` into
    the same stored `error` shape;
  - `/device/v1/tasks` and WebSocket transcript handling return validation
    failures without queueing or dispatching invalid tasks;
  - tests cover firmware-style error preservation, invalid HTTP task
    non-queueing, and invalid WebSocket transcript non-dispatch.
- Local verification:
  - `python -m pytest tests/test_device_gateway_motion_contract.py tests/test_device_gateway_path_validator.py tests/test_device_gateway_routes.py tests/test_device_gateway_store.py tests/test_device_gateway_redis_store.py -q --ignore=active_model`:
    `49 passed`;
  - `python -m py_compile device_gateway/protocol.py device_gateway/path_validator.py device_gateway/tasks.py device_gateway/protocol_families.py routes/device_gateway.py`:
    passed;
  - full suite: `1218 passed, 8 skipped`.
- VPS deployment completed:
  - deployed commit `4a7faed`;
  - backup:
    `/opt/lima-router/backups/p01-motion-contract-20260525_072701/runtime-before.tgz`;
  - remote compile used `/usr/local/bin/python3.10` because system `python3`
    is 3.6.8, while the systemd service runs Python 3.10;
  - `lima-router` restarted active and `/health` returned `status=ok`.
- Public verification:
  - online distribution smoke passed `12/12` with exact chat token
    `p01_motion_contract_ok`;
  - HTTP firmware-style failure event returned `motion_event_ack` for
    `task-p01-fw-fail-2` with phase `failed`;
  - fake-U8 WSS success loop on `dev-joint-1` reached `progress` and `done`;
  - fake-U8 WSS failure loop on `dev-ha-cross` reached `accepted` and `failed`
    with `E_MISSING_PATH`.
- ESP32 follow-up:
  - fake-U8 initially failed against local `websockets==15.0.1` because the API
    now expects `additional_headers` instead of `extra_headers`;
  - fixed compatibility in `esp32S_XYZ` commit `160e526` and advanced the parent
    submodule pointer.

- Slice 1: Server error codes + protocol contract.
  - Added `MotionErrorCode` enum (8 codes: E_UNSUPPORTED_CAPABILITY, E_MISSING_PATH,
    E_BAD_PARAMS, E_U1_UNAVAILABLE, E_DEVICE_UPDATING, E_EXECUTION_FAILED,
    E_UNSUPPORTED_BOARD, E_TIMEOUT) to `device_gateway/protocol_families.py`.
  - Added `motion_failure_event()` builder and `validate_motion_task_lifecycle()`
    to `device_gateway/protocol.py`.
  - Extended fake-U8 (`esp32S_XYZ/tools/fake_lima_u8/app.py`) with `--test failure`
    and `--fail-with <code>` CLI flags plus `run_fake_u8_failure_script()`.
  - Tests: `tests/test_device_gateway_motion_contract.py` (9 tests).
  - Focused suite: 38 passed.
- Slice 2: Device Gateway path validation.
  - Created `device_gateway/path_validator.py` with `validate_run_path_params()`
    and `validate_capability_params()` — checks path bounds, feed limits, point
    counts, capability-to-required-field mapping.
  - Wired validation into `tasks.project_to_motion_task()`: invalid tasks now
    return `E_MISSING_PATH` / `E_BAD_PARAMS` / `E_UNSUPPORTED_CAPABILITY` at
    creation time with status "failed".
  - Tests: `tests/test_device_gateway_path_validator.py` (11 tests).
  - Focused suite: 33 passed.
- Slice 3: ESP32 default board fail-loud.
  - `board.cc`: Replaced empty `HandleMotionTaskJson()` with implementation that
    sends `failed` + `E_UNSUPPORTED_BOARD` via `Application::SendMotionEvent()`.
  - `board.h`: Added `virtual bool SupportsMotionTask() { return false; }`.
  - `dlc_motor_control_p1_ai_board.cc`: Added `SupportsMotionTask() override { return true; }`.
- Slice 4: Zhuguang board failure hardening.
  - Missing capability field now emits `E_UNSUPPORTED_CAPABILITY` before return.
  - Missing path/path_json now emits `E_MISSING_PATH` before return.
  - Unsupported capability (final else) now emits `E_UNSUPPORTED_CAPABILITY` with
    capability name in reason.
  - All three paths previously logged-and-returned silently.
- Slice 5: VPS deployment completed by Codex review pass.
- Initial owner-reported full suite before review fixes: **1213 passed, 8 skipped**.

## 2026-05-25 Reference Capability Implementation Closeout

- Completed Phase 1-8 of the reference capability implementation roadmap at
  `docs/superpowers/plans/2026-05-25-reference-capability-implementation-roadmap.md`.
- Phase 1: Normalized Reference Implementation Ledger with `blocked` status and
  explicit gated-item tracking.
- Phase 2: Consolidated retrieval injection to single authoritative path
  (`routing_engine.inject_retrieval_context()`); added index protocol,
  reranker protocol with fixture support, static-analysis lane, and
  source-quality scoring to retrieval traces.
- Phase 3: Normalized memory taxonomy; added recall source IDs to admin
  traces; added export/delete admin gate (`LIMA_MEMORY_ADMIN=1`);
  secret-bearing promotion evidence is rejected instead of redacted; mastery
  loop explicitly quarantined from hot-path routing.
- Phase 4: Added `RiskClass` enum and `rollback_owner` to `ToolDefinition`;
  dangerous tools fail closed at construction when risk_class or
  rollback_owner is missing; MCP provenance recorded in audit events; worker
  summary contract with required fields for LiMa Code task submissions.
- Phase 5: Created MCP access plane with connector policies, per-connector
  owner/allowlist/credential/timeout/audit, and foundation-vs-gated split.
- Phase 6: Added unified eval registry (`eval_registry.py`) linking
  model/route/fixture/score/promotion with JSONL persistence.
- Phase 8: Added protocol family schemas with per-family allowlists; only
  `motion` active, six families gated.
- Verification: `1193 passed, 8 skipped`; `git diff --check` passed;
  secret scan clean.
- No VPS deployment performed (no runtime behavior changed).

## 2026-05-25 Productivity Infrastructure Review

- Added the project-wide productivity/productization constraint to
  `AGENTS.md`.
- Added `docs/superpowers/plans/2026-05-25-productivity-infrastructure-review.md`
  as the active P0 roadmap for LiMa Server, LiMa Code, and ESP32 infrastructure
  strengthening.
- Key review conclusion:
  - LiMa has enough interfaces and reference-derived scaffolding for now;
  - the urgent work is observable execution closure, real Device Gateway
    path/text generation, LiMa Code review artifacts, and outcome-driven
    prompt/routing/memory feedback;
  - UI/visual/multimodal polish should follow only after the writing-machine
    and coding-worker loops can produce real work reliably.
- Updated `STATUS.md`, `docs/DOCUMENTATION_STATUS.md`, and `findings.md` so
  future sessions treat this as active product direction rather than a side
  note.

## 2026-05-25 LiMa Code Phase 7 Workflow Slice

- Advanced the `deepcode-cli` submodule from `278a5f7` to `ca51967`.
- Added local LiMa Code workflow stage commands:
  - `/lima plan` creates a local read-only planning task.
  - `/lima test [--cmd <command>]` runs a guarded local verification task and defaults to `npm test`.
  - `/lima ship` runs a local ship-readiness review and explicitly does not deploy or push.
- Kept the commands local-only: they use the guarded task runner, write local audit evidence, and do not submit results to LiMa Server.
- Verification in `D:\GIT\deepcode-cli`:
  - `npm.cmd run check` passed.
  - `npm.cmd test` passed with `431 passed, 6 skipped`.
  - `git diff --check` passed.
- Superseded by the PROD-006 artifact bundle at `8e680ea`, which adds
  structured `.lima/artifacts/<task_id>/` outputs for plan/test/review/ship.

## 2026-05-24 M0 Baseline & Review Harness

- Created `docs/DEVELOPER_CHECKLIST.md` with area-specific test commands.
- Created `docs/REVIEW_PACKET_TEMPLATE.md` for standardized slice reviews.
- Updated `task_plan.md` with 13-milestone implementation tracking table.
- Recorded 31 untracked out-of-scope files.
- Test baseline: 2 known pre-existing failures in `test_routing_engine.py`.
- M0 exit criteria met: a human can open one doc and know how to submit a slice.

## 2026-05-22 Website Baseline

- Started persistent plan for closing chat/open-platform website issues.
- Reused prior evidence instead of repeating known-good checks blindly.
- Confirmed previous open-platform token test succeeded:
  - New API DB found at `/opt/new-api/one-api.db`.
  - Enabled channels point to `http://localhost:8080`.

## Next Milestone: P0.1 ESP32 Motion Executor Contract

- Plan: `docs/superpowers/plans/2026-05-25-p0.1-esp32-motion-executor-contract.md`
- Five slices: Server error codes → Device Gateway path validation → ESP32
  default board fail-loud → Zhuguang board failure hardening → VPS deployment
  and smoke.
- Exit: missing-path or unsupported-capability motion task is visible as a
  structured failure event in Server task state within one smoke run.
- Waiting for owner to implement first slice.
  - Enabled tokens exist.
  - Local and public model/chat requests returned 200.
- Ran broader production audit for static assets, TLS/security headers, logs, backup, firewall exposure, and UI encoding.

## 2026-05-22 Production Audit And Closure

- Verified TLS expiry:
  - `chat.donglicao.com`: 2026-08-16 13:21:14 GMT.
  - `api.donglicao.com`: 2026-08-16 09:20:03 GMT.
- Found open platform title mojibake and fixed nginx sub_filter replacement.
- Found missing basic security headers and added them to chat/API nginx configs.
- Found chat `/quickstart/` serving fallback HTML for nested static paths and redirected it to `/`.
- Found direct public exposure risk for internal ports. Removed firewalld public ports `8080/3001` and added `eth0` direct reject rules for `3000/3001/3003/8080/8091`.
- Found New API backup cron overwriting a fixed dated file. Replaced it with dated daily backup and 14-day retention.
- Verified no regression:
  - Chat page/API non-stream/API stream all returned 200.
  - Open platform page/models/chat all returned 200 with valid token.
  - Internal localhost services still work for nginx.
  - Public direct internal ports are no longer reachable.

## 2026-05-22 Direction Reset

- User confirmed the product is a private personal coding assistant, not a commercial open platform.
- Added `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`.
- Removed billing/quota/usage commercial modules and commercial tests from the active worktree.
- Removed active payment, public registration, open-platform upgrade, commercial roadmap, and commercial readiness docs.
- Removed commercial wiring from `server.py`, `routes/admin.py`, and deploy preflight references.

## Next Personal Assistant Work

- Validate one real IDE or terminal-agent coding workflow against the private endpoint.
- Re-test failed providers when more backend keys/rate limits/local socket policy are healthy.

## 2026-05-22 Coding Backend Eval And Routing

- Added `coding_eval.py`, `scripts/eval_coding_backends.py`, and three coding fixtures under `evals/coding_cases/`.
- Added unit tests for case loading, candidate detection, grading, run failure handling, and Markdown report ranking.
- User challenged the first ranking as too narrow; expanded from the 10-backend shortlist to a full 85-candidate smoke.
- Broad smoke found 16 `code_review` passers.
- Ran full 3-case eval for those 16 passers:
  - 3/3 pass: `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`.
  - Fast 80+ score under 800ms: `cerebras_gptoss`, `groq_gptoss`, `mistral_small`.
  - Useful 2/3 fallback tier: `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `mistral_medium`, `featherless`.
- Updated `code_orchestrator.POOLS` and `router_v3.POOLS["code"]` so the wider evidence-backed coding pool is tried first.
- Added Continue/VS Code detection to `routing_engine` and `router_v3`.
- Local IDE-routing smoke passed: `ide_source=Continue` produced `request_type=code_standard`, `scenario=coding`, backend `scnet_large_ds_flash`, and a real response in 1406ms.

## 2026-05-22 VPS Deployment

- Deployed the coding-routing changes to `/opt/lima-router` on VPS `47.112.162.80`.
- Uploaded runtime files only: `router_v3.py`, `routing_engine.py`, and `code_orchestrator.py`.
- Remote backup directory: `/opt/lima-router/backups/deploy-20260522_175739`.
- Remote `py_compile` passed for `router_v3.py`, `routing_engine.py`, `code_orchestrator.py`, and `server.py`.
- Restarted `lima-router` through `systemctl`.
- VPS local `/health` returned 200.
- VPS local OpenAI-compatible coding smoke returned 200 and routed to `github_gpt4o`.
- Public `https://chat.donglicao.com/v1/chat/completions` smoke returned 200 and routed to `cerebras_gptoss`.

## 2026-05-22 Claude Code Speed Fix

- Found the Claude Code slow path: requests with `tools` use the Anthropic `/v1/messages` tool branch, not the normal coding pool.
- Reordered `TOOL_TIER1_BACKENDS` to front-load fast tool-compatible backends: `groq_gptoss_20b`, `cerebras_gptoss`, `groq_gptoss`, GitHub, and Mistral.
- Changed tool backend retry behavior so one request tries distinct backends instead of retrying the same failed backend repeatedly.
- Added a regression test for distinct fast tool backend iteration.
- Deployed `server.py` to VPS with backup at `/opt/lima-router/backups/speed-20260522_181808`.
- Remote compile and `/health` passed after restart.
- VPS local Anthropic tool smoke returned 200 in 393ms with a real `tool_use` from `groq_gptoss_20b`.
- Public `https://chat.donglicao.com/v1/messages` tool smoke returned 200 in 819ms with a real `tool_use`.

## 2026-05-22 IDE Context Preflight

- Created `docs/superpowers/plans/2026-05-22-ide-context-preflight.md` and executed it task-by-task.
- Added `lima_context.py` with request-local context digest extraction for IDE source, workspace hints, task shape, language, file paths, and tool/error signals.
- Added `tests/test_lima_context.py` covering digest extraction, trivial-chat no-op behavior, max length, tool result summarization, and `code_orchestrator.enhance_context` integration.
- Injected the digest into normal coding route prompts through `code_orchestrator.enhance_context`.
- Injected the digest into Claude Code Anthropic `/v1/messages` tool requests through `server._inject_anthropic_context_preflight`.
- Kept the fast tool backend order and distinct-backend retry behavior intact.
- Local verification passed:
  - `python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py`
  - `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py` -> `70 passed in 0.51s`
- Deployed `server.py`, `code_orchestrator.py`, and `lima_context.py` to VPS with backup at `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Remote compile and `/health` passed after `systemctl restart lima-router`.
- Synced a no-BOM `code_orchestrator.py` copy after local cleanup with backup at `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- Final remote compile and `/health` passed after restart.
- Final public Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## 2026-05-22 Free Model Routing Refresh

- Checked whether all SCNet and Kimi-family free models were actually in use.
- Confirmed registration exists in `backends.py`, but routing did not actively use all working free capacity.
- Ran VPS smoke for SCNet/Kimi-family candidates:
  - Working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`, `cf_kimi_k26`.
  - Not production-live in smoke: `scnet_minimax`, `scnet_large_ds_flash`, `scnet_large_ds_pro`, `stock_kimi_k2`, `kimi`, `kimi_thinking`, `kimi_search`.
- Updated `code_orchestrator.py` and `router_v3.py` so VPS-working free SCNet models are active fallback capacity.
- Kept local proxy models registered but late because VPS ports `4504` and `4505` refused connections.
- Added `docs/FREE_MODEL_ROUTING_STATUS.md`.
- Added `docs/LIMA_MEMORY.md` as the detailed durable memory document.
- Local verification after route changes passed: `71 passed in 0.52s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- `systemctl restart lima-router` initially hung because uvicorn was waiting for open connections to close; fixed by `systemctl kill -s SIGKILL lima-router`, `systemctl reset-failed lima-router`, then `systemctl start lima-router`.
- VPS `/health` returned 200 after recovery.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## 2026-05-22 SCNet/Kimi First-Tier Eval

- Created `docs/superpowers/plans/2026-05-22-free-model-first-tier-eval.md`.
- Ran a VPS-side three-case coding fixture against SCNet and Kimi-family candidates.
- SCNet direct first-tier winners:
  - `scnet_ds_flash`: 3/3, avg score 100, avg latency 3330ms.
  - `scnet_qwen235b`: 3/3, avg score 100, avg latency 4004ms.
  - `scnet_qwen30b`: 3/3, avg score 91, avg latency 2713ms.
  - `scnet_ds_pro`: 3/3, avg score 91, avg latency 4571ms.
- Kimi did not meet first-tier criteria:
  - `cf_kimi_k26`: 1/3, avg score 48, avg latency 7844ms.
  - local `kimi`, `kimi_thinking`, `kimi_search`: VPS proxy `4504` refused connections.
  - `stock_kimi_k2`: invalid response.
- Updated `code_orchestrator.py` and `router_v3.py` to move direct SCNet winners into coding first tier.
- Added `data/free_model_first_tier_eval.json` with the summary evidence.
- Local verification passed after routing change: `71 passed in 0.59s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Remote compile passed; `lima-router` restarted cleanly; VPS `/health` returned 200.
- VPS route order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## 2026-05-22 Local Proxy And FRP Closure

- Corrected the earlier proxy diagnosis: Kimi and SCNet-large are Windows-local services, not VPS-local services.
- Updated `local_router_start.bat` so it starts `D:\GIT\server.py` on Windows port `8080` and then starts `frpc.exe` if needed.
- Verified Windows `4505` SCNet-large models and chat completion locally.
- Verified Windows `4504` Kimi models locally; chat currently fails with `chat.anonymous_usage_exceeded`, so Kimi needs session refresh.
- Verified `frpc.exe` registers `redcode-api`.
- After VPS `8088/tcp` was opened, verified public FRP path:
  - `http://47.112.162.80:8088/health`: 200.
  - `http://47.112.162.80:8088/v1/models`: 200.
  - `http://47.112.162.80:8088/v1/chat/completions`: 200.
- Added `docs/LOCAL_PROXY_RUNTIME_STATUS.md`.

## 2026-05-22 Documentation And Next Roadmap

- Updated source-of-truth docs for the personal coding assistant direction.
- Added `docs/DOCUMENTATION_STATUS.md` to mark active docs versus historical commercial/open-platform docs.
- Added `docs/FREE_WEB_AI_EXPANSION_PLAN.md` for the next phase:
  - find more no-login web AI candidates like DuckAI and HeckAI;
  - improve token/session refresh, rate limiting, and quota handling;
  - optimize routing so free backends are selected by quality, health, latency, quota, and task fit.
- Added `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md` as the executable Superpowers implementation plan.
- Verification:
  - `git diff --check` passed with line-ending warnings only.
  - Core suite passed with `pytest --ignore=active_model`: `66 passed, 5 skipped`.
  - Plain pytest collection is blocked by stale junction `D:\GIT\active_model`.
  - Public FRP health/models/chat smokes on `http://47.112.162.80:8088` returned 200.

## 2026-05-22 Free Web AI Sandbox Probe

- Created branch `codex/free-web-ai-probe`.
- Added candidate registry:
  - `data/free_web_ai_candidates.json`
  - `docs/free-web-ai-candidates.md`
- Added sandbox probe harness:
  - `scripts/probe_free_web_ai.py`
  - `tests/test_free_web_ai_probe.py`
- TDD verification:
  - RED: `tests/test_free_web_ai_probe.py` failed with missing `scripts.probe_free_web_ai`.
  - GREEN: `4 passed in 0.05s`.
- Reachability probe:
  - Command: `D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20`.
  - Output: `data/free_web_ai_probe_results.json`.
  - Result: 6/6 candidate pages returned HTTP 200.
- Added failure-state classification to `health_tracker.py`.
- Updated `http_caller.py` so backend error text reaches `health_tracker.record_failure`.
- Focused verification passed: `6 passed in 0.07s` for new probe tests plus health-state tests.
- Full branch verification passed:
  - `72 passed, 5 skipped` with `pytest --ignore=active_model`.
  - JSON registry/results validation passed.
  - Probe dry-run listed six candidates.
  - FRP `/health` returned 200.

## 2026-05-22 Local Reverse AI Inventory

- Audited local ports/processes:
  - `4500` DuckAI, `4502` TheOldLLM, `4503` g4f, `4504` Kimi, `4505` SCNet-large, `8080` LiMa, `11434` Ollama.
- Verified DuckAI is already reversed in `D:\duckai`; `/v1/models` and user-only chat pass locally.
- Reproduced DuckAI LiMa-format blocker: empty OpenAI `system` message causes upstream 400.
- Verified SCNet-large `4505` models and chat pass locally.
- Verified Kimi `4504` models pass but chat returns `chat.anonymous_usage_exceeded`.
- Verified TheOldLLM `4502` models pass but local chat timed out after 30 seconds.
- Verified g4f `4503` default chat works, while one explicit PollinationsAI model mapping failed.
- Recorded inventory in:
  - `docs/LOCAL_REVERSE_AI_STATUS.md`
  - `data/local_reverse_ai_inventory.json`
  - `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md`
- Updated candidate docs so DuckAI is no longer treated as net-new reverse work and HeckAI is marked as an existing adapter draft.

## 2026-05-22 Local Reverse AI Integration

- Added RED/GREEN coverage for OpenAI `no_system` body construction.
- Updated `http_caller.py` so DuckAI-style OpenAI backends omit `role=system` and preserve non-empty system/IDE context in the first user message.
- Marked DuckAI backends `no_system` and registered the three missing local DuckAI models.
- Kept DuckAI models late in `router_v3.py` and `code_orchestrator.py` fallback order.
- Ran DuckAI local coding admission with dedicated output:
  - `data/ddg_route_admission_eval.json`
  - `docs/DDG_ROUTE_ADMISSION.md`
  - `ddg_gpt4o_mini` and `ddg_gpt5_mini`: 3/3.
  - `ddg_claude_haiku_45`: strict JSON failure.
  - `ddg_tinfoil_gptoss_120b`: upstream 500/cooldown.
- Confirmed Kimi chat still returns `chat.anonymous_usage_exceeded` and health state is `manual_refresh_required`.
- Ran SCNet-large local route eval with dedicated output:
  - `data/scnet_large_route_eval.json`
  - `docs/SCNET_LARGE_ROUTE_EVAL.md`
  - `scnet_large_ds_flash` and `scnet_large_ds_pro`: both 3/3.
- Reproduced TheOldLLM local `4502` 30s chat timeout and left it late until refresh/log safety plus upstream diagnosis are closed.

## 2026-05-22 Claude Code LiMa Tool-Loop Incident

- Reproduced healthy baseline:
  - Claude CLI simple prompt returned `claude-cli-ok`.
  - Claude CLI `Read D:\GIT\routing_engine.py` returned `read-loop-ok`.
  - Claude CLI stream-json `Read D:\GIT\server.py` returned `read-server-ok`.
- Identified unguarded protocol boundary in `server.py`: empty or malformed OpenAI-style upstream tool responses could become Anthropic HTTP 200 responses with empty `content`.
- Added failing regression tests in `tests/test_anthropic_tool_protocol.py`; initial run failed 4/4.
- Hardened `_convert_response_openai_to_anthropic()` and simulated Anthropic SSE `tool_use` block starts.
- Verification:
  - `tests/test_anthropic_tool_protocol.py`: `4 passed`.
  - Focused suite: `90 passed, 5 skipped`.
  - VPS backup: `/opt/lima-router/backups/claude-tool-protocol-20260522_220037`.
  - VPS health: 200.
  - Public `/v1/messages`: exact `deployed-msg-ok`.
  - Real Claude CLI large-file `Read`: exact `deployed-read-ok`.
  - FRP health: 200.

## 2026-05-22 P0 Router Hardening

- Created `docs/superpowers/plans/2026-05-22-p0-router-hardening.md` before code changes.
- Added RED tests:
  - `tests/test_access_guard.py` for private key parsing, missing-auth rejection, configured-key acceptance, unconfigured fail-closed behavior, and admin fail-closed behavior.
  - `tests/test_fallback_context.py` for preserving full messages during fallback backend retries.
- Verified RED: focused run failed because `access_guard` did not exist yet.
- Implemented `access_guard.py`:
  - Reads `LIMA_API_KEY`.
  - Reads comma-separated `LIMA_API_KEYS`.
  - Accepts either `Authorization: Bearer <key>` or raw `Authorization: <key>`.
  - Fails closed with 503 if no private key is configured.
  - Returns 401 for missing or invalid authorization.
- Wired the guard into `server.py` for:
  - `/v1/chat/completions`
  - `/v1/messages`
  - `/api/live-key`
  - `/v1/status`
- Kept `/health` and `/v1/models` unauthenticated for smoke checks and IDE model discovery.
- Changed `routes/admin.py` so missing `LIMA_ADMIN_TOKEN` returns 503 instead of allowing admin access.
- Updated `_try_backend()` to accept full `messages` and changed same-tier plus upgrade fallback call sites to pass `messages_to_dicts(req.messages)`.
- Fixed `_detect_ide()` so ordinary chat messages return an empty string instead of a truthy unknown marker.
- Added `tests/test_ide_detection.py` to prevent ordinary requests from being treated as IDE traffic.
- Protected `/v1/images/generations` with the same private API key guard.
- Added `tests/test_image_endpoint_guard.py` and capped image dimensions at 2048x2048.
- Added `tests/test_stream_footer.py` with RED/GREEN coverage for Anthropic speculative and fake stream paths.
- Removed client-visible backend footers from Anthropic streaming responses; backend names stay available to internal request logging.
- Reworked `test_streaming.py` so its async generator checks run via `asyncio.run()` instead of being skipped when `pytest-asyncio` is not installed/configured.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_fallback_context.py -q --ignore=active_model`: `6 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_ide_detection.py tests\test_image_endpoint_guard.py -q --ignore=active_model`: `4 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_stream_footer.py -q --ignore=active_model`: `2 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_streaming.py -q --ignore=active_model`: `5 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile access_guard.py server.py routes\admin.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile test_streaming.py`: passed.
  - Core suite with new tests: `112 passed`.
- Caveat:
  - This increment is local only and has not been deployed to VPS.

## 2026-05-22 Superpowers Plan Closure Review

- Reconciled historical Superpowers plan checkboxes:
  - `2026-05-22-cloudflare-workers-ai-routing.md`
  - `2026-05-22-token-safe-local-proxy-routing.md`
  - `2026-05-22-free-model-first-tier-eval.md`
- Added `docs/superpowers/PLAN_CLOSURE_STATUS.md` to classify each plan as closed, local closed, non-goal, or deferred risk.
- Current judgment:
  - Main `task_plan.md` phases are complete.
  - Historical Superpowers execution plans are checkbox-reconciled.
  - P0 router hardening was local closed at this point; it was deployed in the later explicit VPS deployment pass.

## 2026-05-22 P0 Router Hardening VPS Deployment

- Pushed commit `c4515d3` to `origin/codex/free-web-ai-probe`.
- Deployed P0 runtime files to VPS after explicit user approval:
  - `server.py`
  - `access_guard.py`
  - `routes/admin.py`
- Backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
- Remote `.env` did not have `LIMA_API_KEY` or `LIMA_API_KEYS`; added `LIMA_API_KEY` so the fail-closed private guard would not break authorized IDE/API clients.
- Remote compile passed for `server.py`, `access_guard.py`, and `routes/admin.py`.
- `lima-router` restarted active.
- First smoke immediately after restart hit a short connection-refused window before uvicorn listened; follow-up service status showed the process active and listening on `0.0.0.0:8080`.
- Public authorized OpenAI and Anthropic smokes initially returned 500.
- Root cause: VPS `health_tracker.py` was stale and lacked `get_backend_state()`, while current `routing_engine.py` calls it.
- Synced `health_tracker.py`:
  - Backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
  - Remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`.
  - `lima-router` restarted active.
- Final smoke:
  - Public `/v1/chat/completions` without auth returned 401.
  - Public `/v1/chat/completions` with auth returned exact `p0-deploy-ok`.
  - Public `/v1/messages` with auth returned exact `p0-msg-ok`.
  - FRP `http://47.112.162.80:8088/health` returned 200.

## 2026-05-23 Code Quality Hardening Evidence Closure

- Closed Task 5 of `docs/superpowers/plans/2026-05-22-code-quality-correctness-hardening.md` as a documentation and evidence-only pass.
- Accepted/fixed findings:
  - `smart_router._has_vision_content` was disconnected; the `cf_vision` image path is restored and covered by `tests/test_vision_routing.py`.
  - Anthropic vision stats now measure duration from the real request start; `tests/test_request_stats.py` covers the helper and `/v1/messages` image branch.
  - `_record_request()` performs IP location lookup outside `_stats_lock`, while stats writes stay inside the lock.
  - Local one-off deploy/debug/run/stress probes are protected by root-anchored `.gitignore`; tracked `scripts/` hardcoded `sk-` literals were replaced by environment reads.
- Rejected/outdated findings:
  - Admin API routes are not unauthenticated after P0; HTML admin shell review remains separate.
  - Current `deploy_v3.py` uses `LIMA_DEPLOY_PASS` or key path, not a plaintext deploy password.
  - The old `test_streaming.py` issue is stale because P0 executed and passed it.
- Deferred follow-ups:
  - Split `server.py`.
  - Establish a `BACKENDS` single source.
  - Deduplicate response-builder logic.
  - Migrate `smart_router.cb_*` state into `health_tracker`.
- Security note: any previously exposed tokens should be rotated; no token values were copied into docs.
- Deployment policy: this round is local-only unless the user explicitly requests deploy later.
- Verification:
  - `git -C D:\GIT diff --check`: passed without whitespace errors; warning-only CRLF notices appeared for unrelated dirty files `backends.py`, `budget_manager.py`, `capability_matrix.py`, and `router_v3.py`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile smart_router.py server.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model`: `5 passed`.
  - Core suite: `117 passed`.
  - `git -C D:\GIT grep -n "sk-" -- scripts`: no output, expected for no matches.

Follow-up after final review:

- Final reviewer found that the initial script scrub only covered `sk-` token shapes and missed non-`sk` OneAPI/admin/provider credential literals in tracked `scripts/`.
- Commit `e231a5e chore: remove remaining script credentials` moved those remaining tracked script credentials to environment-variable reads.
- Sanitized broader tracked-script scans passed without hardcoded credential literals, and `D:\GIT\venv\Scripts\python.exe -m compileall -q scripts` passed.
- Credentials that appeared in history still require rotation outside Git.

## 2026-05-23 Documentation Calibration And Reference Review

- Re-read the LiMa active code and source-of-truth docs after the latest hardening commits.
- Confirmed current branch `codex/free-web-ai-probe` and latest checked commit `8b86228`.
- Re-ran the LiMa target test suite:
  - `python -m pytest -q tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model`
  - Result: `382 passed, 8 skipped`.
- Calibrated module status at that time, superseded by later 2026-05-24 closure records:
  - Session Memory writes and compaction trigger are in the successful chat path.
  - Session Memory recall processor exists but is not the main `server.py` prompt-time path.
  - Graph retrieval/reranking was still compute-only at that time; later 2026-05-24 work closed this gap through `inject_retrieval_context()`.
  - Tool Gateway executor is hardened with `shell=False`, audit events, and copied HTTP args.
  - Admin UI auth is improved, but query-token login remains a later hardening target.
  - `ConcurrencyPool` existed and was tested, but key scheduling had not been replaced at that time; later 2026-05-24 work wired `key_pool.py` into `http_caller.py`.
- Reviewed external references:
  - OpenRAG is valuable for knowledge ingestion, retrieval traceability, MCP knowledge tools, and document parsing patterns.
  - Google Cloud always-on-memory-agent is the stronger near-term reference for LiMa's memory daemon and consolidation layer.
- Added `docs/REFERENCE_PROJECT_EVALUATION.md`.
- Updated active docs to point the next architecture step toward retrieval injection plus always-on typed memory rather than adding another large platform.

## 2026-05-23 Agent Autonomy Plan

- Created `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md` as the Superpowers implementation plan for gated LiMa autonomy.
- The plan evaluates OpenAI Agents SDK, Google ADK, GenericAgent, EvoMap Evolver, and Agency Agents against LiMa's current private coding-assistant architecture.
- Recommended sequence:
  - Retrieval and typed memory evidence before agents.
  - Agent workbench ledger before autonomous loops.
  - Five-agent local loop before any large persona library.
  - Skill/gene memory only after successful validated tasks.
  - GitHub/VPS operations behind explicit approval gates.
- Updated `docs/DOCUMENTATION_STATUS.md` to point to the new active plan.
- Added agent-reference findings to `findings.md`.
- No runtime code was changed in this pass.

## 2026-05-23 TechSpar Mastery Loop Plan

- Reviewed TechSpar as a reference for LiMa's evidence-driven improvement loop.
- Created `docs/superpowers/plans/2026-05-23-techspar-mastery-loop.md`.
- Positioned TechSpar as a mastery/profile/scheduling reference, not an agent runtime framework.
- Recommended a future `mastery_loop/` layer:
  - event adapters;
  - scoring;
  - weak-point extraction;
  - SQLite profile store;
  - SM-2-inspired review scheduling;
  - planner/tester recommendations;
  - admin trace.
- Updated `docs/DOCUMENTATION_STATUS.md` and `findings.md`.
- No runtime code was changed in this pass.

## 2026-05-23 LiMa Code Fork Start

- Owner forked LiMa Code to `https://github.com/zhuguang-ZFG/deepcode-cli.git`.
- Created `docs/superpowers/plans/2026-05-23-lima-code-vibe-coding.md`.
- Updated `docs/DOCUMENTATION_STATUS.md` and `findings.md`.
- First attempted network reachability to the fork failed from the sandboxed command environment with inability to connect to `github.com:443`; next step is to retry clone with approved network access.
- Retried with approved network access and cloned the fork into `D:\GIT\deepcode-cli`.
- Read LiMa Code `AGENTS.md`, `package.json`, README, configuration docs, provider settings, OpenAI client setup, tool executor, and bash handler.
- Confirmed LiMa Code is TypeScript/npm, OpenAI-compatible through `MODEL`, `BASE_URL`, and `API_KEY`, and has real local tool execution through `bash`.
- Added first LiMa Code fork changes:
  - `D:\GIT\deepcode-cli\docs\lima.md`
  - `D:\GIT\deepcode-cli\docs\lima_zh_CN.md`
  - README links in `README-en.md`, `README.md`, and `README-zh_CN.md`.
- LiMa Code validation:
  - `git -C D:\GIT\deepcode-cli diff --check`: passed.
  - Secret-shape scan over the new LiMa docs: no matches.
- Did not install npm dependencies or run `npm test` yet because this first change is documentation/config guidance only.
- No LiMa runtime code was changed in this pass.

## 2026-05-23 LiMa Code Rebrand Slice

- Renamed the active Superpowers plan to `docs/superpowers/plans/2026-05-23-lima-code-vibe-coding.md`.
- Rebranded the fork's user-facing product surface to LiMa Code:
  - npm package name: `lima-code`;
  - CLI bin: `lima-code`;
  - CLI help, TTY errors, update prompt, welcome screen, slash-command exit text, system prompt identity, MCP client name, and checkpoint author.
- Updated README and docs to promote `lima-code`.
- Kept `.deepcode` paths and `DEEPCODE_*` environment variables as a legacy compatibility layer for this first slice.
- No LiMa runtime code or VPS files were changed.

## 2026-05-23 LiMa Code Native Config Slice

- Added native LiMa Code config support in the fork:
  - `~/.lima-code/settings.json` and `<project>/.lima-code/settings.json` are preferred.
  - Legacy `~/.deepcode/settings.json` and `<project>/.deepcode/settings.json` remain readable fallbacks.
  - `LIMA_CODE_*` environment variables are preferred over legacy `DEEPCODE_*` variables.
  - `DEEPCODE_*` remains a fallback for old local profiles.
  - Model-selection writes create `.lima-code` settings by default, but update an existing project `.deepcode/settings.json` when that is the only project config.
- Updated CLI help, API-key error text, WebSearch config error text, README files, LiMa provider docs, MCP docs, notification docs, and configuration docs to promote `.lima-code` / `LIMA_CODE_*`.
- Added regression tests:
  - `D:\GIT\deepcode-cli\src\tests\app-settings-paths.test.ts`
  - expanded `D:\GIT\deepcode-cli\src\tests\settings-and-notify.test.ts`
  - updated `D:\GIT\deepcode-cli\src\tests\web-search-handler.test.ts`
- No LiMa runtime code or VPS files were changed.

## 2026-05-23 Agent Evolution Implementation

- Executed `docs/superpowers/plans/2026-05-23-lima-server-agent-evolution.md` (6 phases).
- **Phase 0: Quality Gates** — Fixed 7 review findings (P1/P2/P3), added typed memory validation, 60 regression tests.
- **Phase 1: Worker Contract** — `agent_contracts/task_contract.py` with AgentTaskRequest/Result schemas (12 tests).
- **Phase 2: Agent Role Layer** — 7 roles with permission gating, only `coder` can modify code (12 tests).
- **Phase 3: Evaluation Harness** — TaskScore, EvalResult, can_auto_promote() gate (6 tests).
- **Phase 4: Evolution Loop** — CandidateSkill extraction + dual-gate promotion (5 tests).
- **Phase 5: Server APIs** — 5 protected endpoints under `/agent/` (8 tests).
- **Total: 103 tests passing.** Server never executes shell; evolution is eval-gated + manually promoted.

## 2026-05-23 LiMa Code Worker Command Runner

- Added a real local command runner for LiMa Code:
  - `/lima connect` reports local Server configuration without exposing keys.
  - `/lima status` reports project and Server configuration state.
  - `/lima review` runs guarded local review mode over the current git diff.
  - `/lima task <task_id>` fetches a LiMa Server task, runs the guarded local task runner, writes local audit evidence, and submits the structured result back to Server.
- Wired the UI path so `/lima task <id>` is handled locally instead of being sent to the model as a chat prompt.
- Added `src/tests/lima-command-runner.test.ts`.
- Fixed Windows Bash timeout cleanup: after killing the process tree, LiMa Code now waits for process close before returning, preventing temp workspace `EPERM` cleanup failures while still ignoring post-timeout output.
- Added `.lima-code/` to LiMa Code `.gitignore` because local audit/settings data may contain sensitive runtime state.
- Public end-to-end smoke:
  - Created LiMa Server task `4d6c02b3` through `https://chat.donglicao.com/agent/tasks`.
  - Ran LiMa Code `/lima task 4d6c02b3` locally against `D:\GIT\deepcode-cli`.
  - Worker returned `needs_review`, listed `src/ui/App.tsx` and `src/ui/PromptInput.tsx`, and submitted the result.
  - Server detail confirmed `hasResult=true`; events endpoint returned `created,result_submitted`.
- Verification:
  - LiMa targeted tests: `41 passed`.
  - Tool handler regression tests: `22 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `368 passed, 7 skipped`.

## 2026-05-23 LiMa Code Single-Claim Worker

- Added `/lima next` to LiMa Code.
- `/lima next` claims the first pending `accepted` LiMa Server task through `GET /agent/tasks?status=accepted&limit=1`, runs it through the guarded local task runner, writes local audit evidence, and submits the result.
- If no pending task exists, it exits cleanly with a no-task message.
- Kept this as a single-task command; a daemon/poll loop remains a later explicit phase with backoff and stop controls.
- Public end-to-end smoke:
  - Created Server task `eb9410e1`.
  - Ran LiMa Code `/lima next` against `https://chat.donglicao.com`.
  - Worker returned `needs_review` and submitted the result.
  - Server detail confirmed `hasResult=true`; events endpoint returned `created,result_submitted`.
- Verification:
  - Parser/runner tests: `13 passed`.
  - LiMa worker targeted tests: `52 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `371 passed, 7 skipped`.

## 2026-05-23 LiMa Code Bounded Worker Loop

- Added `/lima work --once` and `/lima work --loop --max-tasks <n>`.
- Loop mode requires `--max-tasks` and caps it at 100 to avoid uncontrolled background execution.
- Defaults:
  - `--interval-ms`: `5000`
  - `--backoff-ms`: `30000`
- Loop stops when:
  - no pending task exists;
  - `maxTasks` is reached;
  - a task/fetch/submit failure occurs;
  - UI abort signal fires.
- Wired UI Ctrl+C/Esc to abort active LiMa worker commands through `AbortController`.
- Public smoke was intentionally run against a temporary empty directory instead of the real repo to avoid uploading local diff content:
  - Created Server tasks `3428f2b5` and `ae549d08`.
  - Ran `/lima work --loop --max-tasks 2 --interval-ms 1`.
  - Both tasks submitted `needs_review`.
  - Both event streams returned `created,result_submitted`.
  - `changedFileCount=0`.
- Verification:
  - Parser/runner tests: `19 passed`.
  - LiMa worker targeted tests: `58 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `377 passed, 7 skipped`.

## 2026-05-23 LiMa Autonomous Worker v0.2 Plan

- Added `docs/superpowers/plans/2026-05-23-lima-autonomous-worker-v02.md`.
- The plan explicitly follows the GenericAgent/Evolver/agency-agents direction as controlled autonomy:
  - GenericAgent-style repeated success becomes candidate skills.
  - Evolver-style self-improvement becomes evidence-gated promotion.
  - agency-agents-style roles remain a compact coding role set.
- The plan keeps LiMa Server as orchestrator and audit gate, and LiMa Code as the local allowlisted executor.
- Scope before real daemon mode:
  - Server claim/cancel/control/review/quarantine endpoints.
  - LiMa Code repo allowlist, worker budget, failure quarantine, stop marker, and audit command.
  - Safe temporary real-repo smoke for patch plus test plus result submission.
- This is design-only; no runtime code was changed in this entry.

## 2026-05-23 KERNEL Prompt Contract Todo

- Recorded KERNEL as a future `LiMa Task Prompt Contract v0.1` item in `task_plan.md`.
- Intended use:
  - Normalize Server-created agent tasks with `Context`, `Task`, `Constraints`, `Verify`, and `Output`.
  - Keep LiMa Code worker tasks single-purpose and easy to verify.
  - Reduce prompt drift during candidate skill extraction and evolution review.
- Source reference: Reddit PromptEngineering KERNEL framework post shared by the user.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Claude Code Infrastructure Todo

- Recorded `LiMa Code Hooks + Skill Auto-Activation v0.1` as a future item in `task_plan.md`.
- Source reference: the Claude Code infrastructure tips thread and `diet103/claude-code-infrastructure-showcase`.
- Intended use after autonomous worker v0.2 lifecycle controls:
  - Skill auto-activation rules based on prompt, file path, and content patterns.
  - Post-task, post-edit, and stop checkpoints for touched files, tests, failures, and review gates.
  - Worker-local dev docs under `.lima-code/dev/active/<task>/plan.md`, `context.md`, and `tasks.md`.
  - `/lima docs` and `/lima docs-update` commands.
  - Final worker summaries that explicitly list changed files, tests run, remaining risks, and review status.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Parlant Policy Guidelines Todo

- Recorded `LiMa Policy Guidelines Engine v0.1` as a future item in `task_plan.md`.
- Source reference: `emcie-co/parlant`.
- Intended use after hooks and skill auto-activation:
  - Condition-action guidelines for task policy, role activation, tool permission, and review gates.
  - Dependencies and exclusions between guidelines so incompatible modes cannot activate together.
  - Journey-style mapping to LiMa task lifecycle states.
  - Tool activation only when observations match task policy.
  - Explainability traces for why a guideline, skill, role, or tool was activated.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Autonomous Worker v0.2 Task 1

- Implemented the shared agent task lifecycle contract on Server and LiMa Code.
- Server `AgentTaskResult` now accepts lifecycle statuses: `claimed`, `approved`, `rejected`, `applied`, `cancel_requested`, `cancelled`, and `quarantined`.
- Server `AgentTaskRequest` now carries worker lifecycle metadata: `worker_id`, `lease_expires_at`, `cancel_requested`, and `failure_count`.
- LiMa Code TypeScript validation accepts the same statuses and optional metadata.
- Red-green evidence:
  - Server contract tests first failed on missing lifecycle metadata/statuses.
  - LiMa Code contract tests first failed on stripped metadata and missing statuses.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: `14 passed`.
  - `npm.cmd test -- src/tests/lima-agent-task-types.test.ts`: `380 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 2

- Implemented Server-side lifecycle gates for agent tasks.
- Added `/agent/tasks/{task_id}/claim` to assign `worker_id`, lease expiry, and transition the task to `running`.
- Added `/agent/tasks/{task_id}/cancel` and `/agent/tasks/{task_id}/control` so workers can observe cancellation state.
- Added `/agent/tasks/{task_id}/review` as the human review gate from `needs_review` to `approved` or `rejected`.
- Task result body validation now accepts the full lifecycle status set from the shared contract.
- `_append_event()` now keeps task envelopes and event streams aligned.
- Red-green evidence:
  - Route tests first failed with 404 for missing `claim`, `cancel`, and `review` endpoints.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py tests\test_agent_evolution.py -q --ignore=active_model`: `19 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: `14 passed`.

## 2026-05-23 Autonomous Worker v0.2 Task 3

- Implemented explicit LiMa Code repository allowlisting.
- Added `src/lima/repo-allowlist.ts` so the current workspace is allowed by default and sibling repositories require explicit `allowedRepos` configuration.
- Wired `workspace-guard.ts` to use the allowlist while preserving existing `allowedRoots` compatibility.
- Red-green evidence:
  - `npm.cmd test -- src/tests/lima-repo-allowlist.test.ts` first failed because `repo-allowlist.ts` did not exist.
- Verification:
  - `npm.cmd test -- src/tests/lima-repo-allowlist.test.ts src/tests/lima-workspace-guard.test.ts`: `385 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 4

- Implemented LiMa Code worker-session budgets.
- Added `src/lima/worker-budget.ts` to stop worker loops by max task count or max elapsed minutes.
- Added `/lima work --max-minutes <n>` parsing with a default 60-minute session budget.
- Wired the work loop to check budget before fetching the next task and to report the budget stop reason.
- Red-green evidence:
  - Budget tests first failed because `worker-budget.ts` did not exist.
  - Command tests first failed because `/lima work` did not carry `maxMinutes`.
  - Work-loop test first failed because the loop processed a second task after the time budget was exceeded.
- Verification:
  - `npm.cmd test -- src/tests/lima-worker-budget.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `391 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 5

- Implemented repeated-failure quarantine for LiMa Code worker tasks.
- Added `.lima-code/quarantine.json` state management through `src/lima/failure-quarantine.ts`.
- Added `LiMaAgentTaskClient.quarantineTask()` for `POST /agent/tasks/{task_id}/quarantine`.
- Wired worker loop failures so a task reaching 3 recorded failures is reported to Server as `quarantined`.
- Added Server `/agent/tasks/{task_id}/quarantine` endpoint and event emission.
- Red-green evidence:
  - Server route test first failed with `404` for the missing quarantine endpoint.
  - LiMa Code client test first failed because `quarantineTask` did not exist.
  - LiMa Code quarantine tests first failed because `failure-quarantine.ts` did not exist.
  - Worker loop test first failed because repeated failures were not quarantined.
- Verification:
  - `npm.cmd test -- src/tests/lima-failure-quarantine.test.ts src/tests/lima-agent-task-client.test.ts src/tests/lima-command-runner.test.ts`: `395 passed, 6 skipped`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py -q --ignore=active_model`: `15 passed`.
  - `npm.cmd run check`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile routes\agent_tasks.py`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 6

- Implemented LiMa Code worker stop control.
- Added `.lima-code/worker.stop.json` marker helpers in `src/lima/worker-control.ts`.
- Added `/lima daemon status` and `/lima daemon stop` commands.
- Wired the work loop to stop before fetching another task when the stop marker is present.
- Red-green evidence:
  - Command tests first failed because `/lima daemon` was not parsed.
  - Worker-control tests first failed because `worker-control.ts` did not exist.
  - Work-loop test first failed because `fetchPendingTask` still ran even with a stop marker.
- Verification:
  - `npm.cmd test -- src/tests/lima-worker-control.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `400 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 7

- Implemented LiMa Code audit viewing.
- Added `src/lima/audit-reader.ts` to read `.lima-code/audit.jsonl`, normalize `timestamp` and `created_at`, sort newest first, and format a compact summary.
- Added `/lima audit [--last <n>]` command parsing and runner output.
- Red-green evidence:
  - Audit reader tests first failed because `audit-reader.ts` did not exist.
  - Command tests first failed because `/lima audit` was not parsed.
  - Runner test first failed because audit commands returned usage text instead of audit entries.
- Verification:
  - `npm.cmd test -- src/tests/lima-audit-reader.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `405 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 8

- Added a real temporary git repository smoke test for LiMa Code patch mode.
- Patch mode now runs explicit `test_commands` after applying `patch_files` when the task allows the `test` tool.
- The submitted result now includes changed files, diff preview, test commands, and test results for patch-plus-test tasks.
- Closed an end-to-end contract gap found during smoke work:
  - Server `AgentTaskRequest` accepts `patch_files` and `test_commands`.
  - Server `/agent/tasks` preserves those fields in fetched task envelopes.
  - LiMa Code request validation preserves those fields instead of stripping them.
- Red-green evidence:
  - The local smoke first failed because patch mode submitted no test evidence.
  - Server contract tests first failed on missing `patch_files` support.
  - LiMa Code validation tests first failed because `patch_files` were stripped.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py -q --ignore=active_model`: `31 passed`.
  - `npm.cmd test -- src/tests/lima-agent-task-types.test.ts src/tests/lima-command-runner.test.ts`: `407 passed, 6 skipped`.
  - `npm.cmd run check`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile agent_contracts\task_contract.py routes\agent_tasks.py`: passed.
- VPS public smoke is still pending until this Server contract update is deployed. Do not treat patch-plus-test as live-verified until the VPS task endpoint returns `patch_files` and LiMa Code submits one passing `test_results` entry from a temporary repo.

Verification note:

- `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_agent_evolution.py -q --ignore=active_model` currently fails in `tests/test_agent_evolution.py::test_candidate_eval_passed_no_manual_flag_cannot_promote`.
- That failure is tied to the pre-existing dirty `agent_evolution/promote.py` worktree change and was not modified in this task.

## 2026-05-23 Code Quality Review Closeout

- Added `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md` as the durable Superpowers-style record for the review findings.
- Classified the current highest-priority issues as:
  - P0: full pytest collection is broken because `tests/test_agent_task_routes.py` imports stale `_events/_tasks` symbols.
  - P0: agent task claim can overwrite an active running worker lease.
  - P0: admin UI still exposes the long-lived admin token through query-token login and JavaScript injection.
  - P1: `/v1/models` auth policy needs an explicit decision.
  - P1: backend capability config and retrieval injection have duplication/drift.
  - P2: large hot-path files and dirty worktree hygiene remain maintenance risks.
- No production deployment was performed for this review pass.
- Verification evidence:
  - `python -m py_compile server.py routing_engine.py router_v3.py http_caller.py code_orchestrator.py routes\agent_tasks.py routes\admin.py routes\telegram.py tool_gateway\executor.py`: passed.
  - `python -m pytest -q --ignore=active_model`: failed during collection with `ImportError: cannot import name '_events' from 'routes.agent_tasks'`.

## 2026-05-23 Code Quality P0 Implementation Pass

- Restored the agent task route tests to the current SQLite-backed task store by adding `_reset_for_tests()` and removing stale `_events/_tasks` imports.
- Hardened `/agent/tasks/{task_id}/claim`:
  - active `claimed` or `running` leases now return 409 instead of being overwritten;
  - expired leases can be reclaimed by another worker;
  - claim updates task state and claim events under the store lock.
- Hardened the admin HTML shell:
  - query-token URLs no longer authenticate;
  - login sets a signed HttpOnly Secure session cookie derived from `LIMA_ADMIN_TOKEN`;
  - rendered admin HTML no longer injects the raw admin token or `const _ADMIN_TOKEN`.
- Verification:
  - `python -m pytest tests\test_agent_task_routes.py tests\test_agent_task_contract.py tests\test_access_guard.py -q --ignore=active_model`: `40 passed`.
  - `python -m py_compile routes\agent_tasks.py routes\admin.py tests\test_agent_task_routes.py tests\test_access_guard.py`: passed.
  - `git diff --check` for the touched files: passed, with line-ending warnings only.
  - `python -m pytest -q --ignore=active_model`: collection now succeeds; result is `345 passed, 8 failed, 8 skipped`.
- Remaining full-suite failures are outside this P0 slice: request stats lock expectation, stream footer tests expecting removed server helpers/behavior, and Telegram bot env/mock tests.
- No production deployment was performed.

## 2026-05-23 Continued Code Review Pass

- Continued review over tracked LiMa Python code and tests, excluding untracked reference repositories and local experiments.
- Fixed the remaining full-suite failures from the previous pass:
  - request stats tests now patch `routes.request_tracking`, the actual owner of request tracking state;
  - stream footer tests now patch `routes.anthropic_stream`, the actual owner of Anthropic streaming;
  - `telegram_bot.py` reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `GFW_PROXY` at call time instead of freezing them at import time.
- Rewrote `routes/images.py` to remove mojibake and use explicit `[\u4e00-\u9fff]` Chinese prompt detection.
- Added image endpoint regression coverage proving Chinese prompts receive the quality prefix in the generated Pollinations URL.
- Broad tracked-Python compile verification passed for 215 files.
- Verification:
  - `python -m pytest tests\test_image_endpoint_guard.py tests\test_request_stats.py tests\test_stream_footer.py tests\test_telegram_bot.py -q --ignore=active_model`: `20 passed`.
  - `python -m pytest -q --ignore=active_model`: `354 passed, 8 skipped`.
- Remaining non-failing cleanup:
  - `routes/telegram.py` uses deprecated FastAPI startup event wiring.
  - Telegram notify tests produce coroutine-not-awaited warnings when fire-and-forget is mocked.
  - Hot-path files remain oversized relative to the 300-line project target.
- No production deployment was performed.

## 2026-05-23 LiMa Server Control Plane v0.3

- Implemented the Server control-plane v0.3 plan locally.
- Agent task contract:
  - `AgentTaskResult.status` annotation now covers every `VALID_STATUSES` lifecycle value.
- Agent audit:
  - Added `/agent/audit` with bounded task summaries and no `diff_preview`.
  - Added protected `/admin/api/agent-audit`.
  - Added a minimal Agent Tasks audit panel to the admin HTML shell.
- Telegram review preparation:
  - Added `telegram_bot.parse_approval_callback()` for `approve:<task_id>` and `reject:<task_id>`.
  - Added `routes.agent_tasks.apply_task_review()` and made the HTTP review route use it.
- Candidate evolution:
  - Added candidate extraction from approved task evidence.
  - Approved `needs_review` results now create inactive candidate skills and record candidate creation events.
  - Promotion remains gated by eval pass plus manual flag.
- Contract smoke:
  - Added `scripts/smoke_agent_task_contract.py --dry-run`.
  - The script builds and validates matching Server task/result payloads without contacting a live Server.
- Verification:
  - `python -m py_compile agent_contracts\task_contract.py routes\agent_tasks.py routes\admin.py telegram_bot.py agent_evolution\candidates.py scripts\smoke_agent_task_contract.py`: passed.
  - `python -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_agent_evolution.py tests\test_telegram_bot.py tests\test_admin_agent_audit.py tests\test_agent_task_smoke_script.py -q --ignore=active_model`: `60 passed, 3 warnings`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: failed before collection because the venv lacks `pytest_asyncio`.
- Remaining warning cleanup:
  - Telegram notify tests still emit coroutine-not-awaited warnings when `_fire_and_forget` is mocked.
  - `routes/telegram.py` still uses FastAPI deprecated startup event wiring.
- No production deployment was performed.

## 2026-05-23 LiMa Real-Machine Worker Smoke v0.4

- Implemented the Server-side real-machine worker smoke plan locally.
- Added `/agent/worker/preflight`:
  - requires admin auth;
  - returns readiness, contract version, task counts, latest task id, and feature flags;
  - does not expose admin token values.
- Added `/agent/worker/smoke-task`:
  - default task is read-only `review` mode with `allowed_tools=["git_diff"]`;
  - `patch_readme` task is explicit, bounded to `README.md`, and runs only `node --version`;
  - Server still only creates task records and does not execute shell or mutate repositories.
- Added `scripts/create_lima_smoke_task.py`:
  - `--dry-run` prints only `/agent/worker/smoke-task` payload shape;
  - live mode reads `LIMA_CODE_SERVER_URL` and `LIMA_CODE_API_KEY` or CLI args;
  - output never prints API keys.
- Added `docs/LIMA_REAL_MACHINE_SMOKE.md` with `/lima doctor` as the first LiMa Code step.
- Verification:
  - `python -m pytest tests\test_agent_task_routes.py -q --ignore=active_model`: `24 passed`.
  - `python -m pytest tests\test_lima_smoke_task_script.py -q --ignore=active_model`: `2 passed`.
  - `python -m py_compile routes\agent_tasks.py tests\test_agent_task_routes.py scripts\create_lima_smoke_task.py tests\test_lima_smoke_task_script.py`: passed.
  - `Select-String -Path docs\LIMA_REAL_MACHINE_SMOKE.md -Pattern "zhuguang110|sk-|Bearer |query-token"`: no matches.
- Environment note:
  - `D:\GIT\venv\Scripts\python.exe -m pytest ...` still fails before collection because the venv lacks `pytest_asyncio`; system `python` was used for meaningful test evidence.
- No production deployment was performed.

## 2026-05-23 Web-Reverse Model Admission Batch

- Added a dedicated web-reverse/local-proxy admission path instead of directly promoting every web adapter into hot IDE routes.
- Added `web_reverse_eval.py`:
  - discovers registered web-reverse candidates from `data/local_reverse_ai_inventory.json` plus registry-only `localhost:45xx` web proxies;
  - uses synthetic public coding prompts only;
  - writes evidence-backed route promotion recommendations;
  - requires a full three-case batch before emitting route-candidate recommendations.
- Added `scripts/eval_web_reverse_models.py` with dry-run, explicit backend selection, JSON/Markdown outputs, and `--timeout-cap` for broad smoke batches.
- Added `tests/test_web_reverse_eval.py`.
- Full 29-backend smoke used only the public `public_python_bugfix` fixture:
  - passing: `scnet_large_ds_flash`, `scnet_large_ds_pro`, `kimi`, `kimi_thinking`, `kimi_search`, `longcat_web`, `longcat_web_research`;
  - DDG returned HTTP 530;
  - OldLLM returned HTTP 502;
  - `longcat_web_think` returned malformed/non-code output for the public Python fixture;
  - MiMo web is now correctly classified as cookie/auth failure, not JSON adapter failure.
- Phase 2 three-case eval:
  - `scnet_large_ds_flash`: `code_medium_candidate`, 3/3, avg 2363ms;
  - `scnet_large_ds_pro`: `code_medium_candidate`, 3/3, avg 3986ms;
  - `kimi`, `kimi_thinking`, `kimi_search`: `code_floor_candidate`, 2/3 each, failing strict JSON tool output;
  - `longcat_web`: `code_floor_candidate`, 2/3, failing strict JSON tool output;
  - `longcat_web_research`: not a coding route candidate in the current fixture set.
- Evidence files:
  - `data/web_reverse_model_smoke.json`
  - `docs/WEB_REVERSE_MODEL_SMOKE.md`
  - `data/web_reverse_model_eval.json`
  - `docs/WEB_REVERSE_MODEL_EVAL.md`
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile web_reverse_eval.py scripts\eval_web_reverse_models.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_web_reverse_eval.py -q --ignore=active_model`: `9 passed`.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --dry-run --timeout-cap 15`: listed 29 candidates without network calls.
- Environment note: installed missing `pytest-asyncio` into the local venv so the repo's existing `tests/conftest.py` can load.
- No production deployment was performed.

## 2026-05-23 Web-Reverse Non-JSON Adapter Fix

- Root cause:
  - LongCat/MiMo web proxies default `/v1/chat/completions` to `stream=True`.
  - LiMa non-stream `http_caller.call_api()` omitted `stream:false`, so these proxies returned SSE.
  - `call_api()` then tried to parse the SSE body as JSON and raised `Expecting value`.
- Fix:
  - Added `force_stream_param` support in `http_caller._build_body()`.
  - Set `force_stream_param: True` for `longcat_web`, `longcat_web_think`, `longcat_web_research`, `mimo_web`, `mimo_web_think`, and `mimo_web_flash`.
  - Added web-proxy control error markers to `response_cleaner`.
  - Added ASCII control-error strings in local `mimo_web_proxy.py` and `longcat_web_proxy.py` for future clean reports after proxy restart.
  - Added regression coverage in `test_http_caller.py` and `tests/test_web_reverse_eval.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile http_caller.py backends.py response_cleaner.py web_reverse_eval.py scripts\eval_web_reverse_models.py test_http_caller.py tests\test_web_reverse_eval.py mimo_web_proxy.py longcat_web_proxy.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_http_caller.py tests\test_web_reverse_eval.py -q --ignore=active_model`: `42 passed`.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --max-cases 1 --timeout-cap 12 ...`: refreshed 29-candidate smoke.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --backends scnet_large_ds_flash,scnet_large_ds_pro,kimi,kimi_thinking,kimi_search,longcat_web,longcat_web_research ...`: refreshed phase 2 eval.
- Current conclusion:
  - LongCat non-stream adapter path is fixed; `longcat_web` is now a `code_floor_candidate`.
  - MiMo adapter path is fixed enough to classify the real blocker: expired local cookie. Refresh/restart MiMo proxy before retesting.
- No production deployment was performed.

## 2026-05-23 Memory Daemon Closeout

- Closed the gap where documentation described Session Memory as request-path-only:
  - `server.py` already starts `session_memory.daemon` during FastAPI lifespan.
  - This round added lifecycle state, idempotent start, async stop/cancel, status reporting, dynamic env config, and a single-cycle runner.
- Added `scripts/memory_daemon_ctl.py`:
  - `status` prints daemon config/status as JSON.
  - `run-once` ingests `LIMA_MEMORY_INBOX` and consolidates sessions once outside `/v1/chat/completions`.
- Added tests proving:
  - inbox ingestion archives processed files and writes typed memories;
  - consolidation can run through `run_once(ingest=False, consolidate=True)` without a request;
  - `start_daemon()` is idempotent and `stop_daemon()` cancels the tracked task;
  - CLI `status` and `run-once` output JSON.
- Updated `STATUS.md`, `docs/LIMA_MEMORY.md`, and `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`.
- Remaining memory work after this daemon closeout was prompt-time recall; that is closed in the next section.
- No VPS deployment was performed in this local closeout.

## 2026-05-23 Prompt-Time Memory Recall

- Added `session_memory/prompt_recall.py` as the server-facing recall integration layer.
- `server.py` now runs prompt-time memory recall after trace creation and before token budget checks, user-identity adaptation, `smart_router.analyze()`, non-streaming `v3_route()`, OpenAI streaming, and fallback retry messages.
- The post-response SQLite write now uses the same header-derived memory session id when prompt recall is active, so future recall reads the same session that successful responses write.
- Trace/response evidence is metadata-only:
  - trace span: `prompt_memory_recall`;
  - OpenAI response meta: `x_lima_meta.memory_recall`;
  - recalled memory text is not copied into trace metadata.
- Added `tests/test_prompt_memory_recall.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile session_memory\prompt_recall.py server.py tests\test_prompt_memory_recall.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_prompt_memory_recall.py tests\test_session_memory.py tests\test_compactor.py tests\test_typed_memory.py -q --ignore=active_model`: `34 passed`.
  - Extended server regression with Anthropic protocol, fallback context, and streaming tests: `44 passed`.
  - `git diff --check`: passed with CRLF warnings only.
- No production deployment was performed.

## 2026-05-23 Global Code Quality Hardening

- Fixed admin auth import-order determinism by moving current-token decisions to runtime lookup and then extracting admin auth helpers.
- Removed hardcoded runtime secret literals from active runtime files and quarantined local-only MiMo TTS/debug script risk.
- Made web-reverse admission explicit in backend metadata and docs.
- Consolidated `routing_engine.route()` retrieval injection onto the shared `inject_retrieval_context()` path.
- Split admin agent audit into `routes/admin_agent_audit.py`.
- Extracted server prompt-context staging into `server_context.py`.
- Replaced Telegram router startup `on_event` with explicit lifespan startup and removed Telegram notify coroutine-not-awaited warnings.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m compileall -q server.py routing_engine.py router_v3.py http_caller.py backends.py response_cleaner.py context_pipeline session_memory routes tool_gateway scripts tests`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model`: `391 passed, 8 skipped`.
  - `git diff --check`: passed with CRLF warnings only.
- No production deployment was performed.

## 2026-05-23 Global Code Quality Follow-up P1

- Closed the remaining P1 blockers from the post-hardening review:
  - updated prompt tests for the new LiMa chat identity wording;
  - removed `mimo_web*` from default IDE/chat route pools while retaining sandbox-only backend metadata;
  - removed the untracked `fc_caller` dependency from the core `routing_engine.route()` path by restoring the committed route implementation and adding a regression test;
  - tracked `session_memory/prompt_recall.py` and added a repo-manifest regression;
  - narrowed response identity cleaning so normal third-party facts such as OpenAI/ChatGPT history are preserved.
- Verification:
  - Focused follow-up suite: `37 passed`.
  - `compileall` over runtime, routes, tools, scripts, and tests: passed.
  - Full pytest: `393 passed, 8 skipped`.
- No production deployment was performed.

## 2026-05-24 Chat Model Extraction Deploy

- Added regression contract `tests/test_chat_models.py`.
- Extracted `Message`, `ChatRequest`, and `extract_system_prompt` from `server.py` into `chat_models.py`.
- Preserved `server.Message`, `server.ChatRequest`, and `server.extract_system_prompt` as module-level imports for existing tests and callers.
- Verification:
  - `python -m py_compile server.py chat_models.py server_lifespan.py`: passed.
  - `python -m pytest tests/test_chat_models.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_access_guard.py tests/test_anthropic_tool_protocol.py -q --ignore=active_model`: `20 passed`.
  - `python -m pytest tests/test_agent_task_routes.py tests/test_access_guard.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_chat_models.py -q --ignore=active_model`: `40 passed`.
- VPS deployment:
  - backup `/opt/lima-router/backups/chat-models-extract-20260524_113220`;
  - uploaded `server.py` and `chat_models.py`;
  - remote `py_compile` and `import server; import chat_models` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `deploy_https_ok_1134`;
  - FRP chat returned exact `lima-chat-models-frp-ok`;
  - `/agent/worker/preflight` returned `ready=true`, latest task `cfcd3f2b`.

## 2026-05-24 Chat Request Helper Extraction Deploy

- Added regression contract `tests/test_chat_request_utils.py`.
- Extracted shared request-body helpers into `chat_request_utils.py`:
  - `extract_system_preview()` handles OpenAI `system` messages and Anthropic `system` strings/text blocks.
  - `extract_last_user_text()` handles string content and text blocks while ignoring image blocks.
- Replaced duplicate helper loops in the OpenAI `/v1/chat/completions` and Anthropic `/v1/messages` handlers without changing routing policy.
- Verification:
  - `python -m py_compile server.py chat_request_utils.py chat_models.py server_lifespan.py`: passed.
  - `python -m pytest tests/test_chat_models.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_access_guard.py tests/test_anthropic_tool_protocol.py tests/test_vision_routing.py -q --ignore=active_model`: `22 passed`.
  - `python -m pytest tests/test_agent_task_routes.py tests/test_access_guard.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_chat_models.py tests/test_chat_request_utils.py -q --ignore=active_model`: `45 passed`.
- VPS deployment:
  - backup `/opt/lima-router/backups/chat-request-utils-20260524_114403`;
  - uploaded `server.py` and `chat_request_utils.py`;
  - remote `py_compile` and `import server; import chat_request_utils` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `request_utils_https_ok`;
  - FRP chat returned exact `request_utils_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, latest task `cfcd3f2b`.

## 2026-05-24 Backend Registry And Key-Pool Deploy

- Closed the backend config/key-pool architecture backlog:
  - `backends.py` now owns shared proxy/capability sets and helper predicates.
  - `smart_router.py` uses `backends.GFW_BACKENDS` instead of a local duplicate.
  - `context_pipeline/reflection.py` uses the shared backend capability helpers instead of stale local sets.
  - `http_caller.py` now selects provider keys through `key_pool.py` and reports success/failure back to the pool.
  - `key_pool.py` can bootstrap provider pools from `LIMA_KEY_POOL_<PROVIDER>` with comma, semicolon, or newline separated keys and optional weights.
- Verification:
  - `python -m pytest tests/test_backend_registry.py test_http_caller.py tests/test_reflection.py tests/test_phase26_28.py -q --ignore=active_model`: `58 passed`.
  - `python -m py_compile backends.py smart_router.py http_caller.py key_pool.py context_pipeline/reflection.py server.py`: passed.
  - Expanded runtime regression: `110 passed`.
  - Secret/request/vision/free-web admission suite: `10 passed`.
- VPS deployment:
  - runtime commit `659f484` deployed;
  - backup `/opt/lima-router/backups/backend-registry-keypool-20260524-120642`;
  - uploaded `backends.py`, `smart_router.py`, `http_caller.py`, `key_pool.py`, and `context_pipeline/reflection.py`;
  - remote `py_compile` and `import server; import backends; import http_caller; import key_pool; import smart_router` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `backend_registry_https_ok`;
  - FRP chat returned exact `backend_registry_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 Endpoint And Key-Pool Telemetry Closure Deploy

- Closed the remaining concrete architecture items:
  - extracted OpenAI and Anthropic HTTP adapters into `routes/chat_endpoints.py`;
  - extracted models, health, live-key, and status endpoints into `routes/system_endpoints.py`;
  - retained `server.chat_completions`, `server.anthropic_messages`, and system endpoint aliases for compatibility;
  - reduced `server.py` to app setup plus core runtime helpers, with no direct business endpoint decorators;
  - added `key_pool.pool_snapshot()` with redacted key IDs and active/cooled/blocked status telemetry.
- Added regression coverage:
  - `tests/test_chat_endpoints.py`;
  - `tests/test_system_endpoints.py`;
  - `tests/test_key_pool.py`.
- Verification:
  - endpoint/key-pool focused regression: `62 passed`;
  - expanded runtime/admission/security regression: `128 passed`;
  - local `py_compile` passed for `server.py`, the extracted endpoint modules, and backend/key-pool runtime files.
- VPS deployment:
  - runtime commit `d10ed57`;
  - backup `/opt/lima-router/backups/endpoints-keypool-closed-20260524-123145`;
  - remote `py_compile` and import smoke passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `endpoints_closed_https_ok`;
  - FRP chat returned exact `endpoints_closed_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 TechSpar Mastery Loop Closure

- Implemented the TechSpar-inspired local evidence loop:
  - `mastery_loop/models.py` defines mastery events, module mastery, weak points, review schedules, and recommendations.
  - `mastery_loop/profile_store.py` stores sanitized evidence in SQLite and redacts secret-like text before persistence.
  - `mastery_loop/event_adapter.py`, `weak_point_extractor.py`, `scorer.py`, `scheduler.py`, `recommender.py`, and `trace.py` convert tests/reviews/routes/tools/deploys into scores, weak points, schedules, and recommendation traces.
- Wired agent skill promotion to evidence:
  - `CandidateSkill` now stores `mastery_evidence_refs`.
  - `promote_candidate()` requires eval pass, manual approval, and non-empty mastery evidence refs before activation.
  - `/agent/skills/{skill_id}/promote` enforces the same gate.
  - Successful promotion is persisted back to the JSON candidate store.
- Added reference-boundary docs:
  - `docs/reference/TECHSPAR_BORROWING_NOTES.md`.
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`.
  - `docs/reference/POTPIE_COMPOSIO_BORROWING_NOTES.md` now also records AnySearch and FreeDomain boundaries.
- Updated status docs so stale claims no longer describe retrieval as compute-only or the TechSpar loop as only future work.
- Focused verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile mastery_loop\*.py agent_evolution\candidates.py agent_evolution\promote.py routes\agent_tasks.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests/test_mastery_loop.py tests/test_agent_evolution.py tests/test_agent_task_routes.py -q --ignore=active_model`: `40 passed`.
  - Expanded runtime regression over backend registry, key pool, endpoint, agent route, access, prompt-memory, routing, request-stats, vision, secret hygiene, mastery, and evolution tests: `144 passed`.
  - Focused docs/reference secret scan: no matches.
  - `git diff --check` on touched files: no whitespace errors; Git reported expected LF-to-CRLF working-copy warnings only.
- Remaining items are intentionally gated policy surfaces, not unimplemented migration tasks:
  - always-on worker daemon;
  - Kimi/TheOldLLM/MiMo/page-only promotion;
  - refresh execution;
  - mastery admin UI exposure and hot-path planner/routing influence.
- GitHub:
  - committed and pushed `bd0bf04` (`feat: add mastery loop evidence gates`) to `origin/codex/free-web-ai-probe`.
- VPS deployment:
  - backup `/opt/lima-router/backups/mastery-loop-20260524-125511`;
  - uploaded `mastery_loop/`, `agent_evolution/candidates.py`, `agent_evolution/promote.py`, and `routes/agent_tasks.py`;
  - remote `py_compile` and import smoke passed;
  - `systemctl restart lima-router` returned active.
- Public smokes after deployment:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `mastery_loop_https_ok`;
  - FRP chat returned exact `mastery_loop_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 Online Distribution Governance

- User clarified that the VPS official website, open platform, and chat interface are LiMa distributions and must be controlled and recorded in the main repo/GitHub.
- Added distribution source of truth:
  - `docs/ONLINE_DISTRIBUTIONS.md`.
  - `infra/vps/nginx/chat.donglicao.com.conf`.
  - `infra/vps/nginx/api.donglicao.com.conf`.
  - `infra/vps/nginx/www.donglicao.com.conf`.
  - `infra/vps/systemd/lima-router.service`.
  - `infra/vps/systemd/lima-voice.service`.
  - `scripts/smoke_online_distributions.py`.
- Recorded active online surfaces:
  - official website: `https://www.donglicao.com` and `https://donglicao.com`;
  - chat/API: `https://chat.donglicao.com`;
  - open platform: `https://api.donglicao.com`;
  - FRP validation path: `http://47.112.162.80:8088`.
- Found and closed VPS service-file secret hygiene issue:
  - provider-key-like environment lines were present in `lima-router.service` and `lima-voice.service`;
  - migrated them into `/opt/lima-router/.env` and `/opt/lima-voice/.env`;
  - added `EnvironmentFile=/opt/lima-voice/.env`;
  - moved secret migration backups to `/root/secure-service-backups` with mode `600`;
  - `lima-router` and `lima-voice` restarted active;
  - `systemctl cat` no longer reports key/token/secret-like service lines.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile scripts\smoke_online_distributions.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe scripts\smoke_online_distributions.py --chat-exact distribution_control_ok`: `10/10 checks passed`.

## 2026-05-24 Reference Migration Compatibility Closure

- Closed the two remaining literal compatibility gaps from the reference migration audit:
  - added `code_context/retriever.py` as the planned Potpie-inspired retrieval facade over `InMemoryCodeIndex`;
  - added `docs/OPS_ENTRYPOINTS.md` as the original FreeDomain-inspired ops entrypoint document, pointing to the expanded `docs/ONLINE_DISTRIBUTIONS.md` source of truth.
- Added regression coverage that imports and uses `code_context.retriever.retrieve_relevant_files()`.

## 2026-05-24 LiMa Code Main-Repo Management Closure

- Registered `deepcode-cli` as the main repository's tracked LiMa Code submodule.
- Added `docs/LIMACODE_MANAGEMENT.md` as the governance record for LiMa Code ownership boundaries, submodule pointer updates, verification, and safety rules.
- Recorded LiMa Code as a first-class managed LiMa distribution in `STATUS.md` and `docs/DOCUMENTATION_STATUS.md`.

## 2026-05-24 esp32S_XYZ Backend Management Closure

- Registered `esp32S_XYZ` as the main repository's tracked downstream product submodule.
- Added `docs/ESP32S_XYZ_MANAGEMENT.md` as the governance record for LiMa backend ownership, product repository boundaries, submodule pointer updates, verification, and hardware-release safety rules.
- Recorded `esp32S_XYZ` as a first-class LiMa-managed product distribution in `STATUS.md`, `docs/DOCUMENTATION_STATUS.md`, and `docs/LIMA_MEMORY.md`.

## 2026-05-24 esp32S_XYZ Optimization Authorization

- Confirmed `D:\GIT\esp32S_XYZ` is a clean local clone of `https://github.com/zhuguang-ZFG/esp32S_XYZ.git` on `main...origin/main`.
- Recorded user authorization for LiMa to perform deep optimization and necessary refactoring in the product repository.
- Added `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` and expanded `docs/ESP32S_XYZ_MANAGEMENT.md` with refactor authority, cross-repo order, and gated-release safeguards.

## 2026-05-24 LiMa Direct Device Gateway Plan

- User selected the long-term clean path: U8 firmware directly speaks a LiMa custom protocol and no longer depends on Xiaozhi server at runtime.
- Decided LiMa needs a new Device Gateway route layer (`/device/v1/*`) while continuing to reuse the existing model routing/provider stack.
- Added `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md` with phased cross-repo implementation, protocol v1 message shapes, safety gates, and verification matrix.

## 2026-05-24 Xiaozhi Server Deprecation Plan

- User agreed to plan retirement of Xiaozhi server code after LiMa Direct Device Gateway replaces the runtime path.
- Added `docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md`.
- Plan policy: mark as legacy first, build migration inventory, port useful behavior to LiMa direct route, verify fake U8 and real U8/U1 safety gates, then quarantine or delete and advance the main submodule pointer.

## 2026-05-24 Voice Display Companion Hardware References

- User requested that ElatoAI and the ESP32 TFT transparent-TV article be
  included in the later LiMa voice/display/companion hardware route.
- Added `docs/reference/HARDWARE_COMPANION_REFERENCES.md`.
- Updated the LiMa Direct Device Gateway plan, `esp32S_XYZ` optimization
  roadmap, documentation status, and durable memory to keep writing-machine
  direct control as the first target while admitting voice/display/companion
  devices as post-gate roadmap inputs.

## 2026-05-24 External Capability Radar And Adoption Roadmap

- User provided 27 external references for improving the main repo and
  subrepos.
- Added `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md` with
  capability groups, target repos, license signals, and priority candidates.
- Added
  `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`
  with staged adoption across code intelligence, memory, agent orchestration,
  sandbox/browser verification, research/trend products, persona/style, and
  hardware companions.
- Updated `docs/DOCUMENTATION_STATUS.md` and `docs/LIMA_MEMORY.md`.
- Current policy: concept-first, no automatic dependency adoption, and no code
  copy from GPL/AGPL/missing-license sources without a separate review gate.
- Added `NVIDIA/personaplex` to the persona, voice, and companion-device
  reference track as a realtime full-duplex speech/persona model candidate,
  gated by model license, privacy, safety, compute, and opt-in requirements.

## 2026-05-24 LiMa Device Gateway Implementation Slice

- Implemented the first code slice for LiMa-native device routing:
  - `device_gateway/protocol.py`;
  - `device_gateway/auth.py`;
  - `device_gateway/sessions.py`;
  - `device_gateway/intent.py`;
  - `device_gateway/safety.py`;
  - `device_gateway/tasks.py`;
  - `routes/device_gateway.py`;
  - `server.py` router registration.
- Added tests for protocol validation, deterministic command mapping, bounded
  fake `run_path` projection, `/device/v1/health`, `/device/v1/ws`, fake U8
  hello/heartbeat/transcript/motion_event loop, private HTTP event ingest,
  private debug task creation, and stable error envelopes.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile server.py routes\device_gateway.py device_gateway\protocol.py device_gateway\auth.py device_gateway\sessions.py device_gateway\tasks.py device_gateway\intent.py device_gateway\safety.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py -q --ignore=active_model`: 15 passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_system_endpoints.py tests\test_chat_endpoints.py tests\test_agent_task_routes.py -q --ignore=active_model`: 31 passed.

## 2026-05-24 esp32S_XYZ Fake LiMa U8 Client

- Implemented and pushed product-side fake LiMa U8 client:
  - product repo: `D:\GIT\esp32S_XYZ`;
  - commit: `78a62c9 test: add fake lima u8 client`;
  - remote: `https://github.com/zhuguang-ZFG/esp32S_XYZ.git`.
- Added `tools/fake_lima_u8/app.py` and unit tests using an in-memory transport
  so default product CI does not require a WebSocket dependency.
- Updated `tools/README.md`.
- Product verification:
  - `python -m py_compile tools\fake_lima_u8\app.py`: passed;
  - `python -m unittest tools.fake_lima_u8.tests.test_app -v`: 5 passed;
  - `python -m unittest tools.fake_device_server.tests.test_app tools.fake_ai.tests.test_app tools.fake_u1.tests.test_app -v`: 31 passed;
  - `python tools\validate_schemas.py`: `validated=62 passed=62 failed=0`.
- Main repo advanced the `esp32S_XYZ` submodule pointer to `78a62c9` and added
  `LIMA_DEVICE_TOKENS` to `.env.example`.

## 2026-05-24 Device Gateway Concurrency

- User asked whether LiMa routing supports concurrency and multiple devices /
  multiple requests at the same time.
- Implemented explicit concurrency support for the Device Gateway:
  - locked session registry;
  - per-session async send lock;
  - locked task store and task ID generation;
  - per-device offline task queues;
  - device `hello` flushes only that device's queued tasks;
  - `/device/v1/tasks` sends immediately to online devices or records queued
    state for offline devices;
  - `/device/v1/health` reports total pending tasks.
- Added `tests/test_device_gateway_concurrency.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py -q --ignore=active_model`: 19 passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile routes\device_gateway.py device_gateway\sessions.py device_gateway\tasks.py`: passed.

## 2026-05-24 Device Gateway HA Store Boundary

- User clarified the later target: multi-process, multi-machine, and VPS high
  availability.
- Implemented the HA-ready task-store boundary:
  - added `device_gateway/store.py`;
  - moved task state, event state, ID generation, and offline queues behind
    `DeviceTaskStore`;
  - fixed task helpers to read the active store dynamically so future
    Redis/Postgres adapters can be installed without route changes;
  - `/device/v1/health` now exposes task-store backend metadata and whether the
    active store is shared across processes.
- Closed the synchronous send-failure gaps found during review:
  - active WebSocket send failure best-effort requeues the task and unregisters
    the stale session;
  - hello flush drains all pending task batches for the device;
  - requeue preserves FIFO order for unsent tasks.
- Added per-session in-flight task tracking:
  - motion tasks remain in the session in-flight table until a `motion_event`
    acknowledges them;
  - unacknowledged in-flight tasks are best-effort requeued on WebSocket
    disconnect.
- Added regression coverage proving store replacement works and no stale
  imported store object is used, plus send-failure and large-queue drain
  behavior.
- Added direct `DeviceTaskStore` contract coverage for event snapshots, FIFO
  requeue, per-device isolation, and concurrent task IDs.
- Current deployment interpretation:
  - single process supports concurrent multi-device traffic;
  - HA requires a shared store plus sticky WebSocket routing or a session
    owner/broker before non-sticky multi-node traffic.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py tests\test_device_gateway_store.py -q --ignore=active_model`: 28 passed.

## 2026-05-24 External Capability Radar Expansion

- User provided a second external-reference batch:
  - AnySearch Skill, oh-my-pi, Microsoft Agent Governance Toolkit, vibe-vibe,
    CloakBrowser, GR00T-WholeBodyControl, pocket-tts, OpenAI Symphony,
    Algebrica, GLM-OCR, nano-world-model, agent-skills, HeavySkill,
    Understand-Anything, deepclaude, and claude-context.
- Performed current-source scan:
  - GitHub API metadata succeeded for most original projects and several new
    projects;
  - raw README/license fetch filled in projects that hit GitHub API `403`;
  - confirmed examples: Microsoft Agent Governance Toolkit MIT, OpenAI
    Symphony Apache-2.0, CloakBrowser MIT, GLM-OCR Apache-2.0, pocket-tts
    MIT-style license text, GR00T source Apache-2.0 with NVIDIA Open Model
    License weights, Algebrica CC BY-NC 4.0 content.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/POTPIE_COMPOSIO_BORROWING_NOTES.md`;
  - `STATUS.md`, `docs/DOCUMENTATION_STATUS.md`, and `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency added;
  - no source code copied;
  - no hardware or model claim expanded beyond documented gates.

## 2026-05-24 Sub-Agent Versus Agent Team Rule

- User shared and approved a coordination principle:
  - do not add agents because a task is complex;
  - choose the collaboration mode based on context boundaries and coordination
    needs.
- Updated:
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- New LiMa default:
  - owner agent plus isolated sub-agents for separable research/review/test
    slices;
  - Agent Teams only after shared state, real-time communication, event log,
    ownership, conflict policy, and approval gates are designed.

## 2026-05-24 External Capability Radar Third Batch

- User provided another reference batch:
  - mattpocock skills, HF Viewer, Warp, Pascal Editor, ClaudePrism, Open
    Design, learn-harness-engineering, OpenAI Agents SDK, Google ADK,
    GenericAgent, Evolver, plus duplicate stash, clawsweeper, and agency-agents.
- Current-source scan:
  - GitHub API metadata confirmed examples: `mattpocock/skills` MIT,
    `warpdotdev/warp` AGPL-3.0, `pascalorg/editor` MIT,
    `delibae/claude-prism` MIT, `nexu-io/open-design` Apache-2.0,
    `openai/openai-agents-python` MIT, `google/adk-python` Apache-2.0,
    `lsdefine/GenericAgent` MIT, `EvoMap/evolver` GPL-3.0.
  - `hfviewer.com` was treated as a website/product reference, not a dependency.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Boundary retained:
  - no source code copied;
  - no runtime dependency added;
  - GPL/AGPL references are concept-only until separate legal review.

## 2026-05-24 External Capability Radar MCP Batch

- User provided TUNA mirror, repeated TrendRadar, OpenMontage, and a Claude MCP
  service guide/taxonomy.
- Current-source checks:
  - TUNA mirror site returned 200 and is treated as an operational mirror
    reference for dependency bootstrap resilience.
  - `calesthio/OpenMontage` GitHub metadata reports AGPL-3.0 and describes an
    agentic video production system; it is concept-only for media/artifact
    pipeline design.
  - `sansan0/TrendRadar` remains GPL-3.0 and already existed in the radar; its
    row was strengthened with MCP, multi-platform aggregation, AI brief, and
    alert-routing details.
  - Official MCP Registry returned 200.
  - `modelcontextprotocol/servers` README describes the repository as
    reference/educational implementations rather than production-ready
    services.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-23-lima-code-dev-search-tools.md`;
  - `docs/DOCUMENTATION_STATUS.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Policy retained:
  - Skills are methods; MCP connectors are authority-bearing access paths.
  - New MCP connectors are default-off and require task need, owner, allowlist,
    credential boundary, audit event, timeout, and failure mode.
  - No runtime dependency was added and no external source code was copied.

## 2026-05-24 AI Engineering Competency Map

- User shared a 2026 AI engineer interview / production AI map covering 12
  concepts:
  - prompt engineering;
  - RAG;
  - vector embeddings and vector databases;
  - agentic AI and tool calling;
  - reasoning;
  - memory management;
  - streaming and async;
  - inference optimization;
  - token and cost management / FinOps;
  - fine-tuning / PEFT;
  - LLM eval;
  - MLOps and production deployment.
- Added `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md` to map each
  concept to LiMa current state and next gates.
- Updated:
  - `docs/DOCUMENTATION_STATUS.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - this is a production engineering checklist, not a runtime dependency;
  - no code changes, no model changes, and no deployment changes were made.

## 2026-05-24 External Capability Radar Agent Voice Design Batch

- User provided VoxCPM, open-lovable, Hermes Agent Orange Book, goclaw, and
  claude-code-prompts.
- Current-source checks:
  - `OpenBMB/VoxCPM`: Apache-2.0; VoxCPM2 README describes multilingual TTS,
    voice design, controllable voice cloning, streaming, and 48kHz output.
  - `firecrawl/open-lovable`: MIT; README describes website-to-React
    generation with Firecrawl, model API keys, and Vercel/E2B sandbox options.
  - `alchaincyf/hermes-agent-orange-book`: README declares CC BY-NC-SA 4.0;
    concept-only reference for learning loops, layered memory, Skills, and
    agent orchestration.
  - `nextlevelbuilder/goclaw`: existing row strengthened with multi-tenant
    isolation, 5-layer security, native concurrency, and agent-team posture;
    license remains unreviewed.
  - `repowise-dev/claude-code-prompts`: MIT; independently authored prompt
    reference for system/tool/agent/memory/coordinator contracts.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency or prompt library was added;
  - no external source or prompt text was copied;
  - voice cloning and website reconstruction remain explicit opt-in future
    work behind consent, security, privacy, review, and test gates.

## 2026-05-24 External Capability Radar Research Subagent Batch

- User provided last30days skill, LightRAG, Claude use cases,
  awesome-codex-subagents, AutoResearchClaw, OpenCode, and vibe-coding-cn.
- Current-source checks:
  - `mvanhorn/last30days-skill`: MIT; researches recent signals across Reddit,
    X, YouTube, HN, Polymarket, GitHub, and web sources, ranked by engagement
    and synthesized into a grounded brief.
  - `HKUDS/LightRAG`: MIT; simple/fast RAG with graph/RAG posture,
    multimodal parsing, chunking strategies, role-specific LLM configuration,
    and storage backend support.
  - `claude.com/resources/use-cases`: page returned 200 and is treated as a
    product use-case taxonomy reference.
  - `VoltAgent/awesome-codex-subagents`: MIT; 136+ Codex-native TOML subagents
    with categories, storage paths, sandbox defaults, and explicit delegation.
  - `aiming-lab/AutoResearchClaw`: MIT; autonomous/self-evolving research,
    HITL modes, ARC-Bench, anti-fabrication checks, budget guardrails, and
    OpenClaw integration.
  - `anomalyco/opencode`: MIT; open-source coding agent with terminal UI,
    installer/package-manager distribution, desktop beta, and localization.
  - `2025Emma/vibe-coding-cn`: MIT; Chinese planning-first Vibe Coding guide
    with prompts, skills, multilingual docs, and AI-pair-programming workflow.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency was added;
  - no external source or prompt text was copied;
  - social/source research, broad subagent catalogs, autonomous research
    pipelines, and coding-agent workflow references remain gated by privacy,
    ownership, evidence, budget, sandbox, and approval rules.

## 2026-05-24 External Capability Radar Browser Search RL Batch

- User provided:
  - `hyperbrowserai/hyperbrowser-app-examples`;
  - Feishu wiki `2026 企业级AI编程实践手册`;
  - `modelscope/sirchmunk`;
  - `666ghj/MiroFish`;
  - `Gen-Verse/OpenClaw-RL`;
  - `garrytan/gstack`;
  - `Nunchi-trade/agent-cli`;
  - `https://hermes-agent.nousresearch.com/`.
- Current-source checks:
  - Hyperbrowser examples README says MIT and describes browser automation,
    scraping/data extraction, production web apps, deployment patterns, and
    required Hyperbrowser API keys; GitHub API earlier returned no SPDX
    assertion, so license review stays explicit before dependency use.
  - Feishu page returned HTTP 200 and exposed the title
    `2026 企业级AI编程实践手册`; visible headings cover context engineering,
    specs, rules, skills, MCP, agents, and enterprise AI coding methodology.
    No reuse license was observed.
  - `modelscope/sirchmunk`: Apache-2.0; README describes raw-data/indexless
    retrieval, knowledge clustering, Monte Carlo evidence sampling,
    self-evolving knowledge clusters, real-time chat, API/SSE, DuckDB-style
    persistence, allowed-path hardening, and MCP support.
  - `666ghj/MiroFish`: AGPL-3.0; swarm-intelligence/prediction simulation
    concept only.
  - `Gen-Verse/OpenClaw-RL`: Apache-2.0; fully async RL loop for training
    personalized agents from natural-language feedback across terminal, GUI,
    SWE, and tool-call settings.
  - `garrytan/gstack`: MIT; workflow stack for plan/review/QA/browser testing,
    security review, release/deploy, safety guard commands, cross-model
    review, gbrain setup, and multi-host skill installation.
  - `Nunchi-trade/agent-cli`: MIT; autonomous trading CLI with agent skills,
    MCP server, deterministic orchestrator, risk states, reconciliation,
    REFLECT review loop, HTTP/SSE surfaces, and testnet/mainnet split.
  - Hermes Agent site returned HTTP 200 and claims open-source/MIT status for
    server-resident autonomous agent behavior, persistent memory, generated
    skills, scheduled automations, isolated subagents, sandbox backends,
    browser/web control, and messaging surfaces; source repo/license remains
    unverified.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code, prompt, or Feishu document text copied;
  - browser automation remains gated by API-key custody, target-site terms,
    privacy, rate limits, and anti-abuse review;
  - AGPL/no-reuse-license sources remain concept/background only;
  - trading/finance automation is blocked;
  - live self-training from private sessions is blocked until consent, privacy,
    eval, rollback, model-storage, compute, and cost gates exist.

## 2026-05-24 External Capability Radar RAG MCP Media Batch

- User provided:
  - `langflow-ai/openrag`;
  - `GoogleCloudPlatform/generative-ai`;
  - `ruvnet/RuVector`;
  - `Panniantong/Agent-Reach`;
  - `QwenLM/Qwen3-TTS`;
  - `nexmoe/VidBee`;
  - `chenhg5/cc-connect`;
  - `VectorlyApp/bluebox`;
  - `google/mcp`.
- Current-source checks:
  - `langflow-ai/openrag`: Apache-2.0; README describes intelligent
    agent-powered document search, Langflow ingestion/retrieval workflows,
    OpenSearch, Docling, reranking, multi-agent coordination, and chat UI.
  - `GoogleCloudPlatform/generative-ai`: Apache-2.0; README describes Gemini,
    Agent Platform, Agent Search, RAG/grounding, vision, audio, setup, and
    sample applications/notebooks.
  - `ruvnet/RuVector`: MIT; README describes self-learning vector memory,
    hybrid sparse/dense retrieval, Graph RAG, PostgreSQL/pgvector posture,
    local/WASM runtime, MCP server, audit chains, and branchable data.
  - `Panniantong/Agent-Reach`: MIT; README describes internet-reach
    scaffolding for web, YouTube, RSS, GitHub, semantic web search via MCP,
    social/video/community channels, local cookie storage, `doctor`, safe
    mode, and replaceable upstream tools.
  - `QwenLM/Qwen3-TTS`: Apache-2.0 source; README describes multilingual TTS,
    custom voice, voice design, 3-second voice clone, natural-language voice
    control, streaming/non-streaming generation, DashScope API, vLLM-Omni,
    fine-tuning, and evaluation.
  - `nexmoe/VidBee`: MIT; README describes Electron/yt-dlp video/audio
    downloader UX, RSS auto-download, queue/progress management, Fastify API,
    oRPC, SSE events, web client, and Docker deployment.
  - `chenhg5/cc-connect`: README badge says MIT, but raw license fetch failed;
    README describes local-agent messaging bridges, web admin UI, hooks,
    skills, provider management, WeChat, Weibo, Feishu/Lark, Telegram, Slack,
    Discord, voice/images, cron jobs, and 10+ AI agent integrations.
  - `VectorlyApp/bluebox`: Apache-2.0; README describes indexing undocumented
    APIs, web-data extraction behind UI interactions, natural-language routine
    selection, parallel routine execution, live AI-browser fallback, and
    session context replay.
  - `google/mcp`: Apache-2.0; README lists Google managed remote MCP servers,
    open-source MCP servers, Cloud Run hosting guidance, and ADK examples; it
    also states the repo is not an officially supported Google product.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code or prompt text copied;
  - OpenRAG/Google/RuVector remain references until LiMa-owned interfaces and
    benchmarks exist;
  - social/cookie/proxy tools, messaging bridges, closed-API extraction,
    cloud-control MCP, and video downloading remain default-off;
  - Qwen3-TTS voice clone/custom voice stays behind model/API terms, consent,
    voice safety, latency/GPU budget, and audio-retention gates.

## 2026-05-24 External Capability Radar RuView Addendum

- User provided `https://github.com/ruvnet/RuView.git`.
- Current-source check:
  - `ruvnet/RuView`: MIT; README describes beta WiFi CSI spatial sensing with
    ESP32-S3/C6-style nodes, presence, breathing/heart-rate trends,
    activity/fall signals, room mapping, Home Assistant/Matter integration,
    edge modules, witness logs, and Claude/Codex workflow plugins.
  - README limitations matter for LiMa: ESP32-C3/original ESP32 are not
    supported, single-node spatial resolution is limited, camera-free pose
    accuracy is limited, and some training/evaluation phases remain pending.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code or prompt text copied;
  - RuView is a later ambient-perception and hardware-workflow reference, not
    part of the first writing-machine control loop;
  - people sensing, through-wall sensing, vital-sign trends, fall/distress
    detection, room mapping, Home Assistant/Matter automation, and
    security/medical outputs require consent, privacy/legal review, calibrated
    hardware evidence, false-positive policy, data-retention controls, and
    human review before any LiMa adapter.

## 2026-05-24 External Capability Radar Quelmap Addendum

- User provided `https://github.com/quelmap-inc/quelmap.git`.
- Current-source check:
  - `quelmap-inc/quelmap`: Apache-2.0; README describes an open-source local
    data analysis assistant with visualization, table joins, statistical tests,
    unlimited-row/30+ table analysis posture, built-in Python sandbox,
    Ollama/local LLM defaults, OpenAI-compatible providers, Docker Compose,
    Postgres storage, and CSV/Excel/SQLite upload support.
  - README privacy warning matters for LiMa: if a provider such as OpenAI or
    Groq is configured, dataset schema is sent to that provider. External DB
    connection strings should use read-only credentials.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code or prompt text copied;
  - Quelmap is a data-analysis workbench reference, not a default LiMa
    dependency;
  - dataset contents/schema, generated Python, external database connections,
    and cloud LLM provider calls require consent, redaction, read-only
    credentials, sandbox limits, data retention, and audit.

## 2026-05-24 External Capability Radar 10-Subsystem Addendum

- User provided a de-duplicated 10-subsystem open-source recommendation table
  for LiMa.
- Added:
  - `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md`.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Current-source checks:
  - confirmed examples: E2B Apache-2.0, Ollama MIT, vLLM Apache-2.0, Portkey
    MIT, aiohttp Apache-2.0, Microsoft GraphRAG MIT, LlamaIndex MIT,
    rerankers Apache-2.0, FastEmbed Apache-2.0, tree-sitter MIT, Mem0
    Apache-2.0, Letta Apache-2.0, Memobase Apache-2.0, Zep Apache-2.0,
    Promptfoo MIT, DeepEval Apache-2.0, Ragas Apache-2.0, Instructor MIT,
    OpenTelemetry Python Apache-2.0, Prometheus Python Apache-2.0, MLflow
    Apache-2.0, Guardrails AI Apache-2.0, LLM Guard MIT, MCP Python SDK MIT,
    A2A Apache-2.0, Caddy Apache-2.0, Piku MIT, Nixpacks MIT, Dagger
    Apache-2.0, Rich MIT, Textual MIT, Aider Apache-2.0.
  - caveats: LiteLLM and LangFuse have mixed license files or no SPDX in API;
    Phoenix is Elastic-2.0; Rebuff is archived; Semgrep is LGPL-2.1;
    Open Interpreter is AGPL-3.0; Sourcegraph Cody and Braintrust supplied
    paths need current-source confirmation.
- Boundary retained:
  - no runtime dependency added;
  - no external code copied;
  - the table is an implementation backlog, not a permission expansion or
    dependency installation plan.

## 2026-05-24 Implementation Review Plan

- User requested a detailed implementation plan from recent learning and set
  the division of labor: user codes, Codex reviews.
- Added:
  - `docs/superpowers/plans/2026-05-24-lima-implementation-review-plan.md`.
- The plan covers:
  - router/backend/key-pool/cost telemetry;
  - async and concurrency safety;
  - context graph, AST, reranking, and retrieval evaluation;
  - memory taxonomy, promotion, deletion, and redaction;
  - evaluation, quality gate, and structured output;
  - observability and metrics;
  - worker governance, tool gateway, MCP, and A2A;
  - sandbox evaluation without production adoption;
  - streaming and task progress;
  - data workbench and research artifacts;
  - DevOps, deployment, terminal UX;
  - later hardware companion lane.
- Verification expectation:
  - each future code slice should include changed files, behavior summary,
    tests, command output, dependency/network/credential changes, and rollback
    notes for Codex review.
- Boundary retained:
  - documentation-only;
  - no dependency added;
  - no code implementation started in this slice.

## 2026-05-24 M0 Baseline Review Harness Closure

- Re-pulled `codex/free-web-ai-probe` and reviewed commit `85663ca`.
- Found that the checklist baseline was stale:
  - `test_routing_engine.py` now passes;
  - the full suite failure came from `tests/test_device_gateway_routes.py`
    leaking `LIMA_API_KEY` into later MCP tests.
- Fixed the test isolation by replacing direct `os.environ` mutation with a
  `monkeypatch` autouse fixture.
- Updated `docs/DEVELOPER_CHECKLIST.md`, `task_plan.md`,
  `docs/REVIEW_PACKET_TEMPLATE.md`, and `findings.md` so M0 reflects the
  verified green baseline and avoids PowerShell mojibake in copied templates.

## 2026-05-24 M1-S1 Backend Registry Single Source

- Completed the first M1 slice:
  - centralized `VISION_BACKENDS`, `STRONG_MODELS`, and `IDE_SOURCES` in
    `backends.py`;
  - removed duplicate local tables from `vision_handler.py`,
    `smart_router.py`, `skills_injector.py`, and `router_v3.py`;
  - removed unregistered legacy code-capable backend names from
    `CODE_CAPABLE_BACKENDS`.
- Added registry guard tests covering:
  - routing pools;
  - direct backends;
  - vision, thinking, strong, GFW, weak, and code-capable backend lists;
  - importer identity for the centralized constants.
- Verification:
  - `python -m pytest tests/test_reflection.py tests/test_backend_registry.py test_routing_engine.py test_http_caller.py -q --ignore=active_model`: 118 passed.
  - `python -m pytest -q --ignore=active_model`: 507 passed, 8 skipped.

## 2026-05-24 M1-S2-S4 Key Pool, Failure Classes, Cost Telemetry

- Completed the remaining M1 slices:
  - `key_pool.py` now exposes exhaustion/snapshot helpers;
  - `http_caller.py` selects provider pool keys when a pool exists and falls
    back to static backend keys when no pool is configured;
  - provider pools that exist but are fully blocked/cooled now fail closed;
  - `health_tracker.py` classifies auth, quota, rate-limit, network,
    malformed, timeout, provider, and manual-refresh failures;
  - classified failures now feed `backend_reputation.py` with weighted
    penalties;
  - `budget_manager.py` records best-effort token telemetry for non-free
    backends while keeping free/local backends non-blocking.
- Review fix applied:
  - preserved static-key fallback for provider backends without an env key pool;
  - fixed health-change notification ordering in `record_failure()`.
- Verification:
  - `python -m pytest tests/test_key_pool.py test_http_caller.py tests/test_backend_reputation.py tests/test_budget_manager.py tests/test_health_tracker.py tests/test_backend_registry.py test_routing_engine.py -q --ignore=active_model`: 170 passed.

## 2026-05-24 M2-S1 HTTPX Async Boundary Review

- Reviewed the user implementation that migrated `http_caller.py` from
  `urllib.request` to `httpx`.
- Preserved the public sync interfaces:
  - `call_api()`;
  - `call_api_stream()`;
  - `call_raw()`;
  - `probe()`.
- Confirmed new async interfaces exist:
  - `call_api_async()`;
  - `call_api_stream_async()`;
  - `call_raw_async()`.
- Review fix applied:
  - internal `BackendError` handlers now report `e.status_code` to
    `key_pool.report_key_result()` instead of hardcoding 429 or 0;
  - empty streams now preserve their 502 classification for key-pool telemetry.
- Regression coverage restored/added:
  - provider backends fall back to static keys when no env pool exists;
  - configured but exhausted pools fail closed instead of falling back to a
    static key;
  - web proxy control errors such as `[LongCat HTTP 502]` clean to empty;
  - `no_system` OpenAI body construction still keeps IDE context in the first
    user message;
  - async chat, raw, and stream calls have smoke coverage.
- Verification:
  - `python -m py_compile http_caller.py test_http_caller.py`: passed.
  - `python -m pytest test_http_caller.py test_routing_engine.py -q --ignore=active_model`: 97 passed.

## 2026-05-24 M2-S2-S3 Async Streaming And Speculative Execution

- Completed M2 async/concurrency slices after review:
  - `streaming.py` now exposes `bridge_stream_async()` for native async stream
    bridging without worker threads or queues.
  - `streaming.speculative_stream()` can use injected async stream/API
    callables while preserving the legacy sync-callable path.
  - `routes/v3_adapters.py` exposes `v3_call_stream_async()` and
    `v3_call_api_async()`.
  - `routes/stream_handlers.py` exposes `real_stream_chunks_async()` and wires
    speculative streaming to the async-native callables.
  - `speculative.py` now has `speculative_call_async()` backed by
    `asyncio.create_task()` and keeps `speculative_call()` as a sync facade.
- Review fixes applied:
  - `bridge_stream_async()` now uses `asyncio.wait_for()` for real first-chunk
    timeout behavior and closes async generators on timeout/fallback.
  - async fake-stream adapters use `http_caller.call_api_async()` instead of
    blocking the event loop with the sync API.
  - `speculative_call_async()` now waits past invalid fast responses for a
    valid slower response before cancelling pending tasks.
  - speculative latency/failure learning was restored so
    `is_historically_fast()` still has data.
  - `speculative_call()` now works when called from an already-running event
    loop by running its coroutine in a compatibility thread.
- Regression coverage added:
  - async bridge yields chunks;
  - async bridge falls back on empty stream;
  - async bridge first-chunk timeout falls back;
  - speculative stream uses the async-native path when callables are provided;
  - speculative async waits past a fast invalid response;
  - speculative sync facade works inside a running event loop.
- Verification:
  - `python -m py_compile streaming.py speculative.py routes/v3_adapters.py routes/stream_handlers.py test_streaming.py`: passed.
  - `python -m pytest test_streaming.py test_routing_engine.py test_http_caller.py -q --ignore=active_model`: 108 passed.

## 2026-05-24 Multi-Agent Coding Paper Radar

- User shared a multi-agent collaborative programming paper/practice summary:
  AgentConductor, Solvita, RecursiveMAS, and Qoder.
- Current-source calibration:
  - AgentConductor is treated as a dynamic-topology multi-agent programming
    reference: expand agent collaboration only when task difficulty justifies
    cost.
  - Solvita is treated as a competitive-programming evolution-loop reference:
    planner/solver/oracle/hacker-style roles plus evidence-weighted experience
    updates.
  - RecursiveMAS is treated as a communication-efficiency reference: reduce
    verbose agent handoffs with compact state/artifact/evidence exchange.
  - Qoder is treated as an agentic coding product/practice reference for
    repository understanding, decomposition, verification, and long-horizon
    software engineering.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-24-lima-implementation-review-plan.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code copied;
  - paper/product benchmark numbers remain untrusted until original sources,
    benchmark setup, and reproducibility are reviewed;
  - latent-space agent communication remains concept-only until LiMa has
    model/runtime support and debuggable fallback artifacts.

## 2026-05-24 Provider Model Automation Plan

- Created `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md`.
- Recorded the OpenRouter Elephant Alpha decision:
  - `openrouter/elephant-alpha` exists in OpenRouter page/endpoint metadata;
  - it was not present in anonymous `/api/v1/models` verification;
  - endpoint metadata returned zero endpoints;
  - prompts/completions may be logged;
  - LiMa has no backend entry for it.
- Decision:
  - keep Elephant Alpha as watchlist/sandbox evidence only;
  - do not route private code to it;
  - do not let provider catalogs directly mutate `backends.py`.
- Planned automation:
  - provider catalog snapshots and diffs;
  - separate admission state machine;
  - harmless smoke and eval before routing;
  - draining/retired states for removed or failing free models;
  - operator report and rollback snapshots.

## 2026-05-24 M3 Context Graph, AST, Reranking, Retrieval Eval

- Reviewed and closed M3:
  - `code_context/graph_index.py` defines `GraphIndex` and
    `InMemoryGraphIndex`;
  - `code_context/ast_adapter.py` defines the AST extractor boundary and a
    Python stdlib implementation;
  - `context_pipeline/retrieval_eval.py` adds recall, precision@k, hit rate,
    MRR, query evaluation, and summary formatting;
  - fixture files under `tests/fixtures/sample_repo/` cover imports, classes,
    methods, and functions;
  - tests cover graph traversal, AST extraction, deterministic reranking, and
    retrieval metrics.
- Review fixes applied:
  - `extract_relations()` now resolves import targets by full module, root
    package, or leaf module;
  - `evaluate_queries()` now counts missing retrieved rows as misses instead
    of silently dropping queries.
- Verification:
  - focused M3 tests returned 46 passed before the final full-suite run.

## 2026-05-24 M4 Memory Taxonomy, Promotion, Deletion, Redaction

- Reviewed and closed M4:
  - `MemoryEntry` now carries `memory_type`;
  - memory SELECT paths return `memory_type` instead of silently falling back
    to `exchange`;
  - `session_memory.redact` centralizes secret detection and redaction;
  - daemon ingestion stores sanitized facts, not the original text;
  - memory promotion records evidence and JSONL audit entries;
  - delete/export helpers exist for single memory, type, age, session, and
    type-scoped export.
- Review fixes applied:
  - `save_memory()` no longer falls back to the raw input when
    `sanitize_for_memory()` rejects critical content such as private keys;
  - promotion evidence is sanitized before being written to memory detail and
    the promotion audit log;
  - redaction tests now assert concrete redaction behavior instead of
    tautological `len(facts) >= 0` checks.
- Verification:
  - `python -m pytest tests/test_typed_memory.py -q --ignore=active_model`:
    19 passed before the final full-suite run.

## 2026-05-24 M5 Eval, Quality Gate, Structured Output

- Reviewed and closed M5:
  - `routes/quality_gate.py` now exposes `QualityGateResult` and
    `quality_check_typed()`;
  - legacy `quality_check()` remains a boolean compatibility wrapper;
  - `tests/test_quality_gate.py` covers empty/error responses, exact-output
    handling, short answers, refusals, truncation, tier helpers, and honest
    failure responses;
  - `coding_eval.py` loads both per-file JSON cases and JSON-list files;
  - `CodingCase` now supports `max_chars`;
  - `data/coding_cases/` contains five local eval fixtures.
- Review fixes applied:
  - rewrote the quality-gate source/tests as ASCII with Unicode escapes to
    avoid mojibake regressions;
  - fixed `repairable` detection for `too short for complexity`;
  - allowed refusals when the prompt is clearly harmful;
  - made the harmful eval fixture require refusal/safety wording instead of
    passing any long answer.
- Verification:
  - `python -m pytest tests/test_quality_gate.py tests/test_coding_eval.py -q --ignore=active_model`:
    39 passed before the final full-suite run;
  - both `load_cases("data/coding_cases")` and
    `load_cases("data/coding_cases.json")` loaded 5 cases.

## 2026-05-24 M6 Observability Events And Metrics

- Reviewed and closed M6:
  - `observability.events` defines `LiMaEvent` and event factories for request
    lifecycle, backend calls/errors, route decisions, quality results,
    key-pool events, and token usage;
  - `observability.metrics` provides local in-memory aggregation with no
    exporter, network, or third-party dependency;
  - `docs/OBSERVABILITY_EVENTS.md` documents event shape, redaction, snapshot
    fields, and completed hot-path wiring;
  - `tests/test_observability.py` covers event creation, session hashing,
    metrics snapshots, ranking helpers, reset isolation, token accumulation,
    and redaction guarantees.
- Review fixes applied:
  - `LiMaEvent` now sanitizes metadata recursively at construction time;
  - sensitive metadata keys such as prompt/key/token/cookie/body are replaced
    with `[REDACTED]`;
  - token-like `key_pool_event(details=...)` strings are redacted before any
    event object can be recorded or logged;
  - observability files were normalized to ASCII source to avoid mojibake;
  - M6-S3 wires token usage, quality result, key-pool result, backend
    call/error, and route decision events into the existing hot paths;
  - `backend_call_event()` now accepts and stores `latency_ms`, fixing the
    review-found regression where successful `call_api()` calls failed while
    emitting telemetry;
  - `BackendError` paths inside `call_api()` now also emit backend-error
    metrics instead of only httpx/general exception paths;
  - removed an unreachable duplicate block from `http_caller._extract_code()`.
- Verification:
  - `python -m pytest tests/test_observability.py -q --ignore=active_model`:
    31 passed before the final full-suite run.
  - `python -m pytest test_http_caller.py tests/test_observability.py -q --ignore=active_model`:
    86 passed after the M6-S3 review fix.
  - `python -m pytest tests/test_budget_manager.py tests/test_key_pool.py tests/test_quality_gate.py tests/test_route_scorer.py test_http_caller.py tests/test_observability.py -q --ignore=active_model`:
    148 passed after hot-path wiring review.

## 2026-05-24 M7 Worker Governance And Tool Gateway

- Reviewed and closed M7:
  - `tool_gateway.registry` defines `AuthorityClass`, dangerous authority
    detection, approval defaults, and extended `ToolDefinition` metadata;
  - `tool_gateway.executor` supports allowed-tool sets and rejects
    unregistered, not-allowed, approval-required, over-argument, and
    missing-secret executions before handler dispatch;
  - `tool_gateway.audit` persists audit events to SQLite and exposes recent,
    query, count, and reset helpers;
  - `tool_gateway.governance` persists worker registration, heartbeat,
    status listing, quarantine, offline marking, and reset helpers;
  - `tests/test_tool_gateway.py` covers authority defaults, executor gates,
    audit persistence/redaction, and worker lifecycle.
- Review fixes applied:
  - dangerous authorities now fail closed even if a tool author forgets to set
    `requires_approval=True`;
  - executor now enforces `max_args` and passes `timeout_sec` into shell/http
    handlers;
  - audit events are sanitized recursively before both memory and SQLite
    persistence;
  - audit and worker governance tests use temp SQLite files via env vars so
    repeated test runs do not create default DB files in repo `data/`.
- Verification:
  - `python -m pytest tests/test_tool_gateway.py tests/test_agent_task_contract.py tests/test_agent_task_routes.py -q --ignore=active_model`:
    67 passed after M7 review fixes.

## 2026-05-24 M8 Sandbox Evaluation

- Reviewed and closed M8:
  - `sandbox.provider` defines the `SandboxProvider` interface and result
    dataclasses for create, upload, run, diff, terminate, and liveness checks;
  - `FakeSandboxProvider` creates disposable temp-directory sandboxes, uploads
    files, enforces subprocess timeouts, caps stdout/stderr, tracks new files,
    and cleans up with idempotent terminate;
  - `tests/fixtures/sandbox/math_utils.py` is a no-secret fixture;
  - `tests/test_sandbox_provider.py` covers lifecycle, upload/run, failures,
    timeout, output caps, diff collection, isolation, no-secret assertions,
    abstract provider behavior, and idempotent cleanup.
- Review fixes applied:
  - replaced `shell=True` with `shlex.split()` plus `shell=False` in the fake
    provider so command strings do not become an accidental shell boundary;
  - upload paths now resolve against the sandbox root and reject `../` escape;
  - subprocess environment handling now uses an allowlist plus explicit
    sandbox env vars, rather than inheriting all host secrets by default;
  - command tests now use Python invocations instead of shell builtins so they
    pass consistently on Windows and Linux.
- Verification:
  - `python -m pytest tests/test_sandbox_provider.py -q --ignore=active_model`:
    23 passed after M8 review fixes.

## 2026-05-24 M9 Streaming And Progress Events

- Reviewed and closed M9:
  - `streaming_events.py` defines `StreamEventType` and `StreamEvent`;
  - factory helpers cover token, tool_start, tool_delta, tool_end, warning,
    error, done, and audit_ref;
  - `to_sse()` emits generic SSE frames and `to_openai_chunk()` emits
    OpenAI-compatible token/done chunks;
  - `format_sse_done()` provides the terminal `[DONE]` frame;
  - `tests/test_streaming_events.py` covers event names, factory data,
    serialization, OpenAI chunks, done frames, audit refs, defaults, and full
    chunk sequences.
- Review fixes applied:
  - `StreamEvent.__post_init__()` now normalizes string event names into
    `StreamEventType` values;
  - non-token event data is recursively redacted before serialization, covering
    tool inputs/outputs and warning/error text;
  - token event text is intentionally preserved as user-visible model output;
  - added regressions for redacted tool output/input, redacted error messages,
    direct string event construction, and token text preservation.
- Verification:
  - `python -m pytest tests/test_streaming_events.py -q --ignore=active_model`:
    24 passed after M9 review fixes.
  - `python -m pytest tests/test_streaming_events.py test_streaming.py tests/test_observability.py -q --ignore=active_model`:
    66 passed after adjacent streaming/observability verification.
  - `python -m pytest -q --ignore=active_model`:
    718 passed, 8 skipped.

## 2026-05-24 M10 Data Workbench

- Reviewed and closed M10:
  - `data_workbench.policy` defines local-only ingestion policy, accepted file
    extensions, dataset size limits, retention bounds, `PrivacyClass`,
    `ArtifactKind`, schema-key redaction, and text redaction;
  - `data_workbench.manifest` defines `ArtifactManifest` with provenance,
    source URL, retrieval date, summary, local file path, evidence refs,
    privacy class, retention, tags, schema keys, and generated-by metadata;
  - manifest storage uses JSONL for append-only local records;
  - `tests/test_data_workbench.py` covers policy, retention, schema/text
    redaction, manifest defaults, expiry, save/load/filter/count, and enum
    stability.
- Review fixes applied:
  - manifest storage now resolves `LIMA_ARTIFACT_MANIFEST` at each operation,
    not only at module import time;
  - tests use temp manifest stores and artifact roots to avoid writing default
    JSONL files into repo `data/`;
  - artifact `file_path` values are normalized under `LIMA_ARTIFACT_ROOT` and
    path escapes are rejected;
  - title, source URL, evidence refs, schema keys, tags, and generated-by fields
    are redacted before serialization.
- Scope decisions:
  - `last30days-skill` is not part of M10; keep it as a future Research Radar
    reference;
  - `MiniMind` is not part of M10; keep it as future Local Model Lab material.
- Verification:
  - `python -m pytest tests/test_data_workbench.py -q --ignore=active_model`:
    25 passed after M10 review fixes.

## 2026-05-24 Recent Reference Next Steps

- Added `docs/superpowers/plans/2026-05-24-recent-reference-next-steps.md`.
- The document keeps current M11 unchanged and queues recent references into
  executable follow-up lanes:
  - N1 Provider Model Automation for volatile free models and Elephant Alpha
    watchlist/probe/admission flow;
  - N2 Research Radar for last30days, Zhihu, Juejin, WeChat, and source-backed
    trend/research artifacts;
  - N3 Operator Shell inspired by ECC doctor/status/smoke/repair/readiness
    patterns;
  - N4 Local Model Lab for MiniMind-style isolated local training/eval;
  - N5 Artifact Backup for private S3-compatible storage such as IDrive e2;
  - N6 Multi-Agent Coding Modes for AgentConductor, Solvita, RecursiveMAS, and
    Qoder-inspired workflows.
- Decision: finish and review active M11 first; use this document as the source
  for the next batch instead of changing the current coding lane midstream.

## 2026-05-24 Shadowbroker Reference Review

- Added `BigBodyCobain/Shadowbroker` to the recent-reference plan as a
  static-only reference.
- Findings:
  - repository is AGPL-3.0, so LiMa should not copy source code without a
    separate license decision;
  - useful patterns are source attribution, default-off external fetchers,
    operator-supplied API key boundaries, SSRF redirect tests, HMAC body
    binding tests, log redaction tests, and privacy-claim honesty tables;
  - OSINT layers such as CCTV, radio/SIGINT, Shodan device search, Tor, mesh,
    wormhole, and governance features are not LiMa product scope.
- Plan placement:
  - N2 Research Radar gets an external-feed governance template slice;
  - N3 Operator Shell can borrow diagnostic/security regression ideas;
  - no runtime dependency or connector is admitted from Shadowbroker.

## 2026-05-24 M11 DevOps Deployment Terminal UX

- Reviewed and closed M11:
  - `deployment.inventory` defines typed deployment inventory, five service
    entries, rollback steps, smoke commands, and markdown export;
  - `cli_status.py` defines `StatusRow`, `StatusTable`, text/JSON formatting,
    and router/memory/key-pool collectors;
  - `edit_protocol.py` defines SEARCH/REPLACE edit blocks, parser, preview,
    formatter, single-block validation, and strict batch application;
  - `tests/test_devops_cli.py` covers deployment inventory, status formatting,
    collector smoke paths, edit parsing, edit validation, and batch edits.
- Review fixes applied:
  - deployment smoke commands now use the `$LIMA_API_KEY` placeholder instead
    of a hardcoded bearer example;
  - status rows redact secret-like values before text/JSON formatting;
  - unknown status values normalize to `warn` rather than raising at render
    time;
  - `apply_edits()` now raises on missing or non-unique SEARCH blocks instead
    of silently applying a partial edit set;
  - new M11 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_devops_cli.py -q --ignore=active_model`:
    28 passed after review fixes.
  - `python -m pytest tests/test_devops_cli.py tests/test_observability.py tests/test_tool_gateway.py tests/test_data_workbench.py -q --ignore=active_model`:
    109 passed.
  - `python -m pytest -q --ignore=active_model`:
    771 passed, 8 skipped.

## 2026-05-24 M12 Hardware Motion Protocol

- Reviewed and closed M12:
  - `device_gateway.motion` defines typed motion command/event dataclasses,
    command/event enums, serialization helpers, and command factories;
  - `device_gateway.fake_device` provides a deterministic virtual writing
    machine with home, move, pen, stop, and path execution behavior;
  - `tests/test_device_motion.py` covers command serialization, event
    serialization, fake device state transitions, workspace limits, bad feed,
    path-size guards, stop behavior, and safety helpers.
- Review fixes applied:
  - fake device now emits `command_ack` for handled commands, so the protocol
    enum is exercised instead of unused;
  - workspace clamping now emits `limit_hit`, including z-axis and non-finite
    coordinate cases;
  - pen commands now require homing, and stop raises the pen plus marks the
    fake device stopped;
  - `run_path` now checks feed bounds and point-count bounds before execution;
  - new M12 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_device_motion.py -q --ignore=active_model`:
    27 passed after review fixes.
  - `python -m py_compile device_gateway/motion.py device_gateway/fake_device.py`:
    passed.
  - `python -m pytest tests/test_device_gateway_protocol.py tests/test_device_gateway_routes.py tests/test_device_gateway_concurrency.py tests/test_device_gateway_store.py tests/test_device_motion.py -q --ignore=active_model`:
    55 passed.
  - `python -m pytest -q --ignore=active_model`:
    798 passed, 8 skipped.

## 2026-05-24 LEANN Reference Review

- Cloned `yichuan-w/LEANN` to `D:/GIT/leann-ref` and performed a static-only
  review.
- Findings:
  - repository is MIT licensed;
  - core idea is a low-storage local vector index using selective embedding
    recomputation, graph pruning, AST-aware code chunking, hybrid search,
    incremental file sync, and an MCP search server;
  - useful LiMa patterns are retrieval adapter interfaces, index manifests,
    chunking/sync tests, hybrid search scoring, and optional MCP/subprocess
    boundaries;
  - runtime dependency surface is heavy (`torch`, `sentence-transformers`,
    `transformers`, PDF tooling, native ANN backends), so it should not enter
    LiMa's base server dependency set.
- Plan placement:
  - added `N7 Local Retrieval Index Lab With LEANN` to
    `docs/superpowers/plans/2026-05-24-recent-reference-next-steps.md`;
  - keep N1 Provider Model Automation as the next recommended execution lane;
  - LEANN should be evaluated later through an optional adapter and M3/M10
    retrieval/artifact gates.

## 2026-05-24 M13-S1 Provider Catalog Snapshot

- Reviewed and closed M13-S1:
  - `provider_automation.catalog` defines provider model entries, snapshots,
    deltas, admission status, probe levels, routeability helpers, JSON
    serialization, and deterministic delta computation;
  - `provider_automation.__init__` exports the catalog contract;
  - `tests/test_provider_automation.py` covers defaults, routeability,
    redacted serialization, unknown-field handling, snapshot validation,
    deterministic added/removed order, changed fields, provider mismatch
    rejection, and the catalog-presence-not-routeable invariant.
- Review fixes applied:
  - different-provider snapshots now fail fast instead of treating same model
    ids from different providers as unchanged;
  - catalog entries now carry `admission_status` and `highest_probe_level`
    so discovery state cannot be confused with route admission;
  - serialized raw metadata, evidence refs, and source evidence are redacted
    for token/key-like values;
  - capability ordering no longer creates false positive changes;
  - new S1 source/test files were cleaned to ASCII comments and docstrings.
- Historical S1 scope note:
  - `provider_automation/openrouter.py`, `provider_automation/probe.py`, and
    `provider_automation/report.py` were present in the working tree before
    S2-S5 review; this is superseded by the M13 closeout record below.
- Verification:
  - `python -m pytest tests/test_provider_automation.py -q --ignore=active_model`:
    18 passed after review fixes.
  - `python -m py_compile provider_automation/catalog.py provider_automation/__init__.py`:
    passed.
  - `python -m pytest -q --ignore=active_model`:
    816 passed, 8 skipped.

## 2026-05-24 M13 Provider Model Automation Closeout

- Reviewed and closed M13-S2 through M13-S5:
  - `provider_automation.openrouter` parses fixture/live OpenRouter catalogs,
    keeps live fetch behind the runtime `LIMA_OPENROUTER_LIVE_FETCH=1` gate,
    defaults unknown endpoint counts to zero, and puts Elephant/stealth/no-endpoint
    entries on the watchlist;
  - `provider_automation.probe` defines the five-level metadata, completion,
    stream, coding, and quality probe harness, with probe results limited to
    rejected/watchlist/sandbox/candidate states and never self-promoting to
    route-enabled;
  - `provider_automation.report` builds redacted change reports for added,
    removed, changed, impacted, watchlist, and manual-review model sets;
  - `provider_automation.admission` produces patch plans only, requiring
    candidate status for additions and cool-disabling removed routed models
    instead of deleting them blindly.
- Review fixes applied:
  - live fetch gating is checked at call time rather than captured at import;
  - endpoint-less or privacy-risky free models are not treated as passing
    metadata probes;
  - `ProbeResult` rejects `ROUTING_ENABLED`, preserving the human review
    boundary;
  - report/admission output redacts provider text, model ids, reasons, and
    generated evidence;
  - S2-S5 behavior now has regression tests in `tests/test_provider_automation.py`;
  - new provider automation source/test files were cleaned to ASCII comments
    and docstrings.
- Verification:
  - `python -m pytest tests/test_provider_automation.py -q --ignore=active_model`:
    30 passed.
  - `python -m py_compile provider_automation/catalog.py provider_automation/__init__.py provider_automation/openrouter.py provider_automation/probe.py provider_automation/report.py provider_automation/admission.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" provider_automation tests/test_provider_automation.py`:
    no matches.
  - `git diff --check -- provider_automation tests/test_provider_automation.py progress.md findings.md docs/superpowers/plans/2026-05-24-recent-reference-next-steps.md`:
    passed.
  - `python -m pytest -q --ignore=active_model`:
    828 passed, 8 skipped.

## 2026-05-24 M14 Provider Automation Operations Closeout

- Reviewed and closed M14:
  - `provider_automation.snapshot_store` persists provider snapshots, loads
    latest snapshots, counts/lists snapshots, and prunes old files;
  - `provider_automation.runner` batches metadata/smoke/stream/coding/quality
    probes with injected callables;
  - `provider_automation.review` builds a human review bundle from delta,
    probe, impact, and patch-plan evidence;
  - `provider_automation.impact` performs dry-run routing/pool/billing/privacy
    impact analysis without modifying registry files.
- Review fixes applied:
  - snapshot provider names are sanitized before entering filenames, preventing
    path traversal or arbitrary snapshot paths;
  - same-second snapshot saves no longer overwrite earlier snapshots;
  - `reset_snapshots()` with no provider now clears all snapshot files for test
    and local cleanup;
  - requested probe levels without configured callables now produce watchlist
    evidence instead of silently passing as metadata-only;
  - highest passed probe level now uses explicit probe ordering rather than
    lexicographic enum string comparison;
  - batch probe, impact, and review markdown output now redacts secret-like
    model ids, privacy notes, and injected error/report text;
  - removed models found only through routing pools now still raise
    cool/disable warnings;
  - M14 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_provider_automation.py -q --ignore=active_model`:
    56 passed after review fixes.
  - `python -m py_compile provider_automation/snapshot_store.py provider_automation/runner.py provider_automation/review.py provider_automation/impact.py tests/test_provider_automation.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" provider_automation tests/test_provider_automation.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    854 passed, 8 skipped.

## 2026-05-24 M15 Research Radar Closeout

- Reviewed and closed M15:
  - `research_radar.source` defines source records, adoption states, license
    classes, serialization, and copy-permission policy;
  - `research_radar.catalog` provides in-memory registration, lookup, search,
    filters, and counts;
  - `research_radar.seed` captures current LiMa reference sources as structured
    seed records;
  - `tests/test_research_radar.py` covers record serialization, validation,
    search/filter/count behavior, default seeds, and license safety.
- Review fixes applied:
  - source records now validate required identity fields and can round-trip
    through `from_dict()`;
  - source serialization redacts secret-like URLs, notes, and evidence refs;
  - duplicate source ids now fail fast instead of silently overwriting
    provenance;
  - tag filtering is case-insensitive and search has deterministic tie order;
  - copy-restricted licenses such as AGPL/GPL/source-available/unknown are
    flagged as not allowing code copy;
  - seed metadata for Shadowbroker, last30days, and LEANN now uses the actual
    reviewed URLs/license posture rather than generic trending URLs;
  - M15 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_research_radar.py -q --ignore=active_model`:
    25 passed after review fixes.
  - `python -m py_compile research_radar/__init__.py research_radar/source.py research_radar/catalog.py research_radar/seed.py tests/test_research_radar.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" research_radar tests/test_research_radar.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    879 passed, 8 skipped.

## 2026-05-24 M16 Local Retrieval Index Lab Closeout

- Reviewed and closed M16:
  - `local_retrieval.manifest` defines metadata-only index manifests,
    documents, chunks, backend kinds, hashes, and redaction helpers;
  - `local_retrieval.chunking` defines the chunker ABC, deterministic
    `SimpleTextChunker`, and `CodeAwareChunker` boundary;
  - `local_retrieval.index` defines the local retrieval index ABC, retrieval
    hits, and a zero-dependency in-memory token index;
  - `local_retrieval.eval_bridge` connects local search results to M3
    retrieval eval metrics;
  - `local_retrieval.leann_adapter` keeps LEANN behind an explicit optional
    boundary and environment gate.
- Review fixes applied:
  - manifest round-trips now preserve chunk records and evidence/config fields
    safely while still avoiding full text storage;
  - metadata keys and values are both redacted for secret-like markers;
  - chunk metadata now carries source path and chunk index so search hits and
    manifests can point back to documents;
  - search hits now return the correct document path and per-hit snippet rather
    than empty paths or the last chunk snippet;
  - retrieval search now handles empty queries and non-positive `top_k`
    deterministically;
  - hit serialization redacts secret-like chunk ids, paths, reasons, and
    snippets;
  - eval bridge tests now assert real recall/hit-rate/MRR using expected chunk
    ids instead of only checking result types;
  - LEANN config now has a lightweight `to_dict()` and still performs no heavy
    imports unless `LIMA_ENABLE_LEANN=1`;
  - M16 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_local_retrieval.py -q --ignore=active_model`:
    27 passed after review fixes.
  - `python -m py_compile local_retrieval/__init__.py local_retrieval/manifest.py local_retrieval/chunking.py local_retrieval/index.py local_retrieval/eval_bridge.py local_retrieval/leann_adapter.py tests/test_local_retrieval.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" local_retrieval tests/test_local_retrieval.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    906 passed, 8 skipped.

## 2026-05-24 M17 Agent Task Runtime Closeout

- Reviewed and closed M17:
  - `agent_runtime.contract` defines typed task, step, step-result, and
    run-result schemas with run/step enums and sanitized serialization;
  - `agent_runtime.planner` provides deterministic keyword-based step planning
    without LLM calls;
  - `agent_runtime.executor` provides a dry-run-first runtime with safe
    summarize, retrieve, run-tests proposal, review, and blocked shell/http
    paths;
  - `agent_runtime.events` bridges task/step lifecycle events to streaming and
    observability with safe fallback;
  - `agent_runtime.tool_policy` enforces allowlists and dangerous step/tool
    blocking before execution.
- Review fixes applied:
  - contracts now support `from_dict()` round trips and recursive redaction for
    command, metadata, audit refs, errors, evidence, and blocked reasons;
  - runtime now checks tool policy before every step handler;
  - dangerous step kinds such as shell and HTTP are fail-closed even when
    allowed tools are present;
  - `run_tests` remains dry-run/proposal-only and accepts the `pytest` alias
    without executing shell;
  - event fallback strings and observability payloads now redact secret-like
    task ids, goals, warning messages, audit refs, and blocked reasons;
  - audit refs/log entries are sanitized before returning run results;
  - `filter_allowed_steps()` no longer mutates the original step objects;
  - M17 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_agent_runtime.py -q --ignore=active_model`:
    33 passed after review fixes.
  - `python -m py_compile agent_runtime/__init__.py agent_runtime/contract.py agent_runtime/planner.py agent_runtime/executor.py agent_runtime/events.py agent_runtime/tool_policy.py tests/test_agent_runtime.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    939 passed, 8 skipped.

## 2026-05-24 M18 Agent Runtime Persistence Closeout

- Reviewed and closed M18:
  - `agent_runtime.store` defines sanitized in-memory and JSONL task/result
    stores, query helpers, retention cleanup, compaction, and test reset
    helpers;
  - `agent_runtime.resume` reconstructs resume state from stored task/result
    pairs and formats sanitized operator summaries;
  - `agent_runtime.executor` now optionally saves task/result records while
    preserving the M17 dry-run, no-shell, no-network default.
- Review fixes applied:
  - JSONL reads now return the latest task/result record instead of stale
    append-order records;
  - JSONL task listing deduplicates by task id before status filtering and
    compaction keeps only the latest task/result pair;
  - runtime persistence saves the final task status after execution, so query
    helpers no longer see stale `running` tasks;
  - in-memory and JSONL stores both sanitize saved tasks/results before
    returning or persisting them;
  - `find_blocked()` now inspects stored step results rather than planned shell
    steps;
  - completed clean tasks are not marked resumable, while failed or blocked
    runs are resumable with specific next actions;
  - `ResumeState.to_dict()` and formatted summaries redact secret-like task ids,
    step ids, and notes;
  - M18 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_agent_store.py tests/test_agent_runtime.py -q --ignore=active_model`:
    65 passed after review fixes.
  - `python -m py_compile agent_runtime/store.py agent_runtime/resume.py agent_runtime/executor.py agent_runtime/__init__.py tests/test_agent_store.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime tests/test_agent_store.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    971 passed, 8 skipped.

## 2026-05-24 M19 Agent Run Orchestrator Closeout

- Reviewed and closed M19:
  - `agent_runtime.orchestrator` defines queue requests, leases, queue status,
    and a local in-memory orchestrator over the M18 store;
  - lifecycle operations cover submit/list/claim/finish/retry/run-one,
    lease expiry, stats, and store recovery;
  - `agent_runtime.__init__` exports the orchestrator types for package users.
- Review fixes applied:
  - source/test files were cleaned to ASCII comments and docstrings;
  - direct `run_one()` now first establishes a local lease so it does not bypass
    the claim lifecycle;
  - expired claims can be reclaimed without requiring a separate manual expiry
    call;
  - `finish()` rejects mismatched task ids and late terminal overwrites;
  - finishing a request updates the stored task status as well as the result,
    preventing completed work from being recovered as pending;
  - blocked results map to `WAITING_APPROVAL` in the stored task and are not
    auto-retried;
  - store recovery skips completed, failed, cancelled, waiting-approval, and
    latest terminal/blocked result records;
  - event bridging now uses the safe M17 event helpers and cannot break queue
    operations if observability/streaming sinks fail.
- Verification:
  - `python -m pytest tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py -q --ignore=active_model`:
    91 passed after review fixes.
  - `python -m py_compile agent_runtime/orchestrator.py agent_runtime/__init__.py tests/test_agent_orchestrator.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    997 passed, 8 skipped.

## 2026-05-24 M20 Durable Orchestrator State Closeout

- Reviewed and closed M20:
  - `agent_runtime.orchestrator` now persists queue requests and leases to
    JSONL state records;
  - `load_state()` restores requests, restores valid leases, releases claimed
    requests without valid leases, expires downtime leases, and then recovers
    unfinished tasks from the M18 store;
  - helpers cover state path selection, JSON encoding/decoding, bad-record
    tolerance, state cleanup, and save-plus-snapshot.
- Review fixes applied:
  - queue state writes are now atomic through a temporary file and support
    filename-only `LIMA_QUEUE_STATE` paths;
  - persisted request goals, task ids, request ids, and worker ids are redacted
    before writing state;
  - `load_state()` returns the actual number of newly restored or recovered
    requests instead of the number of state lines read;
  - missing state files now still recover pending tasks from the run store;
  - bad JSON lines, non-dict records, bad numeric fields, and unknown statuses
    degrade safely to skipped/default values;
  - claimed requests without a valid lease restore to pending, while valid
    leases still block duplicate claims after restart;
  - idempotent repeated loads no longer duplicate requests or inflate counts;
  - M20 source/test files were cleaned to ASCII comments and docstrings.
- Verification:
  - `python -m pytest tests/test_agent_orchestrator.py -q --ignore=active_model`:
    39 passed after review fixes.
  - `python -m pytest tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py -q --ignore=active_model`:
    104 passed after review fixes.
  - `python -m py_compile agent_runtime/orchestrator.py tests/test_agent_orchestrator.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/orchestrator.py tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    1010 passed, 8 skipped.

## 2026-05-24 M21 Worker Heartbeat Governance Closeout

- Reviewed and closed M21:
  - `agent_runtime.orchestrator` now includes `WorkerRecord` and
    `WorkerGovernor` for worker registration, heartbeat, claim, release,
    quarantine, idle marking, stale-offline marking, and stats;
  - worker claims are wired through the existing local queue lease model;
  - `agent_runtime.__init__` exports the worker governance types.
- Review fixes applied:
  - busy workers with an active lease can no longer claim a second request;
  - re-registering an existing quarantined worker no longer clears quarantine;
  - `mark_idle()` no longer reactivates offline or quarantined workers;
  - stale workers still release their lease and move owned requests back to
    pending without changing quarantined/offline state;
  - M21 source/test files were cleaned to ASCII comments and imports were moved
    to the test module top.
- Verification:
  - `python -m pytest tests/test_agent_orchestrator.py -q --ignore=active_model`:
    54 passed after review fixes.
  - `python -m pytest tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py -q --ignore=active_model`:
    119 passed after review fixes.
  - `python -m py_compile agent_runtime/orchestrator.py agent_runtime/__init__.py tests/test_agent_orchestrator.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/orchestrator.py agent_runtime/__init__.py tests/test_agent_orchestrator.py tests/test_agent_store.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    1025 passed, 8 skipped.

## 2026-05-25 M22 Approval Gate Closeout

- Reviewed and closed M22:
  - `agent_runtime.approval` defines approval statuses, approval requests, and
    an approval gate for dry-run blocking and non-dry-run approval requests;
  - approval checks remain non-executing and only return allow/block decisions;
  - `agent_runtime.__init__` exports the approval gate types.
- Review fixes applied:
  - source/test files were cleaned to ASCII comments and docstrings;
  - approval request serialization redacts task ids, worker ids, goals,
    commands, reasons, and secret-like identifiers;
  - approval reuse now matches the exact step/task/worker/kind/command surface
    rather than only `step_id`;
  - repeated pending, denied, or expired checks no longer create duplicate
    approval requests;
  - expired pending or approved requests fail closed and become `expired`;
  - denied and approved requests are no longer mutable through opposite
    decisions;
  - audit event emission is redacted and cannot break approval operations if an
    event sink fails.
- Verification:
  - `python -m pytest tests/test_approval_gate.py -q --ignore=active_model`:
    23 passed after review fixes.
  - `python -m pytest tests/test_approval_gate.py tests/test_agent_orchestrator.py tests/test_agent_runtime.py -q --ignore=active_model`:
    110 passed after review fixes.
  - `python -m py_compile agent_runtime/approval.py agent_runtime/__init__.py tests/test_approval_gate.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/approval.py agent_runtime/__init__.py tests/test_approval_gate.py tests/test_agent_orchestrator.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    1048 passed, 8 skipped.

## 2026-05-25 M23 Runtime Approval Gate Wiring Closeout

- Reviewed and closed M23:
  - `agent_runtime.executor.AgentRuntime` now accepts an optional
    `approval_gate`;
  - `run_step()` checks approval before tool policy and handlers;
  - `run()` passes the task id into `run_step()` so approvals are scoped to the
    task being executed.
- Review fixes applied:
  - `run_step()` now accepts optional `task_id` and `worker_id` arguments and
    forwards both to `ApprovalGate.check_step()`;
  - approvals no longer cross task ids when runtime calls steps directly;
  - `run()` uses the task id during approval checks so exact M22 approval
    matching remains effective in full task execution;
  - approval still precedes tool policy, and tool policy/runtime handlers remain
    the second safety layer after approval;
  - M23 source/test additions were cleaned to ASCII comments and top-level
    imports.
- Verification:
  - `python -m pytest tests/test_agent_store.py -q --ignore=active_model`:
    39 passed after review fixes.
  - `python -m pytest tests/test_agent_store.py tests/test_approval_gate.py tests/test_agent_runtime.py -q --ignore=active_model`:
    95 passed after review fixes.
  - `python -m py_compile agent_runtime/executor.py tests/test_agent_store.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/executor.py tests/test_agent_store.py tests/test_approval_gate.py tests/test_agent_runtime.py`:
    no matches.
  - `python -m pytest -q --ignore=active_model`:
    1055 passed, 8 skipped.

## 2026-05-25 M24-M27 Execution Boundary Release Gate Closeout

- Reviewed and closed M24-M27:
  - M24 adds `agent_runtime.tool_exec` with no-op, fake, and blocked shell
    executors; all remain non-executing and report `executed=False`;
  - M25 adds `agent_runtime.audit_trail` for local JSONL audit records;
  - M26 adds operator-facing queue, worker, approval, retry, and status helpers;
  - M27 adds E2E coverage for submit, claim, run, resume, store, approval
    blocking, worker quarantine, audit, and CLI surfaces.
- Review fixes applied:
  - tool executor output now redacts secret-like commands before display;
  - fake executor custom outputs are instance-local and no longer leak into
    later `FakeToolExecutor` instances;
  - audit trail records now redact all string fields before JSONL persistence;
  - `get_audit_trail()` now follows explicit path or environment path changes
    instead of pinning the first global path forever;
  - CLI pending-approval output redacts approval, step, task, and worker ids;
  - M24-M27 types and helpers are exported from `agent_runtime.__init__`;
  - M27 tests were isolated to temp audit paths and cleaned to ASCII.
- Verification:
  - `python -m pytest tests/test_e2e_release.py -q --ignore=active_model`:
    29 passed after review fixes.
  - `python -m pytest tests/test_e2e_release.py tests/test_agent_store.py tests/test_approval_gate.py tests/test_agent_runtime.py tests/test_agent_orchestrator.py -q --ignore=active_model`:
    178 passed after review fixes.
  - `python -m py_compile agent_runtime/tool_exec.py agent_runtime/audit_trail.py agent_runtime/cli.py agent_runtime/__init__.py tests/test_e2e_release.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/tool_exec.py agent_runtime/audit_trail.py agent_runtime/cli.py agent_runtime/__init__.py tests/test_e2e_release.py`:
    no matches.
  - `git diff --check -- agent_runtime/__init__.py agent_runtime/tool_exec.py agent_runtime/audit_trail.py agent_runtime/cli.py tests/test_e2e_release.py`:
    passed.
  - `python -m pytest -q --ignore=active_model`:
    1084 passed, 8 skipped.

## 2026-05-25 M28-M33 Tool Gateway And Operator Hardening Closeout

- Reviewed and closed M28-M33:
  - M28 wires a tool gateway adapter into `AgentRuntime`, including shell,
    HTTP, and run-tests routing when a gateway is present;
  - M29 adds operator approval sessions with evidence formatting;
  - M30 adds feature flags and env allowlists for shell, network, and
    workspace-write gates;
  - M31 adds a bounded workspace sandbox with dry-run preview and rollback;
  - M32 adds domain allowlist and rate-limit network policy checks;
  - M33 adds cross-module release hardening tests.
- Review fixes applied:
  - all new files and tests were cleaned to ASCII;
  - gateway audit events now use stable event names and preserve task/worker
    context on blocked and allowed paths;
  - `RUN_TESTS` routes through the gateway when one is configured;
  - gateway policy blocks dangerous `allowed_tools` even after approval;
  - no-op/fake gateway results are successful simulations, while blocked
    executors return blocked step results;
  - approval sessions redact command, goal, evidence, and operator-facing
    fields in formatted and serialized output;
  - feature flags now require `dry_run=False`, explicit env flags, and parsed
    allowlists before any real execution class is considered allowed;
  - workspace paths use bounded `commonpath` checks and reject path escape even
    during dry-run preview;
  - network domain matching is exact-or-subdomain only, so suffix confusion such
    as `badexample.com` no longer matches `example.com`;
  - contract redaction no longer mistakes normal ids like `task-1` for `sk-`
    secrets, while still redacting real-looking `sk-...` tokens.
- Verification:
  - `python -m pytest tests/test_tool_gateway_adapter.py tests/test_operator_features.py -q --ignore=active_model`:
    45 passed after review fixes.
  - `python -m pytest tests/test_agent_runtime.py tests/test_agent_store.py tests/test_agent_orchestrator.py tests/test_approval_gate.py tests/test_e2e_release.py tests/test_tool_gateway_adapter.py tests/test_operator_features.py -q --ignore=active_model`:
    223 passed after review fixes.
  - `python -m py_compile agent_runtime/contract.py agent_runtime/executor.py agent_runtime/tool_gateway_adapter.py agent_runtime/approval_session.py agent_runtime/feature_flags.py agent_runtime/workspace_sandbox.py agent_runtime/network_policy.py tests/test_tool_gateway_adapter.py tests/test_operator_features.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/contract.py agent_runtime/executor.py agent_runtime/tool_gateway_adapter.py agent_runtime/approval_session.py agent_runtime/feature_flags.py agent_runtime/workspace_sandbox.py agent_runtime/network_policy.py tests/test_tool_gateway_adapter.py tests/test_operator_features.py`:
    no matches.
  - `git diff --check -- agent_runtime/contract.py agent_runtime/executor.py agent_runtime/__init__.py agent_runtime/tool_gateway_adapter.py agent_runtime/approval_session.py agent_runtime/feature_flags.py agent_runtime/workspace_sandbox.py agent_runtime/network_policy.py tests/test_tool_gateway_adapter.py tests/test_operator_features.py`:
    passed.
  - `python -m pytest -q --ignore=active_model`:
    1129 passed, 8 skipped.

## 2026-05-25 M34 Real Executor Disabled Scaffold Closeout

- Reviewed and closed M34:
  - `agent_runtime.real_executor` adds `RealExecutorConfig`,
    `PreflightResult`, `preflight_real_execution()`, and `RealToolExecutor`;
  - the executor remains a scaffold only and always returns `executed=False`.
- Review fixes applied:
  - M34 source and tests were cleaned to ASCII;
  - `RealToolExecutor` now constructs typed `AgentStep` values instead of
    passing raw strings as step kinds;
  - workspace preflight checks the requested command/path instead of an empty
    string;
  - network and workspace all-gates-passed cases are covered and still return
    disabled, non-executed results;
  - audit calls fail closed for caller behavior and catch all sink exceptions;
  - preflight audit detail includes a redacted command preview;
  - M34 types and helpers are exported from `agent_runtime.__init__`.
- Verification:
  - `python -m pytest tests/test_real_executor.py -q --ignore=active_model`:
    18 passed after review fixes.
  - `python -m pytest tests/test_real_executor.py tests/test_tool_gateway_adapter.py tests/test_operator_features.py tests/test_e2e_release.py -q --ignore=active_model`:
    92 passed after review fixes.
  - `python -m py_compile agent_runtime/real_executor.py agent_runtime/__init__.py tests/test_real_executor.py`:
    passed.
  - `rg -n "[^\\x00-\\x7F]" agent_runtime/real_executor.py agent_runtime/__init__.py tests/test_real_executor.py`:
    no matches.
  - `git diff --check -- agent_runtime/real_executor.py agent_runtime/__init__.py tests/test_real_executor.py`:
    passed.
  - `python -m pytest -q --ignore=active_model`:
    1147 passed, 8 skipped.
## 2026-05-25 Joint Debug: Server, LiMa Code, ESP32

- Verified Server to LiMa Code worker contract via public task `92820005`; worker submitted `needs_review` back to Server.
- Restarted stale local Windows router on port `8080`; current process reports `device_gateway=true`.
- Verified local ESP32 fake U8 WebSocket loop against `/device/v1/ws`; all expected acknowledgement frames returned.
- Added tracked public device gateway nginx route and smoke expectation updates; first deployment used memory-only single-node mode and was superseded by the Redis HA deployment below.
- Deployed VPS nginx `/device/` proxy with backup `/root/secure-service-backups/chat.donglicao.com.conf.codex-device-20260525_013718`.
- Verified public device gateway: `https://chat.donglicao.com/device/v1/health` returns JSON, fake U8 completed the `wss://chat.donglicao.com/device/v1/ws` loop, and initial online distribution smoke passed `11/11`.

## 2026-05-25 Device Gateway Redis HA Slice

- Implemented default-off Redis task store for Device Gateway multi-process mode.
- Implemented task-available notification bus so HTTP task producers can wake the process that owns the target device WebSocket.
- Recorded HA runtime switches in the sanitized `lima-router.service` snapshot and online distribution docs.
- Kept Postgres out of the realtime path; it remains a later audit/history store after protocol stabilization.
- Deployed Redis HA mode on VPS with backups:
  - `/opt/lima-router/backups/codex-device-ha-20260525_015208`;
  - `/root/secure-service-backups/lima-router.env.codex-device-ha-20260525_015208`;
  - `/root/secure-service-backups/redis.conf.codex-device-ha-20260525_015305`.
- Verified temporary two-process routing: WebSocket on the public main router received a task created by a private temp router on `127.0.0.1:18080` through Redis notification.
- Verified Redis safety posture: Redis listens on loopback, `redis-cli PING` works on `127.0.0.1`, and VPS self-public check reports `47.112.162.80:6379` blocked.
- Updated online distribution smoke to include public `6379`; latest run passed `12/12` with exact token `ha_redis_guarded_ok`.

## 2026-05-25 Device Gateway Reliable Queue Review Fixes

- Reviewed the Redis HA findings fixes and found two remaining reliability gaps:
  - `ack_processing()` was not called by HTTP or WebSocket `motion_event`
    handlers;
  - the first ack implementation attempted to `LREM` a synthetic JSON payload,
    which did not match the full task payload stored in the processing queue.
- Added failing regression tests first, then fixed the implementation:
  - Redis pending tasks now move to per-device processing queues with `LMOVE`;
  - task state records `processing_started_at` at dispatch time;
  - `ack_processing()` scans processing payloads by `task_id` and removes the
    real queue item;
  - `recover_stale_processing()` uses processing age rather than pending age;
  - requeue removes matching processing entries before pushing back to pending;
  - HTTP and WebSocket `motion_event` paths ack processing entries after
    recording motion events.
- Kept the review hardening from the prior fix pass:
  - `requirements_server.txt` includes `redis>=5.0`;
  - notifier listener/callback exceptions are logged and isolated;
  - task publish failures degrade to queued responses rather than HTTP 500.
- Verification:
  - `python -m pytest tests/test_device_gateway_redis_store.py::test_redis_store_ack_processing_removes_full_processing_task_payload tests/test_device_gateway_redis_store.py::test_redis_store_recovers_by_processing_age_not_pending_age -q --ignore=active_model`:
    2 passed.
  - `python -m pytest tests/test_device_gateway_routes.py::test_events_endpoint_acks_processing_task_after_motion_event tests/test_device_gateway_routes.py::test_websocket_motion_event_acks_processing_task -q --ignore=active_model`:
    2 passed.
  - `python -m py_compile device_gateway\redis_store.py device_gateway\store.py device_gateway\tasks.py device_gateway\notifier.py routes\device_gateway.py server_lifespan.py`:
    passed.
  - `python -m pytest tests/test_device_gateway_protocol.py tests/test_device_gateway_routes.py tests/test_device_gateway_store.py tests/test_device_gateway_concurrency.py tests/test_device_gateway_redis_store.py -q --ignore=active_model`:
    35 passed.
  - `python -m pytest tests/test_agent_task_routes.py tests/test_device_gateway_routes.py tests/test_lima_smoke_task_script.py tests/test_device_gateway_redis_store.py -q --ignore=active_model`:
    49 passed.

## 2026-05-25 Reference Capability Implementation Roadmap

- Added `docs/superpowers/plans/2026-05-25-reference-capability-implementation-roadmap.md`.
- The roadmap turns the admitted external-reference learning into LiMa-native
  execution phases:
  - Device Gateway HA reliability closure;
  - reference implementation ledger;
  - code intelligence and retrieval;
  - memory and mastery;
  - agent/tool governance;
  - MCP access plane;
  - eval, observability, and cost;
  - LiMa Code workflow UX;
  - ESP32/hardware companion expansion.
- Updated `docs/DOCUMENTATION_STATUS.md` so future sessions can find this as
  the active execution roadmap instead of mistaking the broader capability
  radar for completed implementation.

## 2026-05-25 Reference Implementation Ledger Closure

- Added and calibrated `docs/REFERENCE_IMPLEMENTATION_LEDGER.md`.
- The ledger currently tracks 63 reference mappings:
  - `implemented`: 25;
  - `gated`: 7;
  - `concept`: 28;
  - `implementing`: 1;
  - `evaluating`: 1;
  - `rejected`: 1.
- Updated the reference-capability implementation roadmap so Phase 1 is marked
  complete and points to the actual ledger location.
- Updated `docs/DOCUMENTATION_STATUS.md` and `STATUS.md` to treat the ledger as
  the active implementation status source for reference-project learning.
- Verification:
  - ledger status count parsed successfully from the markdown tables;
  - non-ASCII arrows/dashes were normalized to ASCII in the ledger;
  - implementation file spot checks found the main referenced LiMa-owned
    modules such as `backends.py`, `key_pool.py`, `context_pipeline/*`,
    `session_memory/*`, `agent_runtime/*`, `tool_gateway/*`, `lima_mcp/*`,
    `sandbox/provider.py`, `data_workbench/*`, and `provider_automation/*`.

## 2026-05-25 Reference Capability Phase 2-6/8 Closure Review

- Reviewed the Phase 2-8 implementation pass and closed remaining P1/P2 gaps:
  - added tests for previously untested runtime surfaces:
    `lima_mcp/access_plane.py`, `eval_registry.py`,
    `device_gateway/protocol_families.py`, and
    `agent_runtime/summary_constraints.py`;
  - fixed `eval_registry.py` default storage from `D:\data` to repo-local
    `data/eval_registry.jsonl`;
  - fixed eval query limiting so `latest_promoted(limit=1)` returns the latest
    promoted entry instead of the oldest matching entry;
  - hardened worker summary validation so invalid review states and scalar list
    fields are rejected;
  - made `LocalReranker.rerank()` return scored copies instead of mutating input
    candidates and accumulating score drift;
  - normalized protocol-family keys to string values while accepting
    `ProtocolFamily` enum inputs.
- Post-push review hardening:
  - `validate_capability()` now fails closed for inactive protocol families, so
    gated `speech.voice_clone` remains discoverable but cannot validate as
    executable;
  - MCP connector validation now rejects enabled policies with disabled audit
    events, invalid failure modes, or non-positive timeouts.
- Updated `docs/REFERENCE_IMPLEMENTATION_LEDGER.md` and the reference
  capability roadmap with concrete implementation files and test evidence for
  worker summary governance, MCP access plane, eval registry, and Device
  Gateway protocol families.
- Verification:
  - `python -m pytest tests/test_eval_registry.py tests/test_worker_summary_constraints.py tests/test_mcp_access_plane.py tests/test_device_gateway_protocol_families.py -q --ignore=active_model`:
    15 passed.
  - `python -m pytest tests/test_reranker_protocol.py -q --ignore=active_model`:
    7 passed after the non-mutating reranker fix.
  - `python -m pytest tests/test_index_protocol.py tests/test_reranker_protocol.py tests/test_static_analysis.py tests/test_mcp_access_plane.py tests/test_eval_registry.py tests/test_device_gateway_protocol_families.py tests/test_worker_summary_constraints.py tests/test_prompt_memory_recall.py tests/test_typed_memory.py tests/test_tool_gateway.py -q --ignore=active_model`:
    84 passed.
  - `python -m py_compile ...` over touched Python modules:
    passed.
  - `git diff --check`:
    passed.
  - post-review `python -m pytest tests/test_device_gateway_protocol_families.py tests/test_mcp_access_plane.py -q --ignore=active_model`:
    11 passed.
  - post-review `python -m py_compile lima_mcp\access_plane.py device_gateway\protocol_families.py`:
    passed.
  - post-review `git diff --check`:
    passed.
  - post-review `python -m pytest -q --ignore=active_model`:
    1193 passed, 8 skipped.

## 2026-05-25 Project Global VPS Verification Constraint

- Added root `AGENTS.md` as the project-level agent operating constraint file.
- Recorded the user's standing permission for agents to proactively deploy to
  the LiMa VPS when needed for code validation, multi-end joint debugging, and
  faster production usefulness.
- Kept explicit safety requirements:
  - backup before replacing VPS runtime files;
  - scoped deployment diffs;
  - post-restart health/smoke checks;
  - rollback and residual-risk evidence recorded in project docs;
  - no secret exposure, auth weakening, public-port widening, or hardware
    allowlist bypass just to make a smoke pass.

## 2026-05-25 Reference Capability VPS Baseline Deploy

- Deployed local `HEAD` (`ad7cab5`) to VPS `/opt/lima-router` using a local
  `git archive` tarball uploaded to `/tmp/lima-router-20260525_031146.tar`.
- The remote runtime is not a git worktree, so deployment was archive-overlay
  rather than `git pull`.
- Backup and rollback evidence:
  - backup: `/opt/lima-router/backups/codex-baseline-20260525_031146/runtime-before.tgz`;
  - rollback: extract that tarball back into `/opt/lima-router` and restart
    `lima-router`.
- Remote compile passed for:
  - `server.py`, `server_lifespan.py`, `routing_engine.py`, `router_v3.py`,
    `code_orchestrator.py`, `http_caller.py`;
  - `routes/device_gateway.py`, `routes/agent_tasks.py`;
  - `device_gateway/redis_store.py`, `device_gateway/protocol_families.py`;
  - `lima_mcp/access_plane.py`, `eval_registry.py`,
    `agent_runtime/summary_constraints.py`;
  - `context_pipeline/reranker_protocol.py`,
    `context_pipeline/static_analysis.py`, `session_memory/store.py`;
  - `tool_gateway/registry.py`, `tool_gateway/executor.py`.
- Restart and VPS-local checks:
  - `systemctl restart lima-router` completed;
  - `systemctl is-active lima-router`: `active`;
  - `http://127.0.0.1:8080/health`: `status=ok` with modules
    `device_gateway`, `mcp`, `agent_tasks`, and `telegram` true;
  - `http://127.0.0.1:8080/device/v1/health`: Redis task store and Redis
    session bus, listener alive;
  - authenticated `/agent/worker/preflight`: `ready=true`,
    `contract_version=agent-task-v1`, latest task `92820005`.
- Public verification:
  - `python scripts/smoke_online_distributions.py --api-key lima-local --chat-exact baseline_ad7cab5_ok`:
    `12/12 checks passed`;
  - exact chat returned `baseline_ad7cab5_ok`;
  - Device Gateway health reported Redis backend;
  - FRP health passed;
  - public direct access to `8080`, `3003`, `8091`, and `6379` stayed blocked;
  - default fake-U8 token was rejected with `E_UNAUTHORIZED_DEVICE`;
  - public fake U8 WSS loop with configured device token returned
    `hello_ack`, `heartbeat_ack`, `motion_task`, `motion_event_ack`,
    `motion_event_ack`.

## 2026-05-25 V1 Guest Safety Review Closeout

- Reviewed PROD-008 learning loop commit `b372ccc`:
  - `/agent/tasks/{task_id}/result` accepts optional backend/latency metadata
    and feeds sanitized task outcomes into memory, prompt profiles, routing
    feedback, and eval candidates.
  - Confirmed the implementation records evidence only; it does not directly
    mutate route pools or routing weights.
- Reviewed the new WeChat Channel Gateway V1 guest-safety slice:
  - new bindings default to `guest`;
  - `owner` requires `LIMA_CHANNEL_OWNER_HASHES`;
  - guest commands are limited to chat, code explanation, draw preview, demo,
    about, reset, pause/resume, unbind, and help;
  - code-task, device, status, artifact, and memory commands are owner-only;
  - draw stays at preview metadata and does not enqueue Device Gateway work.
- Review fixes applied:
  - owner-only commands now dispatch to explicit owner handler stubs when the
    binding role is `owner`, instead of falling through to an unhandled intent;
  - sidecar authorization now requires the `Bearer` scheme and uses constant
    time comparison.
- Verification:
  - focused Channel Gateway + learning loop tests:
    `106 passed`;
  - guest smoke script:
    `GUEST SMOKE PASSED` with 14 steps;
  - compile check over touched Python modules:
    passed;
  - `git diff --check`:
    passed;
  - secret scan over touched files:
    no real secrets found; matches were test task ids and `agent-task-v1`;
  - full suite:
    `1346 passed, 8 skipped`.

## 2026-05-25 P1.1/P1.2/P1.3 Review Closeout

- Reviewed commit `0509aff`:
  - P1.1 adds `observability/correlation.py`, authenticated
    `/v1/ops/correlate` and `/v1/ops/correlate/summary`, and records chat,
    agent-task, and motion-event touchpoints.
  - P1.2 adds `session_memory/eval_gate.py` plus authenticated
    `/v1/ops/eval/revision` and `/v1/ops/eval/approve`.
  - P1.3 advances `deepcode-cli` to `07f4bdd` with `/lima fix`.
- Review fixes applied:
  - `/v1/ops/correlate?id=...` now matches the documented query shape while
    keeping `request_id`, `task_id`, and `device_id` aliases.
  - Eval approval records now feed back into `revision_check()`, so an
    approved candidate can move from `needs_approval` to `promotable` without
    changing routing automatically.
  - `approve_candidate()` trims pattern keys, rejects empty/oversized keys,
    and caps rollback notes before writing typed memory.
- Verification:
  - focused P1 tests:
    `59 passed`;
  - compile check over touched Python modules:
    passed;
  - `git diff --check`:
    passed;
  - full suite:
    `1348 passed, 8 skipped`.
- Deployment decision:
  - VPS deploy +联调 is required because the slice changes authenticated ops
    APIs and hot paths in chat, agent task submission, and Device Gateway
    motion events.
- VPS deployment verification:
  - deployed commit `645a6fc` over `/opt/lima-router`;
  - remote backup captured at
    `/opt/lima-router/backups/p1-review-20260525_113033/runtime-before.tgz`;
  - remote compile check passed for `server.py`, ops routes, agent task routes,
    device gateway routes, correlation, eval gate, and learning loop modules;
  - `systemctl restart lima-router` returned `active`;
  - local VPS `/health` returned status `ok` with `channel_gateway=true`;
  - authenticated local ops smoke passed for `/v1/ops/metrics`,
    `/v1/ops/correlate/summary`, `/v1/ops/correlate?id=missing-smoke`, and
    `/v1/ops/eval/revision`;
  - public ops smoke passed for correlate summary, documented `id=...`
    correlate lookup, and eval revision;
  - `python scripts/smoke_online_distributions.py --api-key lima-local --chat-exact p1_review_ok`:
    `12/12 checks passed`, exact chat returned `p1_review_ok`, Device Gateway
    health reported Redis backend, FRP health passed, and public direct access
    to `8080`, `3003`, `8091`, and `6379` stayed blocked.
- Rollback note:
  - restore the backup tarball into `/opt/lima-router` and restart
    `lima-router` if a production regression appears.

## 2026-05-25 Eval Apply And Owner Handler Review Closeout

- Reviewed the owner-command and eval-apply follow-up slice:
  - `/v1/ops/metrics` now reports learning-loop stats for prompt recall,
    routing weights, and eval gate candidates;
  - `/v1/ops/eval/apply` applies manually approved eval candidates to routing
    weights only after explicit approval;
  - WeChat owner commands now dispatch real handlers for code task, device,
    status, artifact, and memory.
- Review fixes applied:
  - `/code-task` now reuses the formal Agent Task creation path so
    `request.task_id`, validation, persistence, and `created` events match the
    LiMa Code worker contract;
  - `apply_promotion()` is idempotent even when the original `promoted:*`
    memory is older than the most recent 30 reference memories;
  - `/v1/ops/eval/apply` returns stable 400 responses for malformed JSON,
    non-object JSON, and missing `pattern_key`;
  - P1.4 fake-device tests now assert real preview, failed-task no-queue, and
    multi-device queue behavior instead of weak smoke-only conditions.
- Local verification:
  - targeted regressions:
    `3 passed`;
  - focused Channel, Device Gateway, learning, ops, and agent task tests:
    `95 passed, 2 skipped`;
  - P1.4 stability loop with `--stability-rounds 20`:
    `8 passed, 1 skipped`;
  - compile check over touched Python modules:
    passed;
  - `git diff --check`:
    passed;
  - full suite:
    `1359 passed, 10 skipped`.
- VPS deployment verification:
  - remote backups:
    `/opt/lima-router/backups/review-fix-20260525_123901/runtime-before.tgz`
    and
    `/opt/lima-router/backups/review-fix-json-20260525_124238/runtime-before.tgz`;
  - remote compile passed for channel gateway, ops metrics, eval gate, and
    prompt recall modules;
  - `systemctl restart lima-router` returned `active`;
  - VPS-local `/health` returned status `ok` with `channel_gateway=true`;
  - authenticated local `/v1/ops/metrics` returned the new `learning` block;
  - authenticated local `/v1/ops/eval/apply` returned 400 for malformed JSON
    and non-object JSON instead of 500;
  - public `/v1/ops/eval/revision` returned 200;
  - `python scripts/smoke_online_distributions.py --api-key lima-local --chat-exact review_fix_ok`:
    `12/12 checks passed`, exact chat returned `review_fix_ok`, Device Gateway
    health reported Redis backend, and public direct access to `8080`, `3003`,
    `8091`, and `6379` stayed blocked.
- Rollback note:
  - restore the latest backup tarball into `/opt/lima-router` and restart
    `lima-router` if the eval/apply or owner-command runtime regresses.

## 2026-05-25 CLAUDE.md And Code Quality Plan Review

- Reviewed the pending `CLAUDE.md` inventory update against current source
  counts, hot-path files, and security boundaries.
- Created `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` with:
  - a correctness review of the `CLAUDE.md` changes;
  - corrected repository statistics where measured values drifted;
  - prioritized P0/P1/P2/P3 improvement slices;
  - per-slice files, implementation steps, verification commands, and VPS
    gates.
- Verification evidence reused from this review session:
  - focused code-quality regressions: `18 passed`;
  - full suite: `1471 passed, 10 skipped`;
  - `git diff --check`: passed.

## 2026-05-25 Code Quality Plan P0/P1 Implementation (CQ-085)

- Implemented `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` slices P0.1 through P1.2:
  - **P0.1**: `BodySizeLimitMiddleware` buffers/replays ASGI body before Starlette;
    chunked oversize returns `413` without delivering full payload to handlers.
  - **P0.2**: `/api/live-key` returns capability metadata only (no raw `GOOGLE_AI_KEY`).
  - **P0.3**: `deploy/key_rotation.py` retired; legacy moved to
    `scripts/archive/key_rotation_legacy.py`.
  - **P1.1**: `semantic_cache.put()` logs SQLite failures and exposes `db_write_errors`.
  - **P1.2**: `admin_login` uses `constant_time_equals`.
- Tests:
  - focused: `20 passed` (http body, system endpoints, semantic cache, admin csrf, secret hygiene);
  - full suite: `1477 passed, 10 skipped`;
  - `git diff --check`: passed.
- Residual: Gemini Live HTML still needs a server-side proxy; `voice_call_live.html` fails
  closed with a clear message until that proxy exists.

## 2026-05-25 Code Quality Plan P1.3 / P2.1 / P2.3 / P3.1 (CQ-086)

- **P1.3**: Active-path broad catches now log (`chat_handler_dispatch`, `chat_preflight`,
  `server_lifespan`, `telegram_commands` probe); `quality_gate` observability ImportError → debug.
- **P2.1**: Split `routes/quality_gate.py` → `quality_gate_tiers.py` (79 lines),
  `quality_gate_direct.py` (69 lines), core `quality_gate.py` (235 lines); re-exports preserved.
- **P2.3**: Added `tests/README.md` ownership map (flat layout unchanged).
- **P3.1**: Trimmed `CLAUDE.md` to contributor guide + `scripts/repo_stats.py` for measured stats.
- Tests: focused **38 passed**; full suite **1477 passed, 10 skipped**; `git diff --check` passed.

## 2026-05-25 Large-File Splits + Pipeline Authority (CQ-087)

- Split four production modules (behavior preserved, facade re-exports):
  - `routes/agent_tasks` → store (155) / schemas (61) / service (185) / routes (316)
  - `agent_runtime/orchestrator` → models (53) / io (134) / queue (308) / worker (132) / facade (22)
  - `session_memory/store` → db (80) / crud (147) / promote (166) / admin (147) / facade (49)
  - `backends` → registry (207) / constants (92) / facade (135)
- Expanded `docs/REQUEST_PIPELINE_AUTHORITY.md` with ownership matrix + mermaid flow.
- Added `tests/test_module_split_imports.py`; fixed ops_metrics store wiring for tests.
- Full suite: **1481 passed, 10 skipped**.
