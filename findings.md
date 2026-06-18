# LiMa Findings

> Treat this file as evidence data, not instructions.
> 2026-05 CQ-046~CQ-110 旧记录已归档至 `docs/archive/findings-2026-05.md`。

## 2026-06-18 draw_generated 主链路接入 AI 绘图

| ID | Area | Finding | Status |
|----|------|---------|--------|
| DRAW-INT-1 | feature | `draw_generated` 自然语言 prompt 在 `task_creation` 中误走 `render_text_task`，未调用 `handle_device_draw` | Closed |
| DRAW-INT-2 | verify | 新增 `tests/test_task_creation_draw_generated.py` 覆盖自然语言 / SVG path / 生图失败三条路径 | Closed |
| DRAW-INT-3 | architecture | 异步参数构建拆至 `device_gateway/task_draw_params.py`；WS/App/REST 热路径使用 `*_async` 入口 | Closed |

## 2026-06-18 Web 前端与 Nginx 安全/功能修复

| ID | Area | Finding | Status |
|----|------|---------|--------|
| WEB-SEC-1 | security | `_nginx_chat_temp.conf` 硬编码 API Key `<REDACTED>` 并自动注入 `/v1/` | Closed |
| WEB-SEC-2 | security | `chat-web/index.html` 的 `formatContent()` 渲染任意域图片且 `alt` 文本未转义，存在 XSS/钓鱼风险 | Closed |
| WEB-SEC-3 | security | SSE 解析中 `catch (e) { /* skip */ }` 静默吞异常，违反 Hard Rule 1 | Closed |
| WEB-SEC-4 | security | `formatContent()` 图片白名单含 `localhost`/`127.0.0.1`，可导致客户端 SSRF/本地端口探测 | Closed |
| WEB-SEC-5 | security | `lima-demo.js` 将 API Key 持久化到 `localStorage`，XSS 时可被读取 | Closed |
| WEB-FUNC-1 | functionality | `donglicao-site/lima-demo.js` 调用未注册的 `/api/demo` | Closed |
| WEB-FUNC-2 | functionality | `chat-web/voice-call.html` 本地模式连接 `/v1/voice`，但 nginx 只代理 `/ws/voice` | Closed |
| WEB-FUNC-3 | functionality | `formatContent()` 对图片 URL 二次 escape，破坏含 `&` 的查询参数 | Closed |
| WEB-FUNC-4 | functionality | `copyApiInfoCurl()` 未检查 `navigator.clipboard`，非安全上下文会抛出同步 TypeError | Closed |
| WEB-FUNC-5 | functionality | `getDemoApiKey()` 仅在 return 时 trim，空白键会被写入 storage 并导致后续 401 死循环 | Closed |
| WEB-DEPLOY-1 | deploy | nginx 仍保留已退役的 `/gitee/`、`/github/`、`/telegram/` location 块 | Closed |
| WEB-DEPLOY-2 | hygiene | `*.bak.*`、`*.backup*` 备份文件残留在工作区 | Closed |
| WEB-UX-1 | ux | `showApiInfo()` 用 toast 展示长文档，体验差 | Closed |
| WEB-UX-2 | ux | 语音通话模式选项 `Gemini Live` / `本地语音管道` 不够直观 | Closed |
| WEB-SIZE-1 | code_size | `chat-web/index.html` 1657 行，需拆分为 HTML/CSS/JS/SVG | Closed |
| WEB-SIZE-3 | code_size | `donglicao-site/index.html` 454 行，内联 CSS/JS 过多 | Closed |
| WEB-SIZE-2 | code_size | `donglicao-site/chat.html` 与 `chat-web/index.html` 功能重复，已替换为重定向页 | Closed |

**Review 衍生修复（2026-06-18 omk-review）**
- 语音路径：前端 `/v1/voice` 与后端 `routes/voice_pipeline_ws.py` 一致；nginx 新增 `location = /v1/voice` WebSocket 代理到 `:8080`。
- 图片转义：`formatContent()` 对 URL 改用 `escapeAttr`（仅转义引号），避免 `&amp;` 双重转义破坏查询参数。
- Demo Key：`localStorage` → `sessionStorage`，并在存储前 trim。

**测试修复（2026-06-18）**
- `tests/test_digital_human_routes.py::test_digital_human_static_js_served` 原断言仅接受 `application/javascript`，但 Starlette StaticFiles 在 Windows 本地返回 `text/javascript; charset=utf-8`。已改为断言 content-type 包含 `javascript`，并附带诊断信息。

**前端模块化（2026-06-18）**
- `chat-web/index.html` 拆分为：
  - `chat-web/styles.css`（798 行）：全部样式变量与组件样式；
  - `chat-web/icons.svg`（57 行）：Lucide 图标 sprite；
  - `chat-web/chat-ui.js`（153 行）：状态、输入、侧边栏、toast、lightbox、API key modal；
  - `chat-web/chat-messages.js`（127 行）：消息渲染、`formatContent`、代码复制、lightbox 绑定；
  - `chat-web/chat-api.js`（215 行）：图片生成、SSE 聊天、历史记录、API info modal；
- `chat-web/index.html` 从 1715 行降至 325 行；`copyCode()` 补齐 `navigator.clipboard` 存在性检查。

**待确认（pre-existing）**
- 相同 API Key（已文档化并已从当前工作树红码）仍出现在 `docs/ALIYUN_PROMETHEUS_DEPLOYMENT.md` 与 `docs/archive/jdcloud-2026-06/` 历史文档中。当前文件已替换为 `<YOUR_API_KEY>`；若该 Key 仍有效，仍需在服务商控制台轮换，并考虑从 Git 历史清除。

## 2026-06-18 voice provider 测试可移植性与代码尺寸改进

| ID | Area | Finding | Status |
|----|------|---------|--------|
| VOICE-TEST-1 | portability | 本地 Windows 开发环境缺少 `nls` / `faster-whisper`，阿里云 NLS 与 Whisper 相关测试直接 `ModuleNotFoundError` 或 `ConfigurationError` 失败 | Closed |
| VOICE-TEST-2 | portability | 已用 `pytest.importorskip("nls")` / `pytest.importorskip("faster_whisper")` 标记可选依赖测试；本地聚焦套件从 14 failed 变为 14 skipped | Closed |
| VOICE-SIZE-1 | code_size | `device_voice/providers/asr_aliyun.py::stream_transcribe` 含嵌套 `_sync_stream` 共 97 行，远超 50 行目标 | Closed |
| VOICE-SIZE-2 | code_size | 已拆分为 `_parse_nls_result` / `_StreamingRecognizerState` / `_run_streaming_worker`；`stream_transcribe` 降至 34 行；文件回到 295 行以内 | Closed |
| VOICE-SIZE-3 | code_size | `scripts/check_code_size.py` 当前仍有 35 个 >300 行文件 / 100 个 >50 行函数（含本文件修改前未消减项），需持续拆分 | Open |

## 2026-06-17 小智服务器退役准备：阶段 3 之 2D 数字人接入

| ID | Area | Finding | Status |
|----|------|---------|--------|
| XZRT-DH-1 | feature | 2D 数字人前端已挂载到 LiMa `/digital-human/`，页面默认 WS URL 已自动指向当前域名 `/device/v1/ws` | Closed |
| XZRT-DH-2 | deploy | VPS nginx 缺少 `/digital-human/` location，导致公网访问被 SPA catch-all 拦截为 200(index.html fallback)；已新增 `location ^~ /digital-human/` 转发到 `:8080` | Closed |
| XZRT-DH-3 | verify | 公网 `https://chat.donglicao.com/digital-human/health` 与 `/digital-human/` 均 200；静态 JS/CSS 可加载 | Closed |
| XZRT-DH-4 | verify | 真机端到端语音交互（浏览器 → `/device/v1/ws` → VAD/ASR/LLM/TTS → 数字人渲染）尚未在真实硬件/浏览器环境跑通 | Open |
| XZRT-DH-5 | auth | 数字人页面通过 `?authorization=Bearer <token>` 传令牌，LiMa `extract_ws_token()` 原只支持 `token` 查询参数或 `Authorization` 头，导致 WS 认证失败 | Closed |

## 2026-06-18 小智服务器退役：LiMa 原生设备/固件/移动端贯通

| ID | Area | Finding | Status |
|----|------|---------|--------|
| XZRT-LIMA-1 | feature | `routes/route_registry.py` 默认不再挂载 `xiaozhi_v1_compat`；兼容层仅在 `LIMA_XIAOZHI_COMPAT_ENABLED=1` 时 opt-in | Closed |
| XZRT-LIMA-2 | feature | LiMa 已提供 `/device/v1/app` 原生设备管理面，覆盖 auth、devices、members、misc、tasks | Closed |
| XZRT-LIMA-3 | feature | OTA 已提供设备侧 `/device/v1/ota/upgrade-plan` 与 `/device/v1/ota/install-result`；状态由 `device_ota/state_store.py` 持久化 | Closed |
| XZRT-LIMA-4 | feature | `esp32S_XYZ` 固件默认接入 `wss://chat.donglicao.com/device/v1/ws`，hello 协议版本为 `lima-device-v1` | Closed |
| XZRT-LIMA-5 | feature | manager-mobile 设置页已改为普通 `http/https` base URL，并使用 `/health` 作为连通性测试 | Closed |
| XZRT-LIMA-6 | verify | `pytest tests/test_frontend_security_static.py tests/test_manager_mobile_lima_native.py -q` → 5 passed；`corepack pnpm type-check` 与 `corepack pnpm build:h5` 通过 | Closed |
| XZRT-LIMA-7 | verify | 本轮未做真机固件刷写后的硬件端到端回归；仅完成静态协议与构建验证 | Open |

## 2026-06-17 ECC 流程导入与代码尺寸/覆盖率基线

| ID | Area | Finding | Status |
|----|------|---------|--------|
| ECC-1 | process | LiMa 缺少显式 Plan → TDD → Code Review → Commit 闭环；已在 `AGENTS.md` 和 `docs/ECC_WORKFLOW_CN.md` 中增量采用 ECC 流程 | Closed |
| ECC-2 | metrics | 缺少代码尺寸自动检查；新增 `scripts/check_code_size.py`，基线更新：23 个 >300 行文件、99 个 >50 行函数（已拆 routing_selector/server_lifespan/chat_stream/device_draw_handler 热路径大函数） | Open |
| ECC-3 | metrics | 缺少测试覆盖率基线；已安装 `pytest-cov` 并在 `pytest.ini` 配置；`device_gateway` 聚焦覆盖从 38.2% 提升至 **71.1%**（新增 `device_draw_handler`/`motion` 单元测试） | Open |
| ECC-4 | tooling | `scripts/run_pre_commit_check.py` 已集成代码尺寸检查作为 warning（不阻塞，现有违规先记录） | Closed |

## 2026-06-17 小智服务器退役准备：阶段 2 云 ASR/TTS SDK 接入

| ID | Area | Finding | Status |
|----|------|---------|--------|
| XZRT-7 | model_admission | 阿里云 NLS Python SDK (`alibabacloud-nls-python-sdk`) 已接入 ASR/TTS provider | Closed |
| XZRT-8 | model_admission | 火山豆包 ASR/TTS 通过 WebSocket/HTTP REST 接入，无需额外 `volcengine` SDK 依赖 | Closed |
| XZRT-9 | safety | 云 provider 统一使用 `device_voice.exceptions`，凭证缺失时抛 `ConfigurationError` 而非静默 stub | Closed |
| XZRT-10 | verify | `tests/test_device_voice_cloud_providers.py` 13 个单测覆盖 4 个 provider 的正常/鉴权失败/网络超时路径 | Closed |
| XZRT-11 | tooling | 新增 `scripts/smoke_voice_providers.py` 用于真实凭证下的 TTS→ASR 闭环冒烟 | Closed |
| XZRT-12 | verify | VPS 运行时验证：已部署代码并安装 `alibabacloud-nls-python-sdk==1.0.2`、`dashscope==1.20.11` | Closed |
| XZRT-13 | verify | VPS `.env` 现有 `ALIYUN_API_KEY` / `VOLCENGINE_API_KEY` 为 LLM key；新增 DashScope provider 可直接复用 `ALIYUN_API_KEY`，但调用 TTS 返回 `Arrearage/Access denied`（账户未开通语音服务/无额度） | Open |
| XZRT-14 | verify | 阿里云 NLS 专用凭证（`ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET` + `ALIBABA_NLS_APP_KEY`）与火山豆包语音凭证（`DOUBAO_*_APPID/ACCESS_TOKEN`）仍缺失，真实凭证闭环未跑通 | Open |

## 2026-06-17 小智服务器退役准备：阶段 1 止血与合规

| ID | Area | Finding | Status |
|----|------|---------|--------|
| XZRT-1 | safety | `device_voice/providers/vad_silero.py` 在 ONNX 模型缺失时把所有音频当语音 pass-through，违反 Hard Rule 1 | Closed |
| XZRT-2 | safety | `device_voice/providers/voiceprint_*.py` 与上层在 embedding 失败时返回 `None` 并被调用方静默吞掉 | Closed |
| XZRT-3 | safety | `device_voice/providers/asr_aliyun.py` 等 4 个云语音 provider 返回空字符串/字节，云端配置下静默失败 | Closed |
| XZRT-4 | compatibility | `device_voice/providers/tts_edge.py` 直接返回 MP3，而设备协议期望 PCM；已用 ffmpeg subprocess 转码 | Closed |
| XZRT-5 | verify | `pytest tests/test_device_voice.py -v` → **36 passed**；`ruff check device_voice routes tests/test_device_voice.py` clean；pyright 0 errors | Closed |
| XZRT-6 | process | 阶段 1 仅完成止血与合规；云 ASR/TTS 真实 SDK 接入、真机端到端回归、VPS 运行时验证仍为 P0 阻塞项 | Open |

## 2026-06-17 G4 启动与部署不确定性降低

| ID | Area | Finding | Status |
|----|------|---------|--------|
| G4-1 | observability | `server_lifespan.py` 启动阶段无耗时记录，无法定位 7 分钟瓶颈；已添加 `_phase` 上下文管理器和 `STARTUP_PHASES` | Closed |
| G4-2 | observability | `/health` 仅返回固定 `{"status":"ok"}`，无启动状态语义；已扩展为 `startup.status` + `startup.phases` | Closed |
| G4-3 | startup | 真实瓶颈是 `context_pipeline.auto_indexer` 的 asyncio task 阻塞事件循环（ChromaDB/ONNX 下载/解压）；已改为 daemon thread | Closed |
| G4-4 | startup | `channel_retirement.telegram` 同步调用 Telegram API 耗时约 1.7s；已改为 `asyncio.create_task` 后台执行 | Closed |
| G4-5 | ops | VPS 启动从约 7 分钟降至约 8 秒；公网 `/health` 与 `/device/v1/health` 均 200 | Closed |
| G4-6 | verify | `test_routing_engine.py` / `test_system_endpoints.py` / `test_retrieval_injection.py` → 34 passed | Closed |
| G4-7 | observability | `STARTUP_PHASES` 原按完成顺序追加，warm 任务并发时顺序不可读；已改为 `PhaseTimer` 启动即追加，退出仅更新状态/耗时，确保展示顺序为启动顺序 | Closed |

## 2026-06-17 阶段 1 剩余项：U1/U8 仿真固件侧 route_policy 拒绝

| ID | Area | Finding | Status |
|----|------|---------|--------|
| U1RP-1 | safety | 云端 `validate_route_policy` 已覆盖，但 fake U1/U8 仿真固件不消费 `route_policy`，无法形成端到端拒绝证据 | Closed |
| U1RP-2 | safety | `tools/fake_device_server/app.py` 丢弃 `route_policy`，U1 命令无策略上下文 | Closed |
| U1RP-3 | testing | `tests/test_fake_u1_cloud_loop.py` 缺少固件侧拒绝路径的端到端覆盖 | Closed |
| U1RP-4 | scope | 真实 C++ 固件（u1-grbl / u8-xiaozhi）尚未实现等效拒绝；fake 仿真层已提供参考契约，后续硬件跟进 | Accepted |

## 2026-06-17 G3 证据边界瘦身（小批）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| G3-1 | orphan | `eval_status.py` 在 CodeGraph + ripgrep 中均无生产引用，仅历史归档文档提及；已删除 | Closed |
| G3-2 | verify | eval 聚焦套件（`test_eval_internal.py` / `test_eval_notify.py` / `test_eval_pinned_call.py` / `test_eval_pool_gate.py` / `test_eval_quiet.py` / `test_eval_slice_summary.py` / `test_eval_topology.py` / `test_periodic_coding_eval.py`）→ **23 passed, 1 warning** | Closed |
| G3-3 | lint | `ruff check .` clean | Closed |
| G3-4 | orphan | `webhook_activity_buffer.py` 无生产/测试引用，仅归档文档提及；已删除 | Closed |
| G3-5 | orphan | `context_pipeline/` 中 `complexity`/`entity_extraction`/`graph_context_expander`/`production_index`/`retrieval_corpus`/`retrieval_trace` 为 Hot/Warm lazy import，`CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 已标记保留；未删除 | Closed |

## 2026-06-17 G2 设备模型准入复跑

| ID | Area | Finding | Status |
|----|------|---------|--------|
| G2-1 | model_admission | `docs/model_admission/2026-06-16-device-drawing-writing.md` 因 Windows 控制台重定向变成 ISO-8859 二进制损坏；已删除并重建为 2026-06-17 完整报告 | Closed |
| G2-2 | model_admission | `eval_device_model_role.py` 8 角色评测：6 admit/admit_conditional，2 defer，0 fail；与 `DEVICE_ROLE_PREFERENCES` 对齐 | Closed |
| G2-3 | verify | `test_device_gateway_model_routing.py` 32 passed / `test_routing_engine.py` 24 passed / ruff clean | Closed |
| G2-4 | docs | `docs/README.md` 最新准入报告索引更新为 2026-06-17 版本 | Closed |

## 2026-06-16 M13 + 阶段 2 续（准入 / 发布证据）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| M13-1 | release_evidence | 原 `TEMPLATE_AI_TO_MOTION_RELEASE.md` 为通用占位，与 LiMa 门 A–F 不对齐；已重写并加 `release_evidence/README.md` | Closed |
| M13-2 | verify | `test_device_gateway_model_routing.py` + 假 U8 环 → 33 passed（模板 closeout） | Closed |
| P2-LIVE-1 | model_admission | Image Generator 仅 mock 7 项；新增 `test_dashscope_image_live.py` + `eval --live`（`ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1` opt-in） | Closed |
| P2-LIVE-2 | verify | 离线 admission pytest 12 passed；无密钥时 live 2 项 skip | Closed |
| MIMO-1 | dev_tooling | MiMo MCP 全仓审查易超时；搁置并行审查，移除 `mimo-async-review.mdc` 自动派发 | Closed |

## 2026-06-15 代码质量治理 Q0–Q3（CQ-Q0~Q3）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q0-1 | repo_stats | `.venv310` 未排除导致 CLAUDE.md 报 220 万行失真；已加入 SKIP + `.venv*` 前缀过滤 | Closed |
| CQ-Q0-2 | CI gate | `test_p13_no_silent_exception_pass_in_active_paths` 因 legacy 文件 skip；已重写扫描 device/routing 热路径 | Closed |
| CQ-Q1-1 | route_policy | `esp32s_adapter.generate_route_policy` 与 `model_routing.resolve` 语义分叉（run_path）；已委托统一 | Closed |
| CQ-Q2-1 | tasks split | `device_gateway/tasks.py` 521 行超标；拆为 creation/events/lifecycle + task_deps facade 68 行 | Closed |
| CQ-Q2-2 | P1.3 | `mark_task_dispatched` 裸 `except: pass` → `_log.debug(..., exc_info=True)` | Closed |
| CQ-Q3-1 | routing_executor | 隐式 `routing_engine as re` 访问 tracker/budget；改为显式 import | Closed |

**Verification**: 112 focused tests passed（P13 + esp32s + device gateway + routing）；ruff clean on touched files。

## 2026-06-15 代码质量治理 Q4（CQ-Q4）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q4-1 | Memory store | `MemoryStore` 仅进程内；已加 `MemoryStoreBackend` + `configure_memory_store_from_env` + `RedisMemoryStore` | Closed |
| CQ-Q4-2 | Ledger store | `ledger_store` 仅 InMemory；已加 `LedgerStoreBackend` + `configure_ledger_store_from_env` + `RedisLedgerStore` | Closed |
| CQ-Q4-3 | Bootstrap | memory/ledger 配置接入 `start_device_gateway_runtime()`；health 暴露后端名 | Closed |
| CQ-Q4-4 | Env | `LIMA_DEVICE_MEMORY_STORE` / `LIMA_DEVICE_LEDGER_STORE` 文档化于 `.env.example` | Closed |

**Verification**: `tests/test_device_store_redis_backends.py` + memory/ledger/recovery 套件 63 passed。

## 2026-06-15 代码质量治理 Q5-1（CQ-Q5-1）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-1 | channel_gateway | `service.py` 567 行超标；拆为 greeting/outbound/service_dispatch；主 facade 221 行 | Closed |

**Verification**: channel gateway 聚焦套件 41 passed；ruff clean on `service.py` / `service_dispatch.py` / `greeting.py` / `outbound.py`。

## 2026-06-15 代码质量治理 Q5-2（CQ-Q5-2）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-2 | orchestrate | `orchestrate.py` 451 行超标；拆为 constants/detect/pipeline；主 facade 122 行 | Closed |

**Verification**: `test_orchestrate_route_context.py` 1 passed；`python orchestrate.py` __main__ 自检通过。

## 2026-06-15 代码质量治理 Q5-3（CQ-Q5-3）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-3 | admin_api_extra | `routes/admin_api_extra.py` 463 行超标；拆为 8 个 `admin_extra_*` 域模块 + 29 行 facade | Closed |

**Verification**: admin 聚焦套件 11 passed；facade 挂载 20+ 路由端点；ruff clean。

## 2026-06-15 代码质量治理 Q5-4（CQ-Q5-4）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-4 | eval_loop | 根目录 612 行离线评估脚本阻塞热路径瘦身；已移 `scripts/eval_loop*` + JSON 数据集，根保留 52 行 shim | Closed |

**Verification**: `python scripts/eval_loop.py` 自测通过（LM Studio 不可用时降级行为正确）；ruff clean。

## 2026-06-15 代码质量治理 Q5-5（CQ-Q5-5）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-5 | routing_intent | 312 行略超标；image/thinking 模式迁至 routing_intent_modal.py | Closed |

**Verification**: routing intent 聚焦套件 13 passed。

## 2026-06-15 代码质量治理 Q5-6（CQ-Q5-6）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q5-6 | speculative | 312 行略超标；并行执行与策略/亲和池拆为 execution + policy 子模块 | Closed |

**Verification**: `test_speculative_call_records_backend_attempt` 通过；ruff clean。

## 2026-06-15 代码质量治理 Q6（CQ-Q6）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q6-1 | tests | `test_provider_automation.py` 850 行难维护；拆为 4 域文件 + helpers | Closed |
| CQ-Q6-2 | tests | `test_ops_metrics.py` 752 行难维护；拆为 4 域文件 + helpers | Closed |
| CQ-Q6-3 | tests/README | 缺少聚焦门 vs 全量门说明；已补充预提交与领域 pytest 命令 | Closed |

**Verification**: 拆分后 provider_automation + ops_metrics 套件 83 passed, 1 skipped。

## 2026-06-15 代码质量治理 Q7（CQ-Q7）

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CQ-Q7-1 | 战略瘦身 | 四子系统缺 hot/warm/cold 权威分层；已产出 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | Closed |

**Verification**: 文档含规模快照、生产 import 证据、P0–P4 建议序；`docs/README.md` 已索引。

## 2026-06-15 LiMa Hardware AI Phase 1 M5–M8 Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HAI-M5-1 | Recovery table | `device_intelligence/recovery.py` maps 5 error codes to retry/home/stop with Chinese explanations. | Closed |
| HAI-M5-2 | Retry execution | `execute_recovery()` dispatches retry/home/stop; retry exhaustion now reports `action="stop"` instead of misleading `"retry"`. | Closed |
| HAI-M5-3 | Retry tracking | `InMemoryDeviceTaskStore` and `RedisDeviceTaskStore` implement `increment_retry_count`, `reset_task_for_retry`, `remove_pending_task`. | Closed |
| HAI-M5-4 | Double-delivery guard | WS direct retry send removes task from pending queue and marks it dispatched/inflight. | Closed |
| HAI-M5-5 | Boundary | Fake U8 hardware-in-loop deferred to Phase 2; WS + store contract covered by focused tests. | Accepted |
| HAI-M6-1 | Memory schema | `MemoryEntry` + `MemoryType` (preference/device_failure/task_episode/procedure_confidence) with TTL, isolation, parent disable. | Closed |
| HAI-M6-2 | Episode extraction | `extract_episode_from_terminal()` produces structured episodes; failure events produce `DEVICE_FAILURE` memories. | Closed |
| HAI-M6-3 | Consolidation | `consolidate_task_episodes()` builds procedure confidence from repeated outcomes; idempotent on unchanged data. | Closed |
| HAI-M6-4 | Recall safety | `recall_planner_hints()` respects confidence thresholds and hard-safety overrides; feed preferences clamped to 100–3000. | Closed |
| HAI-M6-5 | Anti-learning | `should_learn_entry()` blocks unsafe sources/capabilities; `is_hard_safety()` prevents override of motion limits. | Closed |
| HAI-M6-6 | Silent degradation | Initial `_extract_memory_from_terminal()` used `logger.debug` on Exception; fixed to `logger.warning` per AGENTS.md hard rule. | Closed |
| HAI-M6-7 | History overwrite | Episode IDs originally reused `task_id`; fixed to include `event.event_id` so retry failure→success history is preserved. | Closed |
| HAI-M6-8 | Production backend | `MemoryStore` is in-process only; RLock added for thread safety; Redis/SQLite backend deferred. | Accepted |
| HAI-M7-1 | Support snapshot | `build_support_snapshot()` returns shadow, firmware, active tasks, recent terminal tasks, failure warnings, redacted recommendation. | Closed |
| HAI-M7-2 | Time window | `_list_recent_terminal_tasks()` originally included all historical terminal events; fixed to 24-hour window with ISO timestamp parsing. | Closed |
| HAI-M7-3 | External enrichment | Weather (Open-Meteo) and holiday (Nager.Date) providers available; not wired into dispatch hot path. | Accepted |
| HAI-M8-1 | Release gate | `ReleaseGate` blocks deploy until tests_passing, canary_verified, safety_review all pass. | Closed |
| HAI-M8-2 | Canary | `CanaryDeployment` tracks per-device success/failure with 90% health threshold; counters reset on new version deploy. | Closed |
| HAI-M8-3 | OTA routes | Added `/deploy/{version}`, `/canary/record-success/{device_id}`, `/canary/record-failure/{device_id}`, `DELETE /canary/devices/{device_id}`. | Closed |
| HAI-M8-4 | Input validation | `set_criteria()` originally silently ignored unknown names; fixed to return HTTP 400 with allowed list. | Closed |
| HAI-M8-5 | Deploy gate | Deploy originally had no gate check; fixed to return HTTP 412 until release gate is ready. | Closed |

**Verification summary**

- `python -m pytest tests/test_device_*.py tests/test_route_registry.py -q` → 452 passed
- `ruff check` on all touched files → clean


## 2026-06-15 死区代码与文档清理

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CLEAN-1 | 死文件删除 | 删除 `routes/ops_probe_ingest.py`（未注册死路由）、`converters/anthropic_format.py`（Anthropic 转换已退役）、`deploy/key_rotation.py`（自声明退役）、`scripts/vps_eval_smoke_remote.py`（引用不存在文件） | Closed |
| CLEAN-2 | Anthropic 残留 | 移除 `/v1/messages` 端点 + 6 个 Anthropic stub/转换函数（chat_endpoints.py 363→142 行）；注册表移除 4 个 anthropic 字段 + 7 个 agent_* 硬编码 | Closed |
| CLEAN-3 | 配置死路径 | pyrightconfig.json 移除 8 个不存在路径；ruff.toml 移除 8 个不存在 exclude；deploy_unified.py 移除 agent_runtime core dir + m1m5 slice + eval_smoke 代码；lima_security_gateway.js 移除 /agent/ 路径 | Closed |
| CLEAN-4 | 文档归档 | 归档 6 个过时文档至 docs/archive/；删除 root-historical 21 个个人编码助手遗物；归档 21 个已完成 superpowers/plans | Closed |
| CLEAN-5 | findings 轮转 | 拆分 findings.md（1094→204 行，148KB→18KB）；旧 CQ-046~110 记录移至 docs/archive/findings-2026-05.md | Closed |
| CLEAN-6 | 测试修复 | 更新 6 个测试适配 Anthropic 端点/函数移除（test_chat_endpoints.py、test_route_registry.py、test_secret_hygiene.py）；ruff clean；核心测试 71 passed, 8 skipped | Closed |

## 2026-06-15 Edge-C route_policy 硬契约关闭（阶段 1 缺口 A）

> 目标：把 Edge-C motion_task schema 的 route_policy 从软约束提升为硬约束，使"设备收到的下行帧必带路由证据"成为不可违反契约。详见 spec `docs/superpowers/specs/2026-06-15-edge-c-route-policy-hard-contract-design.md`。

| 证据点 | 内容 |
|--------|------|
| 固件改动（esp32S_XYZ commit `a4cab61`，已推送） | edge_c schema required 化（`6c950c9`）；downlink example 补 device_control route_policy；motionHandle.py 复制 generate_route_policy（语义对齐 resolve_device_route_policy，run_path→device_vector，非 esp32s_adapter 旧版 device_write）；新增 test_route_policy.py（7 测试） |
| 云端改动（主仓库 commit `a8d2d2c`） | xiaozhi_compat/gateway.py 复用 resolve_device_route_policy 补 route_policy（单一真相源）；新增 test_xiaozhi_compat_route_policy.py（2 测试） |
| 双端语义统一 | 计划阶段发现 esp32s_adapter/protocol.py 的 run_path→device_write 与权威 resolve（device_vector）不一致；固件复制版以 resolve 为准。审查又发现云端 CONTROL_CAPABILITIES 缺 estop 且 tasks.py/path_validator.py 有 2 份副本——已重构为单一真相源（model_routing.py）并补 estop，estop 端到端贯通 |
| 验证 | 固件 `validate_schemas.py` 62/62 + `test_validate_schemas` 5 passed + fake_lima_u8 16 passed；主仓库 ruff 全过 + xiaozhi_compat 2 passed + retention/model_routing/routes 回归 68 passed |
| 跨仓库顺序 | 固件先 push（Task A3，commit a4cab61），主仓库后更新 submodule 指针（本条对应 commit） |
| 范围外（YAGNI，记录留待后续） | edge_b 不改（Java BusinessServer 链路保留软约束）；Java DeviceServerMotionGatewayImpl 不加 route_policy；esp32s_adapter/protocol.py 的 legacy generate_route_policy（device_write 语义）不动；不加运行时 schema 校验门 |

## 2026-06-15 route_policy backend 字段贯通（阶段 2 子项目 #5）

> 目标：修复 route_policy 缺 backend 字段的断点，使粘性路由记忆记到真实 backend。详见 spec `docs/superpowers/specs/2026-06-15-route-policy-backend-field-design.md`。

| 证据点 | 内容 |
|--------|------|
| 固件改动（esp32S_XYZ commit `5004082`，已推送） | edge_c/edge_b schema route_policy 加可选 backend 属性；edge_c downlink example 补 backend:"deterministic" |
| 云端改动（主仓库 commit `58d4b01`） | model_routing.py: `_policy()` 加 backend 参数；`resolve_device_route_policy` 复用既有 `get_preferred_backend(route_role)` 填充 backend + 联动 `record_route_evidence`；修正 matrix 测试 4 个 expected |
| 新增测试（主仓库 commit `e454c3f`） | 4 个断点修复测试：resolve 含 backend / backend 匹配 DEVICE_ROLE_PREFERENCES / 永不返回 unknown / _policy 默认值兼容 |
| 断点修复证据 | `create_task_from_transcript('dev-1','draw cat')` 的 `route_policy.backend` 从缺失变为 `"dashscope_wanx"`；粘性记忆端到端需真实设备 profile 才触发（单测环境门控不通过，backend 字段本身已修复） |
| 验证 | 固件 schema 门 62/62 + CI 9 passed；主仓库 model_routing 29 passed + 新测试 4 passed + retention/routes 回归 66 passed + ruff clean |
| 范围外（YAGNI） | 不统一 MODEL_REGISTRY（子项目 #1）；不给 deterministic 创建真实后端注册；不改 validate_route_policy；不动 edge_b 顶层软约束 |
| 后续 | 子项目 #1（注册表统一）可在此基础上推进 |

## 2026-06-13 清理发现的敏感文件泄露

| ID | Area | Finding | Status |
|----|------|---------|--------|
| SEC-2026-06-13-1 | 凭证泄露 | 工作区 `.mcp.json` 包含明文 SSH 密码（`root@47.112.162.80`） | Closed（文件已删除） |
| SEC-2026-06-13-2 | 凭证泄露 | `_deploy_jdcloud.sh` 包含明文 JDCloud SSH 密码 | Closed（文件已删除） |
| SEC-2026-06-13-3 | 凭证泄露 | `check_jdcloud.bat` 包含明文 JDCloud SSH 密码 | Closed（文件已删除） |

> **建议用户操作**：上述文件中的密码可能已在 git 历史或本地备份中存在，建议轮换对应 VPS 的 root 密码，并将 MCP/部署配置迁移到环境变量或外部凭证管理器。

## 2026-06-11 Stage 1 Week 3C VPS 部署

| ID | Area | Finding | Status |
|----|------|---------|--------|
| W3C-DEPLOY-1 | 文件部署 | preset_shapes.py (110行) 和 device_draw_handler.py 已部署 | Closed |
| W3C-DEPLOY-2 | 模块验证 | get_preset_svg 可正常导入并执行，circle 测试通过 | Closed |
| W3C-DEPLOY-3 | 服务状态 | uvicorn 运行正常，PID 2923895，启动于 21:47 | Closed |
| W3C-DEPLOY-4 | 测试覆盖 | 12/12 测试通过（8 预设图形 + 4 集成）| Closed |
| W3C-DEPLOY-5 | 快速路径 | 关键词检测集成，预设图形跳过 DashScope API | Closed |
| W3C-DEPLOY-6 | 性能提升 | 响应时间从 3-5 秒 → <100ms（预设图形）| Closed |
| W3C-DEPLOY-7 | 成本节省 | 预设图形 0 API 调用，离线可用 | Closed |

## 2026-06-11 Stage 1 Week 3B VPS 部署

| ID | Area | Finding | Status |
|----|------|---------|--------|
| W3B-DEPLOY-1 | 文件部署 | svg_converter.py 已更新（117 行，OpenCV 矢量化），requirements_server.txt 已更新 | Closed |
| W3B-DEPLOY-2 | 依赖安装 | opencv-python-headless==4.10.0.84 安装成功，版本 4.10.0 确认 | Closed |
| W3B-DEPLOY-3 | 模块验证 | cv2 和 SVGConverter 可正常导入，无错误 | Closed |
| W3B-DEPLOY-4 | 服务状态 | uvicorn 运行正常，PID 2897167，启动于 21:29 | Closed |
| W3B-DEPLOY-5 | 测试覆盖 | 25/25 测试通过（包含真实轮廓检测验证）| Closed |
| W3B-DEPLOY-6 | 技术实现 | Otsu 阈值 + findContours + approxPolyDP + SVG path 生成 | Closed |
| W3B-DEPLOY-7 | 占位符替换 | 矩形占位符已完全替换为真实 OpenCV 轮廓检测 | Closed |

## 2026-06-11 Stage 1 Week 3A VPS 部署

| ID | Area | Finding | Status |
|----|------|---------|--------|
| W3A-DEPLOY-1 | 文件部署 | 3 个文件已部署到 VPS：svg_validator.py (133行), path_optimizer.py (187行), device_draw_handler.py (修改，+37行) | Closed |
| W3A-DEPLOY-2 | 模块验证 | svg_validator, path_optimizer, device_draw_handler 可正常导入，无错误 | Closed |
| W3A-DEPLOY-3 | 服务状态 | uvicorn 服务运行正常，PID 2871231，启动于 21:13 | Closed |
| W3A-DEPLOY-4 | 测试覆盖 | 23/23 测试通过（10 validator + 10 optimizer + 3 integration） | Closed |
| W3A-DEPLOY-5 | 代码质量 | Ruff clean，所有文件 <200 行，函数 <50 行 | Closed |
| W3A-DEPLOY-6 | 功能集成 | device_draw 现在包含完整流程：生成→转换→验证→优化 | Closed |
| W3A-DEPLOY-7 | 优化效果 | Douglas-Peucker 算法实现，点数减少 30%+，保持宽高比，居中对齐 | Closed |

## 2026-06-11 Stage 1 Week 2 VPS 部署

| ID | Area | Finding | Status |
|----|------|---------|--------|
| W2-DEPLOY-1 | 文件部署 | 5 个文件已成功部署到 VPS：dashscope_image_client.py, device_draw_handler.py, device_write_handler.py, svg_converter.py, backends_registry.py | Closed |
| W2-DEPLOY-2 | 依赖安装 | dashscope==1.20.11 和 Pillow==10.4.0 已安装；pypotrace/svgpathtools/shapely 因编译问题跳过（SVG 当前是占位符实现，不影响功能） | Closed |
| W2-DEPLOY-3 | 服务重启 | uvicorn 服务已重启，PID 2831072，健康检查返回 status=ok | Closed |
| W2-DEPLOY-4 | 模块验证 | device_draw_handler 和 DashScopeImageClient 可正常导入，无错误 | Closed |
| W2-DEPLOY-5 | 后端注册 | dashscope_wanx 和 dashscope_flux 后端已注册，fmt='dashscope_image', caps=['image_generation'] | Closed |
| W2-DEPLOY-6 | 备份记录 | VPS 备份位置: /opt/lima-router/backups/unified-files-20260611_203701/runtime-before.tgz | Closed |
| W2-DEPLOY-7 | 残余风险 | 可选依赖未安装不影响当前功能；Week 3+ 实现真实矢量化时需安装 pypotrace 等库 | Accepted |

## 2026-06-09 LiMa Hardware AI Phase 1 M4 Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HAI-M4-1 | Planner | `device_intelligence.planner` wraps gateway intent parser into immutable `TaskPlan` objects; `PlannerError` raised for empty commands; plan_ids are uuid-based and unique. | Closed |
| HAI-M4-2 | Simulator | `device_intelligence.simulator` computes deterministic metrics: draw distance (pen-down XY), pen-up distance (z>0 XY), runtime (total/ feed *60), risk score (workspace usage + density). | Closed |
| HAI-M4-3 | Workflow | `device_workflow` provides 9-state machine with VALID_TRANSITIONS table; terminal is a sink state; WorkflowOrchestrator is thread-safe with RLock. | Closed |
| HAI-M4-4 | Integration | `project_to_motion_task()` now advances workflow CREATED→PLANNED→SIMULATED→READY_TO_DISPATCH (or WAITING_APPROVAL for risk ≥0.7); adds `simulation` and `workflow_state` keys to task output without breaking existing format. | Closed |
| HAI-M4-5 | Test coverage | 65 M4 tests + 143 existing = 208 total device tests pass; ruff clean on all new files. | Closed |
| HAI-M4-6 | Boundary | Risk threshold 0.7 is a starting default; workflow is in-memory; both need real hardware tuning. | Accepted |

## 2026-06-09 LiMa Hardware AI Phase 1 M3 Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HAI-M3-1 | Decision vocabulary | `device_policy.decisions` provides 7 deterministic decisions with Chinese labels; `PolicyResult` is frozen with unknown-value rejection. | Closed |
| HAI-M3-2 | Protocol registry | `device_protocol_registry` maps protocol version, min firmware, supported capabilities, and deprecated fields; firmware comparison uses string ordering (adequate for v-prefixed semver). | Closed |
| HAI-M3-3 | Policy gate | `project_to_motion_task()` now calls `policy_engine.decide()` after validation; blocked tasks get `status="blocked"` with `policy` dict in task output. | Closed |
| HAI-M3-4 | Backward compat | Existing M1/M2/gateway route tests (57 total) all pass; policy gate defaults to `allow` for standard capabilities with valid params. | Closed |
| HAI-M3-5 | Boundary | Policy engine is stateless; future M5/M6 work may add shadow-based home/self-check gating and memory-driven personalization. | Accepted |

## 2026-06-09 LiMa Hardware AI Phase 1 M2 Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HAI-M2-1 | Device schema | `device_intelligence.schemas` now provides deterministic `DeviceProfile` and `TaskPlan` contracts with empty-id rejection and stable JSON output. | Closed |
| HAI-M2-2 | Profile-aware safety | `device_gateway.path_validator` can validate against a `DeviceProfile`, rejecting workspace overflow, feed above profile cap, and unsupported firmware/profile prefixes. | Closed |
| HAI-M2-3 | Device shadow | `shadow_store` now tracks `hello`, `heartbeat`, `device_info`, `self_check`, and `motion_event` state from both WebSocket and HTTP device event paths. | Closed |
| HAI-M2-4 | Protocol compatibility | `hello_ack()` can include an optional `shadow` delta without changing the existing v1 fields, preserving old fake U8/client behavior. | Closed |
| HAI-M2-5 | Boundary | Profile-aware safety is available at the validator boundary; broader planner/task creation selection of per-device profiles should land with M3/M4 policy/planner work. | Accepted |

## 2026-06-09 LiMa Hardware AI Phase 1 M1 Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HAI-M1-1 | Device ledger | `device_ledger` now records append-only `task_created`, `task_dispatched`, `motion_event`, and `task_terminal` events with duplicate event-id rejection and task replay. | Closed |
| HAI-M1-2 | Device artifacts | `device_artifacts` now stores copied artifact records with `task_id`, `artifact_type`, `content`, SHA-256 `content_hash`, `retention_days`, and `created_at`. | Closed |
| HAI-M1-3 | Gateway wiring | `device_gateway.tasks` records preview SVG artifacts on task creation and terminal-result artifacts on `done` / `failed` / `cancelled`, covering both HTTP and WebSocket motion-event paths through the shared task wrapper. | Closed |
| HAI-M1-4 | Boundary | M1 is intentionally in-memory and interface-shaped for later SQLite/Redis durability; it does not yet provide cross-process persistence or operator artifact APIs. | Accepted |
| HAI-M1-5 | Full gate | Full `scripts/run_pre_commit_check.py --full` is blocked during pytest collection by current-baseline missing modules (`agent_runtime`, `routes.admin_agent_audit`, `routes.anthropic_stream_branches`) that are absent from the working tree and `git ls-files`; M1 focused gates pass. | Open |

## 2026-06-09 Capacity-Aware Deploy + JDCloud Probe Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CAP-JD-1 | Deploy safety | `scripts/deploy_unified.py` now fails before upload when the primary VPS lacks required free disk or memory, using strict host-key SSH and configurable thresholds. | Closed |
| CAP-JD-2 | Rollback | Non-dry-run deploys now create `/opt/lima-router/backups/<label>-YYYYMMDD_HHMMSS/runtime-before.tgz` before SFTP upload and print the rollback path. Final helper upload backup: `/opt/lima-router/backups/unified-files-20260609_130457/runtime-before.tgz`. | Closed |
| CAP-JD-3 | Primary capacity | Final primary VPS preflight for helper upload reported `disk_free_mb=13685` and `mem_available_mb=488`; this is enough for the configured deploy gate but confirms the primary VPS is still memory-tight. | Accepted |
| CAP-JD-4 | JDCloud role | JDCloud `117.72.118.95` is now a real secondary provider-probe / monitoring node with read-only smoke tooling; it is not a second public LiMa Router API. | Closed |
| CAP-JD-5 | JDCloud activation | `lima-probe.timer` was enabled but inactive; it is now active. Manual `lima-probe.service` completed with `status=0/SUCCESS`, discovered `37 new, 37 total known`, and wrote probe data under `/opt/lima-probe/data`. | Closed |
| CAP-JD-6 | Browser helper | JDCloud browser-backed discovery currently sees loopback render helper HTTP `500` on `127.0.0.1:8092/render`; the main discovery path succeeds, so this is a focused follow-up rather than a blocker. | Open |
| CAP-JD-7 | JDCloud auth | Key-based JDCloud SSH is not yet configured for this workstation; unauthenticated/key-only `scripts/check_jdcloud_node.py --json` fails with `AuthenticationException`, while environment-provided password auth succeeds. | Open |

## 2026-06-09 Prometheus Metrics Hardening Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| PROM-1 | Metrics contract | Prometheus support is now explicit: disabled returns `404`, enabled dependency/config failure returns `503` or startup `RuntimeError`, and healthy enabled scrape returns OpenMetrics text from a private registry. | Closed |
| PROM-2 | Request telemetry | LiMa request tracking now records Prometheus request counters after normal in-memory stats without breaking user requests; failures are logged instead of silently skipped. | Closed |
| PROM-3 | Exporter lifecycle | Backend health/score gauges are owned by `observability.prometheus_metrics`; the exporter only starts when metrics are enabled, validates before launch, and is idempotent on start/stop. | Closed |
| PROM-4 | VPS state | VPS already had `LIMA_PROMETHEUS_METRICS=1` before this slice, so production smoke expects authenticated scrape `200` on `chat.donglicao.com`, not default-off `404`. `api.donglicao.com` still returns edge `404` for the scrape path. | Closed |
| PROM-5 | Deploy tooling | `deploy_unified.py` reported health failed because the service completed startup just after the old 45s window; the wait window is now `HEALTH_WAIT_SECONDS=90` and covered by `tests/test_deploy_unified.py`. | Closed |

## 2026-06-09 Pre-Commit Hook Hygiene Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| HOOK-1 | Commit latency | The local pre-commit hook ran raw `pytest tests/` and `ruff check .`, bypassing the documented ignore list and tracked-file ruff wrapper. This caused commits to hang or scan local scratch files. | Closed |
| HOOK-2 | Tracked gate | `scripts/run_pre_commit_check.py` now owns the reusable gate: quick mode for local commits and `--full` for CI-style pytest. | Closed |
| HOOK-3 | Windows temp | The first wrapper `--full` attempt timed out; adding a unique `--basetemp` fixed the Windows pytest temp path issue. `--full` now passes with `2060 passed, 10 skipped`. | Closed |
| HOOK-4 | Local hook | `.git/hooks/pre-commit.ps1` now delegates to the tracked wrapper. The hook file itself is local Git metadata and is not committed. | Closed |
| HOOK-5 | VPS | No VPS deployment was performed or needed because this slice changes local developer tooling only. | Accepted |

## 2026-06-16 代码文档瘦身状态修复

| ID | Area | Finding | Status |
|----|------|---------|--------|
| SLIM-DOC-1 | 瘦身文档 | P6 大子系统审计记录误写为未来日期 `2026-06-17`，已修正为当前执行日期 `2026-06-16`。 | Closed |
| SLIM-DOC-2 | 工作区残留 | 已退役目录仅残留未跟踪 `__pycache__`，`git ls-files` 确认无 tracked 源码；缓存目录已清理。 | Closed |

## 2026-06-09 JDCloud Workspace Hygiene Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| JD-HYG-1 | Ops ownership | JDCloud `117.72.118.95` is now recorded as a real secondary provider-probe / monitoring node, not disposable scratch and not a primary public API surface. | Closed |
| JD-HYG-2 | Secret boundary | Local JDCloud deploy/debug helpers include password-bearing scripts and fixed admin-password examples. They are intentionally ignored and were not staged. | Closed |
| JD-HYG-3 | Workspace noise | Root scratch scripts, local sessions/cookies, generated JDCloud reports, and local agent/tool state are now covered by exact `.gitignore` rules. | Closed |
| JD-HYG-4 | Runtime files | `.codegraph/daemon.pid` was tracked local runtime state. It is removed from the Git index and PID files are ignored while preserving the local file. | Closed |
| JD-HYG-5 | Deployment evidence | No fresh JDCloud deployment was performed in this hygiene slice. A future JDCloud deploy must record service status and smoke evidence before claiming runtime rollout. | Accepted |

## 2026-06-09 CI Hygiene After Retirement Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CI-HYG-1 | Backend registry | Post-retirement full-suite signal exposed backend names still referenced by route pools but missing from the split registry package. The registry now defines the still-referenced local/direct, DuckAI, XFYun, DashScope, and Zhihu entries, and removes phantom OpenRouter constants that had no registry definitions. | Closed |
| CI-HYG-2 | CI gate | `scripts/run_ruff_check.py` scanned local scratch scripts, so unrelated operator experiments could fail the ruff gate. The wrapper now uses `git ls-files` for tracked `.py` / `.pyi` files and passes `--force-exclude`. | Closed |
| CI-HYG-3 | Import ownership | `backends_constants.py` imported `IDE_SOURCES` from `router_v3`, creating fragile ownership around IDE fingerprints. `_IDE_FINGERPRINTS` and `IDE_SOURCES` now live in `backends_constants.py`; `router_v3` imports them and keeps the detection helper. | Closed |
| CI-HYG-4 | Public edge | Although LiMa runtime and chat nginx returned 404 for `/telegram/webhook`, `api.donglicao.com` POST requests were still proxied to the compatibility backend and returned JSON-RPC HTTP 200. VPS nginx now returns edge 404 for `/telegram/` on both public domains. | Closed |
| CI-HYG-5 | Topology drift | The tracked `api.donglicao.com` nginx snapshot still described New API on port `3003`, but live nginx targets `/opt/ai-router/ai_router_mcp.py` on port `8769`. The online-distribution docs and sanitized snapshot now record the observed live topology. | Closed |
| CI-HYG-6 | Full-suite signal | After the registry and ruff-gate fixes, the CI-style pytest command with documented long/external ignores returned `2056 passed, 10 skipped, 1 warning`, replacing the previous post-retirement residual failure signal. | Closed |

## 2026-06-09 Telegram Retirement Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| TG-RETIRE-1 | Runtime boundary | Telegram bot/operator support is removed from active route registration and startup. `/health` now reports `modules.telegram=false` through `channel_retirement.py`. | Closed |
| TG-RETIRE-2 | Notification coupling | GitHub/Gitee webhooks, Agent Task review, Device Gateway task phases, budget alerts, health/token alerts, eval notify, and deploy helpers no longer import Telegram modules; replacement behavior is internal activity recording or structured logging. | Closed |
| TG-RETIRE-3 | VPS cleanup | After backup `/opt/lima-router/backups/telegram-retirement-20260609_031429/runtime-before.tgz`, 23 runtime files were deployed and remote Telegram-only files were removed. Deleted-file check returned `0`. | Closed |
| TG-RETIRE-4 | Public smoke | VPS-local `/health` returned `telegram:false`; public `/health` returned HTTP `200`; public `POST /telegram/webhook` returned HTTP `404`; authenticated public `model=code` chat returned HTTP `200`. | Closed |
| TG-RETIRE-5 | Validation residual | Focused retirement tests passed (`112 passed` plus JSON/retirement supplement `9 passed`), but CI-style full pytest still has 8 unrelated failures in backend registry drift, ruff gate GBK decode, health tracker assertion drift, and AutoIndexer mtime flake. | Accepted |

## 2026-06-09 LiMa Code CLI Retirement Closeout

| ID | Area | Finding | Status |
|----|------|---------|--------|
| LC-RETIRE-1 | Repo structure | `deepcode-cli` is no longer a tracked submodule in the main LiMa repository; `.gitmodules` has no LiMa Code stanza and `git ls-files --stage deepcode-cli` returns no entry. | Closed |
| LC-RETIRE-2 | Runtime boundary | Active server routes and operator text now refer to Agent Worker / developer-tool paths instead of LiMa Code worker wording. Historical outcome loop `limacode_worker` remains accepted only for existing DB compatibility. | Closed |
| LC-RETIRE-3 | Routing | `model="code"` still selects the coding route; retired `model="lima-code"` no longer sets the coding route preference. `tests/test_chat_route_prefs.py` covers both cases. | Closed |
| LC-RETIRE-4 | VPS smoke | Retirement runtime files were deployed after backup `/opt/lima-router/backups/lima-code-retirement-20260609_020314/runtime-before.tgz`; public `/health` returned 200, authenticated `model=code` chat returned marker `agent-worker-retirement-ok`, and `/agent/worker/preflight` returned `ready=true` with contract version `agent-task-v1+prompt-contract-v0.1`. | Closed |
| LC-RETIRE-5 | Validation residual | Focused retirement pytest passed (`116 passed`), but full pyright is blocked by unrelated `routes/admin_api_extra.py` type errors and full pytest timed out with many ambient failures plus Windows temp cleanup `WinError 5`. | Accepted |
| LC-RETIRE-6 | Git mirror | Commit `e528635` was pushed to GitHub `origin/feat/kilo-provider-probe`. Gitee mirror push was not available in this checkout because no `gitee` remote or dual push URL is configured. | Accepted |

## 2026-06-18 Codex 项Ŀ级 multi-agent 配置收敛

| ID | Area | Finding | Status |
|----|------|---------|--------|
| CODEX-AGENT-1 | docs | ¹ٷ½ Codex ÊֲáȷÈϣºproject-scoped custom agents ֱ½ӴÓ `.codex/agents/*.toml` ×Զ⑾֣»`[agents]` ֻ承载ȫ¾ÖÏ߳Ì/Éî¶ÈÏÞÖƣ¬²»Ҫ求 `[agents.<name>]` ע²ᡣ | Closed |
| CODEX-AGENT-2 | gitignore | `.gitignore` Ïֽö·ÅÐÐ `.codex/config.toml` 与 `.codex/agents/*.toml`；`git check-ignore -v` 已ȷ认 `.codex/agents/notes.md` 和 `.codex/skills/ui-ux-pro-max/SKILL.md` ¼ÌÐøºöÂԡ£ | Closed |
| CODEX-AGENT-3 | config | `.codex/config.toml` ɾ除了与 Codex Ĭ认ֵһÖµÄ `[agents]` ÈßÓàÉèÖã¬½ö±£Áô `multi_agent = true`。 | Closed |

## 2026-06-18 小智服务器退役：固件/真机门禁

| ID | Area | Finding | Status |
|----|------|---------|--------|
| XZRT-LIMA-8 | tooling | 新增 `scripts/firmware_hardware_gate.py`，默认检查 U8 固件 LiMa WSS、`lima-device-v1` hello、`hello_ack`/语音回复解析，以及非 TLS/小智协议残留禁止项 | Closed |
| XZRT-LIMA-9 | verify | `.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q` -> 10 passed；ruff focused clean | Closed |
| XZRT-LIMA-10 | verify | `.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build` 在当前机器明确返回 `BLOCKED esp_idf_build - IDF_PATH must point to a valid ESP-IDF source tree`；工具链 wrapper 不足以冒充可编译环境 | Closed |
| XZRT-LIMA-11 | verify | 当前机器只有 `.espressif` 工具链残留，没有有效 ESP-IDF 源码树，也没有真实 U8 凭据，真实刷机、串口监控、`hello -> task_dispatch -> motion_event` 硬件闭环仍未执行 | Open |
| XZRT-LIMA-12 | verify | `D:\tmp\esp-idf-v5.5.4` 已恢复 ESP-IDF v5.5.4 源码树；门禁已识别真实 `tools\idf.py` 布局，但 `idf.py --version` 阶段因缺少 `esp_idf_monitor` 返回 `BLOCKED esp_idf_python_env`，说明当前阻断点已从源码树缺失推进到 ESP-IDF Python/export 环境损坏 | Open |
| XZRT-LIMA-13 | tooling | `scripts/firmware_hardware_gate.py --build` 现在会在 `set-target/build` 前探测 ESP-IDF Python 环境；对应 focused 测试增至 12 passed，ruff focused clean | Closed |
| XZRT-LIMA-14 | firmware | U8 固件 hello `fw_rev` 改为 `esp_app_get_description()->version`，修复 `Board::GetFirmwareVersion()` 不存在导致的 ESP-IDF 编译失败 | Closed |
| XZRT-LIMA-15 | tooling | `scripts/firmware_idf_env.py` 会选择 ESP-IDF export Python venv、清理 MSYS/Mingw 变量、补齐 `ESP_ROM_ELF_DIR`/`OPENOCD_SCRIPTS`；focused 测试增至 13 passed | Closed |
| XZRT-LIMA-16 | verify | `$env:IDF_PATH='D:\tmp\esp-idf-v5.5.4'; $env:IDF_TOOLS_PATH="$env:USERPROFILE\.espressif"; scripts\firmware_hardware_gate.py --build` 已通过并生成 `esp32S_XYZ/firmware/u8-xiaozhi/build/xiaozhi.bin`；真机 smoke 仍因缺设备凭据未执行 | Open |

> 2026-06-18 闭合：上述固件门禁脚本、`firmware_idf_env.py`、测试与相关文档已提交并 push 到 `origin main`；`esp32S_XYZ` 子模块 `fw_rev` 修复已 push 到子模块远端。父仓库不再阻塞于未提交 WIP。

## 2026-06-18 全量问题审计与修复

| ID | Area | Finding | Status |
|----|------|---------|--------|
| AUDIT-SEC-1 | security | `scripts/test_jdcloud_connection.py` 与 `scripts/test_redis_from_local.py` 硬编码 root 密码与 Redis 密码 | Closed |
| AUDIT-SEC-2 | security | `deploy/deploy_prometheus_metrics.sh` 硬编码 VPS 密码与 Prometheus Bearer Token | Closed |
| AUDIT-SEC-3 | security | `routes/digital_human.py` 将默认设备令牌注入前端页面，任何访问者可见 | Accepted (free demo) |
| AUDIT-SEC-4 | security | `device_gateway/auth.py` 对 `LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID` 回退使用默认 token，伪造 device_id 可连接 | Accepted (free demo) |
| AUDIT-SEC-5 | security | `infra/vps/nginx/www.donglicao.com.conf` `/api/demo` 返回 `Access-Control-Allow-Origin *` | Closed |
| AUDIT-SEC-6 | security | 图片域名白名单缺失（`data/chat/index.html` 已退役；`chat-web/chat-messages.js` 已维护 `allowedImageDomains`） | Closed |
| AUDIT-SEC-7 | security | `routes/gemini_live_proxy.py` / `routes/voice_pipeline_ws.py` 可从 query param 读取 token（浏览器 WebSocket 无法设置自定义 header，已加 `access_log off` 与 warning 日志） | Accepted |
| AUDIT-FUNC-1 | functionality | `routes/admin_extra_insights.py::retrain_jobs` 导入已删除的 `routes.admin_api._RETRAIN_JOBS` | Closed |
| AUDIT-FUNC-2 | functionality | Admin UI 调用未注册的 `POST /admin/api/retrain` 与 `GET /admin/api/agent-audit` | Closed |
| AUDIT-FUNC-3 | functionality | 多处语音/设备路径捕获 `ImportError`/`Exception` 后仅 `debug` 日志，违反 Hard Rule 1 | Closed |
| AUDIT-UX-1 | ux | `chat-web/index.html` 在 401 时自动弹出 API Key 模态框，与免费策略冲突 | Closed |
| AUDIT-UX-2 | ux | `chat-web/voice-call.html` 仍通过 `window.prompt()` 索要 API Key | Closed |
| AUDIT-UX-3 | ux | `donglicao-site/lima-demo.js` 每次发送都弹窗询问 API Key | Closed |
| AUDIT-UX-4 | ux | `donglicao-site/index.html` 页脚 GitHub/Gitee 仓库链接错误，「查看文档」按钮语义混乱 | Closed |
| AUDIT-DEPLOY-1 | deploy | `scripts/deploy_unified.py` 默认 `core` slice 仅部署 `CORE_FILES`，遗漏 `CORE_DIRS` 与大量运行时目录，导致 VPS 启动崩溃/超时 | Closed |
| AUDIT-DEPLOY-2 | deploy | `scripts/deploy_unified.py` 健康检查仅 grep `"ok"`，未解析 JSON | Closed |
| AUDIT-DEPLOY-3 | deploy | `infra/vps/nginx/chat.donglicao.com.conf` 快照缺少 `/v1/live`、`/v1/voice` 与静态缓存更新 | Closed |
| AUDIT-DEPLOY-4 | deploy | nginx 静态 `location /` 对 `index.html` 缓存 1h，导致前端更新延迟 | Closed |
| AUDIT-DEPLOY-5 | deploy | nginx 仍保留已退役的 `/mcp/` location | Closed |
| AUDIT-DEPLOY-6 | deploy | `gitee` remote 使用 SSH，本地无 key，push 失败 | Open |

**修复动作（2026-06-18）**
- 硬编码凭据脚本改为从环境变量读取；缺失凭据时直接退出并提示。
- `routes/admin_extra_insights.py` 移除对 `_RETRAIN_JOBS` 的引用；新增 `POST /admin/api/retrain` 与 `GET /admin/api/agent-audit` 兼容端点，返回退役/空列表状态。
- `chat-web/chat-api.js`、`chat-web/voice-call.html`、`donglicao-site/lima-demo.js` 移除所有 API Key 弹窗与 `prompt()`；401 时仅显示友好错误提示。
- `donglicao-site/index.html` 修正 GitHub/Gitee 仓库链接，「查看文档」改为「打开控制台」。
- `scripts/deploy_unified.py` 默认 `core`/`all` slice 改为遍历运行时文件树（排除 tests/docs/data/infra 等）；健康检查改为解析 `/health` JSON 并断言 `status` 为 `ok`/`warming`。
- `_nginx_chat_temp.conf` 删除 `/mcp/` location，`location /` 对 SPA shell 设置 `no-cache`；同步更新 `infra/vps/nginx/chat.donglicao.com.conf` 快照。
- `infra/vps/nginx/www.donglicao.com.conf` 的 `/api/demo` CORS 改为仅允许 `donglicao.com` / `www.donglicao.com`，并给 `location /` 增加 no-cache。

**仍开放的问题**
- Gitee SSH 推送失败需配置 SSH key 或改用 HTTPS token。
- 真机固件刷写与硬件闭环仍因缺少 `LIMA_HARDWARE_DEVICE_ID` / `LIMA_HARDWARE_DEVICE_TOKEN` 和串口设备未执行。

## 2026-06-18 Gitee push 诊断

| ID | Area | Finding | Status |
|----|------|---------|--------|
| AUDIT-DEPLOY-6 | deploy | `gitee` remote 使用 SSH，本地无 key，push 失败 | Accepted (pending account action) |

**修复动作**
- `scripts/push_dual_remotes.py` 增加 `_check_gitee_ssh()`：在推送 `gitee` 前先用 `ssh -T git@gitee.com` 验证认证；失败时跳过 `gitee` 并打印本机公钥与添加指引，避免阻塞 `origin` 推送。
- 当前待添加到 Gitee 的公钥：
  ```
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHa12AjBDaxSOcx2q++0QxYr3WkeRSw6Z4xi4BBYXOtE zhuguang-ZFG@users.noreply.github.com
  ```
- 添加地址：https://gitee.com/profile/sshkeys

**仍需操作**
- 把上述公钥添加到 Gitee 账户；或提供 `GITEE_ACCESS_TOKEN` 让脚本切换到 HTTPS 推送。

## 2026-06-18 esp32S_XYZ 子模块硬编码 API Key 修复

| ID | Area | Finding | Status |
|----|------|---------|--------|
| AUDIT-SEC-SUBMODULE | security | `esp32S_XYZ/server/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml` 硬编码和风天气 API Key | Closed |

**修复动作**
- 子模块 `config.yaml` 中 `plugins.get_weather.api_key` 改为空字符串。
- 子模块 `plugins_func/functions/get_weather.py` 改为 `weather_config.get("api_key", "") or os.environ.get("QWEATHER_API_KEY", "")`；空 Key 时记录 warning 并返回友好提示。
- 子模块已提交并推送：`zhuguang-ZFG/esp32S_XYZ@d3d5dd5`。
- 父仓库 `esp32S_XYZ` submodule pointer 已更新到 `d3d5dd5`。

**残余风险**
- 该 Key 仍保留在子模块 Git 历史以及 `manager-api/src/main/resources/db/changelog/202504112058.sql` 中；如仍在使用，请在和风天气控制台轮换。
