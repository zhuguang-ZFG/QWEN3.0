# LiMa Findings

> 历史归档：2026-06 及更早非审计条目 → [`docs/archive/findings-2026-06-CN.md`](docs/archive/findings-2026-06-CN.md)
> AUDIT 审计批次：2026-06-28/29 AUDIT-1~12 → [`docs/archive/findings-2026-06-audit-CN.md`](docs/archive/findings-2026-06-audit-CN.md)
>
> ⚠️ 新发现请按「五问法」记录：现象？复现？根因？修复？如何预防？

## 2026-07-06 设备网关 WS 下发链去留：已闭环（用户确认无存量设备 → 已退役）

- **2026-07-06 闭环结论**：用户明确确认「研发阶段，无线上存量设备依赖 `chat.donglicao.com` 的 `/device/v1/ws`」，阻塞点解除。自托管 WS/MQTT 任务下发死代码链已物理退役：删除 `mqtt_client/mqtt_handlers/mqtt_topics/health/notifier/attestation/protocol/protocol_frames/protocol_validators/protocol_negotiator`、`routes/device_gateway_dispatch.py`、`routes/device_gateway_helpers.py`，并将 `device_logic/gateway.py::dispatch_or_enqueue` 与 `device_gateway/tasks.py::create_and_route_task` 简化为纯 `enqueue_pending_task`（生产本就恒 queued，行为等价）。保留 `protocol_families.py` 与全部绘图核心。下方原始调查记录保留作历史证据。

- **问题**：`routes/device_gateway*.py`（约 1248 行）+ `device_logic/gateway.py` + `device_gateway/notifier.py`/`mqtt_handlers.py` 的任务下发链，在生产入口 `server_dlc.py` 下是否为死代码。这是仓库最大一块潜在瘦身目标。
- **已查清的代码事实（仓库内可确定）**：
  1. 服务端唯一任务下发链依赖 WS 端点 `/device/v1/ws`（`dispatch_task_to_session` → `session.send_json`；`drain_pending_tasks`；`publish_task_available_safe` 只是跨进程唤醒信号，非第二通道）。
  2. `server_dlc.py` / `dlc_api.app` 只注册 `dlc_router`，**未注册** `/device/v1/ws`；`server.py`/`routes/route_registry.py` 已删除 → 该端点生产不可达。
  3. 固件目标架构（设计文档 §1.2/§2.3）：语音走 xiaozhi.me 官方云 → MCP → `self.plotter.*`/`self.motor.run_path` HTTP 调 `dlc_api`，设备本地执行，**不从服务端拉任务**。
  4. **但**固件仍保留 WS/MQTT 的 `motion_task` 接收能力（`application.cc:588 HandleMotionTaskJson`），协议由 OTA config 动态选择（`InitializeProtocol`：`HasMqttConfig`→MqttProtocol，否则 WebsocketProtocol）；WS 音频通道默认 URL `wss://chat.donglicao.com/device/v1/ws`（`websocket_protocol.cc:94`）。
- **阻塞点（仓库代码无法回答的运行时事实）**：`routes/device_gateway*` 是否可删，取决于**线上存量设备的 OTA config 实际指向哪个服务器**：
  - 若全部设备已迁移 xiaozhi.me 官方云 → WS 网关是死代码，可删。
  - 若有设备 OTA config 仍指向 `chat.donglicao.com` 自托管 WS/MQTT 语音 → 删服务端会**断掉真实硬件的语音+任务下发**，不可逆。
- **删除代价**：`routes/device_gateway*` 被 230 个测试文件引用，深度嵌入，非孤立死代码。删除需连带处理 230 测试 + gateway/notifier/mqtt 整条链。
- **结论**：属高风险不可逆操作（影响真实设备语音链路），按 Ponytail 不可妥协边界 + 系统高风险操作规则，**必须先确认线上 OTA config 现状**再决定，不能靠读代码赌。
- **需要的输入**：线上设备 OTA config 的 `websocket.url`/`mqtt` 指向统计（xiaozhi.me vs chat.donglicao.com 的设备占比），或明确"自托管语音已全部退役、无存量设备依赖 chat.donglicao.com 的 /device/v1/ws"。

## 2026-07-06 系统瘦身残留审计：仓库与 VPS 分叉 + 死代码物理删除

- **现象**：STATUS.md 声称「P5 瘦身后约 280 py 文件 / ~18000 行」，实测 git 跟踪应用 py = **356 文件 / 41922 行**——数字差 76 文件 / 翻倍行数。仓库里有大量从 `server_dlc.py` 生产路径不可达的死代码。
- **根因（仓库与 VPS 分叉）**：
  - VPS 生产服务 `lima-router.service`（`infra/vps/systemd/lima-router.service`）ExecStart = `uvicorn server:app`，但 `server.py` 已在 P4/P5 删除。
  - `deploy_unified_restart.py:43` 仍 `systemctl restart lima-router`（旧服务名）。
  - `deploy_unified_common.py::CORE_FILES` 仍列 `server.py` + 旧路由模块（`routing_engine`、`router_v3`、`health_tracker` 等），`CORE_DIRS` 仍列已删目录（`context_pipeline`、`session_memory`、`code_context`、`device_voice`、`backends_registry`、`channel_retirement`）。
  - **推论**：VPS 上运行的是旧版完整代码（未被覆盖删除），仓库与生产已分叉。`deploy_unified.py` 若以旧清单执行会在 VPS 上找不到文件而失败。
- **修复（本轮已做）**：
  1. 物理删除三项零风险死代码（生产零引用，仅 .worktrees 旧副本引用）：
     - `integrations/cloud_services.py`（全仓库零 import）
     - `reference/grbl_fix/`（17 文件，一次性固件修复脚本，无 importer）
     - `device_support/`（2 文件，仅被审计脚本列举目录名）
  2. 清理三处脚本对 `device_support` 的字符串引用：`scripts/guardian_full_scan.py`、`scripts/coverage/analyzer.py`、`scripts/codegraph_orphans.py`
  3. `deploy_unified_common.py::CORE_FILES`/`CORE_DIRS` 对齐到 `server_dlc.py` 实际可达的模块清单（移除已删旧路由/旧目录，新增 `dlc_api`/`dlc_core`/`dlc_mcp`/`device_intelligence`/`device_logic` 等）
- **待办（需用户确认后操作）**：
  1. **VPS 部署同步**：确认 VPS 是否运行旧代码 → 部署新 `server_dlc.py` + 新 `dlc-drawing.service` → 切换服务名 `lima-router`→`dlc-drawing`。这是部署操作，不能仅改仓库。
  2. **设备网关 WSS 路由注册**：`server_dlc.py`/`dlc_api.app` 只注册了 `dlc_router`，**未注册 `routes/device_gateway.py` 的 `/ws` WebSocket 端点**。设备通过WSS取Redis队列任务的半条链没有对外端点。需确认是 WSS 路由漏注册（需补注册），还是设备通过别的方式取任务（HTTP轮询/MQTT），再决定是否物理删除 `routes/device_gateway*`。
  3. `sdk/`（5 文件，对外 Python SDK）是否保留——属交付物，非服务端死代码。
  4. ~~`observability/` 13 个非 prometheus 模块是否删除~~ **（2026-07-06 已删，见下）**。
  5. `routes/` 中 ~54 个未注册路由模块的去留取决于"WSS 是否需注册"。

- **续（本轮第二切片）物理删除 observability ops-metrics 死子系统**：
  - 证据：`server.py`/`server_lifespan.py`/`server_bootstrap.py` 全已删；`server_dlc.py` 无 lifespan，只挂 startup 日志。`observability/__init__.py` 为空，所有生产引用均为 `from observability import prometheus_metrics`；`prometheus_metrics.py` 只依赖 4 个 `prometheus_*` 子模块，零引用下列死模块。
  - 删除（13 模块）：`telemetry_aggregator`、`backend_telemetry`、`cli_telemetry`、`jsonl_store`、`alert_evaluator`、`routing_guard`、`gray_metrics`、`metrics`、`events`、`probe_state`、`stack_dump`、`structured_logging`、`prometheus_exporter`。
  - 删除 `routes/ops_metrics/`（整组，唯一外部引用是 `alert_evaluator.py` 函数体内惰性 import，已随之删除）。
  - 删除 6 个对应测试：`test_alert_evaluator`、`test_cli_telemetry`、`test_jsonl_store`、`test_observability_metrics`、`test_telemetry_aggregator`、`test_observability_trace_buffer` + `tests/ops_metrics_helpers.py`。
  - 保留：`prometheus_metrics`、`prometheus_device_task_metrics`、`prometheus_handwriting_metrics`、`prometheus_image_metrics`、`prometheus_startup_metrics`、`correlation`（生产可达）。
  - 残留死配置（本轮未动，避免扩大改动面）：`config/node_role.py::alert_evaluator_enabled/structured_logging_enabled`、`config/settings_core.py::structured_logging/routing_guard_*` 字段零消费方，留待后续统一清理。
- **预防**：P4/P5 物理删除后必须同步更新部署脚本的文件清单和服务入口，否则仓库与 VPS 分叉导致"声称瘦身的文件在生产还在跑"。

## 2026-07-06 §13 安全审计续：S3 限流 + S10 幂等去重（dlc_api）

- **S3（`/dlc/tasks/*` 无速率限制，🟠 中等）**
  - **现象**：`/dlc/tasks/preview` 与 `/dlc/tasks/dispatch` 无任何限流；`draw_from_image` 高 CPU/费用，可被单设备刷爆做 DoS。
  - **复现**：同一 Bearer token 高频调 `/dlc/tasks/preview`（type=draw_from_image），服务端无节流全部受理。
  - **根因**：dlc_api 是瘦身后新入口，未接入主 `server.py` 上的限流中间件；`dlc_api/app.py` 无任何全局中间件。
  - **修复**：复用现成 `routes/rate_limit_helper.check_key_limit`（内存滑动窗口，Redis 自动切换），按 `caller_device_id` 限流。配额加到 `config/settings_core.py::DeviceConfig`：`dlc_task_per_min`（默认 30）、`dlc_image_per_min`（默认 8，`draw_from_image` 专用低配额）。`_quota_for(task_type)` 按类型选配额。超限返回 429 `rate_limit_error`。
  - **预防**：新增公网端点必须显式接入 `check_key_limit`/`check_ip_limit`；重 CPU 操作单列低配额。测试用 autouse fixture `rate_limiter.reset()` 防止限流状态跨用例泄漏（否则同 device_id 多次调用会耗尽配额致 KeyError）。

- **S10（dispatch 无重放保护，🟠 中等）**
  - **现象**：静态 Bearer token 无 nonce/timestamp，重放同一 dispatch 请求可重复下发运动指令。
  - **复现**：同一请求体 POST 两次 `/dlc/tasks/dispatch`，设备执行两次。
  - **根因**：dispatch 端点未做幂等去重；`task_id` 由 `next_task_id()` 自增生成，非幂等键。
  - **修复**：dispatch 端点读 `Idempotency-Key` header，`_claim_idempotency_key` 用 Redis `SET NX EX`（TTL 600s，key 前缀 `lima:dlc:idem`）原子首次占用；重放返回 `status="duplicate"`。无 header 时保持旧行为（向后兼容）。
  - **降级决策**：Redis 不可用时 **fail-open**（放行 + `logger.warning`），理由：重复派发比丢失合法指令危害小，且 warning 显式暴露降级状态（遵守「禁止静默降级」硬规则）。
  - **预防**：固件/MCP 侧下发运动指令时应带 `Idempotency-Key`；幂等 key 由 `caller_device_id` + header 值组合，防跨设备碰撞。

## 2026-07-06 §13 安全审计闭环：SEC-06 队列投毒 + SEC-04 SSRF 加固 + v2_device_token 建表

- **SEC-06（Redis 任务队列投毒，🔴 严重）**
  - **现象**：`pop_pending_tasks` 把 Redis pending 队列里的任务 `decode_redis_json` 后直接经 `device_gateway_dispatch.py:154 session.send_json(pending_task)` 透传给固件，全程无 capability/字段校验。
  - **复现**：任何拥有 Redis 写权限者 `RPUSH lima:device:pending:<id> '{"capability":"delete_everything",...}'` → 固件收到并可能执行恶意运动指令。
  - **根因**：pop 路径信任 Redis 内容；enqueue 侧的 HTTP 校验（`routes/device_gateway.py::_validate_task_body`、`APP_TASK_CAPABILITIES`）被 Redis 直写绕过。
  - **修复**：`device_gateway/redis_store_helpers.py` 新增纯函数 `validate_task_schema` + `_ALLOWED_TASK_CAPABILITIES`（对齐 `APP_TASK_CAPABILITIES` 并含 `draw_from_image`）。`redis_store.pop_pending_tasks` 逐条 gate，拒绝的任务从 processing 队列 `lrem` 移除并 `logger.warning`，绝不下发。
  - **预防**：信任边界原则——任何来自 Redis/外部存储的任务在下发前必须过 allowlist；新增 capability 时同步更新此 allowlist 与 `APP_TASK_CAPABILITIES`。
- **SEC-04（draw_from_image SSRF，🔴 严重）**
  - **现象**：`dlc_api/routes.py::_validate_image_url` 只拒绝字面量私网 IP，接受任意 HTTPS 主机；公网域名解析到私网 IP（DNS rebinding）可绕过。
  - **根因**：无主机白名单 + 无 DNS 解析后二次校验。
  - **修复**：三层顺序——(1) 字面量私网 IP 拒绝；(2) 主机白名单 `ALLOWED_IMAGE_HOSTS={"api.telegram.org"}`（图库唯一来源）；(3) 新增 `_resolve_hostname`（可测试注入点）解析后若命中私网 IP 则拒绝。
  - **预防**：服务端下载类接口默认走「白名单 + 解析后私网拒绝」双闸；新增可信图源时只扩白名单，不放开任意主机。
  - **契约变更**：旧 `test_dlc_api.py` 用 `example.com` 断言 success 的 3 个用例是不安全行为的固化，已改用 `api.telegram.org` + 注入 `_resolve_hostname` 返回公网 IP；重复的 SSRF 用例合并进 `test_sec04_ssrf_hardening.py`。
- **S1/S7（v2_device_token 表缺失）**
  - **现象**：`dlc_api/deps.py` 设计为 DB 优先鉴权，但 `v2_device_token` 表从未接入迁移，生产环境 `_lookup_token_from_db` 恒返回 None → 实际只走 `LIMA_DEVICE_TOKENS` env fallback。
  - **修复**：`device_logic/db_migrations.py::_DDL_STATEMENTS` 末尾追加 `v2_device_token` 建表 + `idx_v2_device_token_hash` 唯一索引，随其他 v2_* 表幂等 bootstrap。
  - **预防**：设计文档中的 DDL 必须同步落到 `_DDL_STATEMENTS`，否则消费方代码的 DB 分支形同虚设。
- **门禁**：全量 `pytest` **1565 passed / 3 skipped / 0 failed**；`ruff check` + `ruff format --check` clean；`check_code_size` PASS。新增聚焦测试：`test_sec06_redis_schema_gate.py`（8）、`test_sec04_ssrf_hardening.py`（6）、`test_v2_device_token_migration.py`（4）。
- **教训**：写 SEC-06 测试时最初用了缺 `capability` 的简化 task fixture，导致 gate 上线后误伤既有 `test_device_gateway_redis_store.py`。核对生产 `_assemble_motion_task` 确认真实任务必带 `capability`（控制能力或 fallback `run_path`）后，修正的是测试 fixture 而非削弱 gate——安全 gate 正确时，应让不真实的旧测试向生产结构对齐。

## 2026-07-05 DLC VPS 部署：认证格式不兼容 + 公网路由未通

- **现象**：DLC 服务部署到 Aliyun VPS 后，`/dlc/tasks/validate` 带认证仍返回 401 "Not authenticated"；公网 `https://chat.donglicao.com/dlc/*` 返回 405。
- **根因 1（认证）**：VPS `.env` 中 `LIMA_DEVICE_TOKENS=dev-test-1=fRAI52A3...` 使用 `device_id=token` 格式（device-gateway 兼容），但 DLC 代码 `_load_device_tokens()` 只解析 `token:device_id` 格式（`:` 分隔）。`=` 格式的条目被跳过，导致 env 回退为空。
- **修复**：更新 `_load_device_tokens()` 同时支持 `:` 和 `=` 分隔符。新增 2 个测试覆盖。重新部署后认证通过。
- **根因 2（公网 405）**：`chat.donglicao.com` DNS 解析到 Cloudflare（198.18.2.214），通过 Cloudflare Tunnel 路由到 JDCloud（117.72.118.95）。DLC 服务部署在 Aliyun（47.112.162.80:8081），JDCloud 上无 DLC 服务和 nginx `/dlc/` 路由。nginx 在 JDCloud 上找不到匹配的 location，返回 405。
- **修复状态**：未修复。JDCloud SSH 认证失败（`deploy_config.jdcloud_password()` 未配置或已过期）。需用户提供 JDCloud 凭据或配置 Cloudflare 路由。
- **预防**：部署前检查 VPS `.env` 中变量格式与代码解析逻辑的一致性；多 VPS 架构部署时确认 DNS/CDN 路由路径。

## 2026-07-04 M4 全项目重构：P3 技术债发现与修复

- **小程序**：
  - 超时魔法数字散落 8 处（alova 15000、chat 120000、login 30000、health 3000、BLE 10000、SoftAP 3000/15000），数值靠上下文推断、调优需逐一 grep。抽 `src/config/timeouts.ts`（8 个 `*_TIMEOUT_MS` / `*_COOLDOWN_MS` 常量）后单点引用，`rg "timeout: [0-9]"` 归零。
  - 非微信端流式自 P0.4 起为 fail-loud 占位（`throw new Error('...only on mp-weixin...')`）。完整实现：`fetch` + `response.body.getReader()` 读取 SSE，`AbortController` 支持 abort，与微信端共用 `parseSSEBuffer` 避免分叉。H5/App 现在可真实流式对话。
  - 三个超大组件（761/691/667 行）脚本逻辑密集，拆分后模板/样式逐字节不变（`git show HEAD:./path | sed -n '/<template>/,$p'` 与工作区 diff 为空验证）。`device-detail` 拆 `useDeviceEvents`（WS 事件+进度+自检）+ `useDeviceActions`（任务派发+耗材+转移+分享+解绑），通过 setter 共享 `latestPhase`/`infoLoading` 避免状态二份。`voiceprint` 拆 CRUD + 音频试听两个 composable。`ultrasonic-config` 把 AFSK DSP 抽成纯函数 `afskAudio.ts`（可单测）+ `useUltrasonicAudio`（播放生命周期）。
  - `chat/chat.vue`(635) 与 `index/index.vue`(604) 超标但脚本已精简（244/130 行），臃肿来自模板+样式。**2026-07-04 已清理（D1/D2）**：脚本抽 composable（chat → `useChatMessages`/`useChatStream`/`useChatHelpers`；index → `useHomeData`/`useHomeNavigation`/`useTaskFormatters`），样式抽独立 `.scss`（`<style src="./x.scss">`）。模板与样式内容逐字节不变（`git show HEAD:./path` 切片与工作区 diff 为空验证），只改 `<script>` 与 `<style src>`。两文件降到 130/238 行，全部 <300。**2026-07-04 已清理（D1/D2）**：脚本进一步抽 composable + 独立 `.scss`（635→130、604→238），模板/样式 byte-identical（`git show HEAD:<path>` 截取 `<template>`/`<style>` 区段与工作区 diff 为空），无需视觉验证即可保证零回归。
- **Chat Web**：
  - `escapeHtml` 在 7 个文件有本地拷贝，实现不一致（playground-utils 转义 backtick、devices/keys/usage 不转义、chat-messages 转义 `'`）—— XSS 面不一致。收敛到 `js/utils.js`（`window.LiMaUtils`，覆盖 `& < > " ' \``）后 8 个 HTML 页面加载顺序调整，所有消费点 alias 到 `LiMaUtils`。
  - 引入 esbuild 0.25.12（避开 0.24.x dev-server 漏洞 GHSA-67mh-4wv8-2f99）做 minify pass：`hash-assets.mjs` 在复制后、哈希前对每个 JS/CSS `transform({minify:true})`，styles.css 68KB→49KB。`chat-web/package.json` + `node_modules`/`package-lock.json` 加入 `.gitignore`。
  - `styles.css` 2060 行按页面拆分作为债务延后——esbuild minify 已解决 payload 体积，盲拆共享 CSS 风险高于收益。**2026-07-04 已清理（D3）**：按注释区块边界切成 `css/common.css`（全局 reset/变量/滚动条/焦点/微交互）+ `css/chat.css` + `css/playground.css` + `css/auth.css` + `css/pages.css`，各 HTML 页面按需组合加载（common 恒先加载）。`hash-assets.mjs` 适配 `css/*.css` minify+哈希，`deploy_chat_web.py` FILES 用 `css/*.css` 取代 `styles.css`。**CDN 教训复现**：部署后新 `css/*` 路径被 Cloudflare 负缓存命中 404，且旧 HTML 仍引用 `styles.css`；因 deploy 只上传 FILES、从不删除远端旧文件，origin 上 `styles.css`(68KB) 仍在——缓存 HTML 用户走旧兜底、新用户走拆分 CSS，CF ~4h 缓存窗口内两态都不破。验证：origin HTTPS（`--resolve` 绕 CDN）5 个 CSS 全 200，旧 `styles.css` 仍 200。**2026-07-04 已清理（D3）**：拆为 `css/{common,chat,playground,auth,pages}.css` 五份，各 HTML 只加载 common + 相关分片（首屏无关规则不再下载）。`hash-assets.mjs` 扩展为对 `css/` 子目录做 minify+hash+HTML 重写。**部署踩坑**：`deploy_chat_web.py` 只 SFTP 上传 FILES 清单、从不删除 origin 旧文件，因此旧 `styles.css`（68KB）仍留在 origin 兜底 CDN 缓存的旧 HTML；Cloudflare 对新 `css/*` 路径先返回负缓存 404，约 4h 后转 HIT 200。新旧两态在过渡窗口都能正常渲染，无需 CF purge 权限。
- **固件**：
  - `ota.cc` 的 `IsAllowedOtaHost`/`IsAllowedEndpointUrl`/`IsLowerHexSha256`/`IsLikelyBase64` 是安全关键纯函数（P0.9 端点白名单），但无单测。新增 `test_u8_ota_allowlist.cpp`（25 用例，含 evil-suffix 绕过 `chat.donglicao.com.evil.com` 必须被拒）。`mqtt_protocol.cc` 的 `DecodeHexString`/`CharToHex` 新增 `test_u8_mqtt_hex_decode.cpp`（10 用例）。两者接入 CI `firmware-native-tests` job。
- **教训**：
  - composable 提取时，跨 composable 共享的状态（如 `latestPhase`、`infoLoading`）必须由「拥有」方暴露 setter，消费方通过 setter 写入，不能各存一份 ref——否则事件流更新的是 events 的 ref，actions 读的是自己的 ref，UI 不刷新。
  - 经典脚本（IIFE + script-tag）去重时，`const` 在全局作用域会与后续脚本的 `function` 同名声明冲突；去重后必须删除所有重复声明，只留一处 alias。
  - 纯 DSP 逻辑（AFSK 调制/WAV 编码）抽成 framework-free 模块后可独立单测，比留在 Vue 组件里更安全——`afskAudio.ts` 的输出是确定性的 base64，可直接断言。
  - 固件 native 单测采用「纯逻辑重实现」模式（不 include ESP-IDF 头），代价是双份代码；若 ota.cc 逻辑变更需同步更新测试拷贝。权衡：可原生编译 vs 维护双份。

- **后端**：
  - `http_caller.py` 为 thin re-export 门面，若下游子模块（`http_sync`/`http_async`/`http_stream` 等）改名或删符号，历史 `from http_caller import X` 会在运行时才 `ImportError`。新增 `tests/test_http_caller_reexports.py` 参数化断言全部公开符号仍可导入，把回归提前到测试期。
  - `probe_loop.py`（对 dead/suspicious 主动探活）与 `backend_probe_loop.py`（全量批次周期探活）职责相近、命名相似，易混淆。已在两者 docstring 顶部加交叉引用说明各自触发条件与区别。
  - `requirements_dev.txt` 强制 `httpx2~=2.5` 只为消 starlette testclient 弃用警告，却引入第二套 httpx 实现、增大依赖面。评估后移除；testclient 在 httpx 0.28 下功能正常，仅保留一条弃用 warning（无害）。
  - `.env.example` 的 `LIMA_ADMIN_TOKEN`/`LIMA_API_KEY` 占位符形似真实密钥，去敏化为 `<set-your-*>` 格式，降低误提交/误用面。
- **Chat Web**：
  - `chat-web/_headers`（含 HSTS/nosniff/缓存策略）已存在，但 `deploy_chat_web.py` 的 `FILES` 未包含它，导致部署后 nginx 不下发这些头。已把 `_headers` 加入上传列表。
- **小程序**：
  - `manifest.config.ts` 与 `pages.config.ts` 各自复制了一份 `getMode()`（解析 `--mode` 命令行参数），重复逻辑。抽到 `scripts/get-mode.ts` 单点导出，两处引用。
  - `unpackage/res/icons/*.png`（17 个 App 打包图标，仅 5+App 端用）被 git 跟踪，污染仓库；`git rm` 后 `.gitignore` 增加 `unpackage/` 忽略。
  - `src/static/app/icons/1024x1024.png`（458KB）用 Pillow `optimize=True` 压缩到 433KB（RGBA PNG 无损压缩上限有限；进一步需转格式或降分辨率，暂不激进处理）。
  - `src/i18n/{zh_CN,en}.ts` 各 800+ 行手工维护，key 容易漂移。新增 `scripts/check-i18n-keys.mjs` 校验中英 key 集合一致（当前 803 keys 对齐），挂到 `package.json` 脚本。
  - `tabbarList.ts` 遗留 TODO 与 `utils/index.ts` 大量注释掉的 `console.log` 调试残留，已清理。
  - 依赖冗余：未使用的 `@tanstack/vue-query`（`main.ts` 已移除 `VueQueryPlugin`）及 8 个非目标平台 `@dcloudio/uni-mp-*`（alipay/baidu/jd/kuaishou/lark/qq/toutiao/xhs）已移除；macOS 专用 `@esbuild/darwin-*` / `@rollup/rollup-darwin-x64` 也移除，减少安装体积与锁冲突。
  - **miniprogram-ci 上传失败（`TypeError: _lruCache is not a constructor`）**：现象——清理依赖并 `pnpm install` 后，`upload:mp-weixin` 在编译阶段抛此错。复现——`node -e "require('@babel/helper-compilation-targets')"`。根因——依赖清理触发 pnpm 重解析，`@babel/helper-compilation-targets`（要求 `lru-cache@^5` 的具名默认导出）被提升到 `lru-cache@11`（v11 无默认导出、构造签名变更）。修复——在 `pnpm-workspace.yaml` 加 `overrides: '@babel/helper-compilation-targets>lru-cache': ^5.1.1`（注意 pnpm 10 已不再读 `package.json` 的 `pnpm.overrides` 字段），`pnpm install` 后锁定 `lru-cache@5.1.1`。预防——依赖清理后必须重跑一次 `build`+`upload` 冒烟；传递依赖版本漂移用 workspace `overrides` 钉死，不要依赖提升顺序。
- **固件**：
  - U1 `platformio.ini` 引用 `board_build.partitions = min_spiffs.csv`，但该文件依赖 Arduino-ESP32 框架内置路径，在跨机器/CI 环境可能解析失败。已将标准 `min_spiffs.csv` 入库到 `firmware/u1-grbl/extra/min_spiffs.csv` 并改本地引用。
  - U8 默认日志级别在 `sdkconfig.defaults` 未显式设置，默认可能是 VERBOSE/DEBUG，生产串口日志冗余。新增 `CONFIG_LOG_DEFAULT_LEVEL_INFO=y` 统一裁剪。
- **文档**：
  - `docs/getting-started.md` 前置条件表仍写「Java JDK | 21 | manager-api 编译」，CI 章节仍列「Java 测试 — manager-api 76+ 测试」。实际上 manager-api 已迁移至 LiMa 主项目，已清理避免误导新成员。
- **教训**：
  - re-export 门面模块必须配「符号完整性测试」，否则重构子模块时门面会静默腐化，只有生产导入才暴露。
  - 静态资源头文件（`_headers`）与部署脚本 `FILES` 列表是两处易脱节的配置，任何新增静态策略文件都要同步进部署清单。
  - i18n 多语言文件适合用「key 一致性」脚本做 CI 门禁，比人工 review 可靠。
  - 固件构建工具链（PlatformIO/ESP-IDF）与 Python 版本强绑定，本地环境损坏时无法即时验证，应在 CI 中固化编译矩阵。

## 2026-07-03 M1 全项目审计：P0 安全/正确性发现与修复

- **CRITICAL 级（小程序/固件侧）**：
  - 上传私钥 `private.wxbf3c1e0013b46343.key` 存在于工作区，但 `git log --all` 确认**未进入 git 历史**。风险：本地泄露；已加 README 保管提示。
  - 生产 `NODE_ENV = 'development'` 导致 vite 压缩/tree-shake 失效；已修正为 `production`。
  - `vite.config.ts` 裸 `console.log` 打印全量 env；已移除。
- **HIGH 级**：
  - 后端静默降级：`xiaozhi_drawing/pipeline.py` 存在 `except ImportError: pass`（AGENTS.md 硬规则精确禁止模式）；已改为 `logger.warning`。
  - CI 门禁盲区：`tests/test_ci_gates.py` 仅扫 `device_gateway/` + `routes/` + 根路由文件，遗漏 `xiaozhi_drawing/`、`context_pipeline/`、`session_memory/` 等；已改为排除式扫描，并补 `.worktrees` 到 skip 集合。
  - 小程序非微信端流式静默失败：无轮询实现却假装支持；已改为 fail-loud。
  - Chat Web 图片生成 XSS 面：只校验协议未校验域名；已加白名单。
  - U1 OTA 无签名/弱认证：默认禁用 WebUI OTA 入口（403）。
  - U8 端点无签名下发：OTA 服务器可推送任意 mqtt/websocket 端点；已加白名单。
  - 固件文档滞后：服务端组件已删除但 Dockerfile/README 仍指向；已清理。
- **M1 遗留项**：
  - `deploy_chat_web.py` 因远程 `/var/www/chat` 目录不存在而失败。根因：脚本未在部署前 `mkdir -p`。建议：要么运维手动创建，要么在 P2 阶段把 `mkdir -p {REMOTE_DIR}` 加进 `deploy_chat_web.py` 并重新部署。
  - `.worktrees/` 中 `feat-device-task-metrics` 与 `feat-handwriting-resilience` 分支仍含静默降级，但当前未进入主分支；这些 worktree 未来合并前需清理。
- **教训**：
  - 排除式 CI 扫描比包含式更健壮；但需把 `.worktrees` 明确加入 skip 集合，避免把特性分支未完成债务误判为 main 回归。
  - 前端构建日志是 secret 泄露面；`vite.config.ts` 的 `console.log` 会被 CI 完整记录，且不受 `esbuild.drop` 约束。
  - 固件服务端迁移后，必须同步删除 Dockerfile 并更新历史 README，否则新成员会按错误文档操作。

## 2026-07-03 M2 全项目审计：P1 质量/文档/测试发现与修复

- **后端质量**：
  - `session_memory` 迁移重试、`observability/jsonl_store` 日志轮转、`context_pipeline/chroma_vector_store` 降级等路径原先只 `logger.debug` 或无日志，AGENTS.md 硬规则要求「禁止静默降级」至少 `logger.warning`；已统一改为 warning 并说明 fallback 原因。
- **Chat Web**：
  - 域名配置分散在 `index.html` 与 `js/app-boot.js` 两处，运维切换 Chat Web 入口时需改两处，易遗漏；已收敛到 `window.LiMaConfig` 单点配置。
  - 部署脚本 `deploy_chat_web.py` 未处理远程目标目录缺失，新 VPS 首次部署即失败；已加 `mkdir -p` 支持多级目录（`js/` 子目录）。
- **小程序（uni-app）**：
  - 类型债务：`utils/index.ts` 大量 `any`、无 `SubPackage` 类型、`deepClone` 类型不精确；已收敛类型。
  - 死代码：`store/config.ts` 无引用、`store/user.ts` 重复清除 `userInfo`、`utils/platform.ts` 依赖未定义宏；已删除/清理。
  - API 层不统一：`chatCompletion` 仍使用原生 `uni.request`，与项目整体 alova 封装不一致；已迁移到 `http.Post`。
  - 安全开关：`manifest.config.ts` 与 `src/manifest.json` 的 `urlCheck` 在真机/生产环境为 `false`，可能放行未校验 URL；已改为 `true`。
  - 测试覆盖：manager-mobile 无单元测试；已引入 `vitest` 3.2.6 + `jsdom` 并覆盖 `deepClone` 纯函数。
- **固件**：
  - U8 `main/CMakeLists.txt` 包含 ml307/nt26/dual_network/rndis/esp_video 等非目标板源码，增加构建面与误触发风险；已移除。
  - U1 `platformio.ini` 的 `[env]` 默认 `board = esp32` 与下方 `release_esp32s3` 覆盖关系未注释，新成员易误读默认配置；已补充说明。
  - 边缘协议 schema 文件无版本号，向后兼容难追踪；已统一加 `schema_version: "1.0.0"`。
  - `docs/schemas/edge_*` README 仍指向旧固件服务端，未说明已迁移至 LiMa `device_gateway`；已加迁移横幅。
- **教训**：
  - 小程序 manifest 双文件（`manifest.config.ts` + `src/manifest.json`）需同步维护，否则版本 bump 或安全开关会丢失。
  - 子模块内嵌套目录若含独立 git 仓库，提交前要确认当前 working tree 属于哪个仓库，避免把指针提交错仓库。
  - 前端引入测试框架时需注意与现有 vite 大版本兼容（vitest 4.x 与 vite 5 冲突），应锁定小版本。


## 2026-07-03 U 批：routes/device_gateway_ws_handlers.py hello 握手机制抽到 device_gateway_hello_helpers.py

- **稳定单例顶层导入安全，但「属性替换」patch 仍须迁移目标模块**：`attestation_verifier` 经 ripgrep 确认无 `set_*_for_tests`/`install_*_for_tests` 接口——是稳定单例（S 批稳定 vs 可替换单例判定法），新模块顶层 `from device_gateway.attestation import verifier as attestation_verifier` 安全。但 8 处测试用 `monkeypatch.setattr(handlers, "attestation_verifier", isolated_verifier)` / `patch.object(handlers, "attestation_verifier", ...)` **替换模块属性为隔离 verifier**——`_check_attestation` 抽到 `hello_helpers` 后从 `hello_helpers` 查 `attestation_verifier`，patch 若仍指 `handlers` 则替换了旧模块的属性、新模块读到的还是全局 verifier，测试隔离失效。教训：**稳定单例的「顶层导入」只解决 R 批 from-import 绑定陷阱（swap 接口）；「属性替换式 patch」（monkeypatch.setattr 模块属性）仍须随符号迁移重指目标模块**。两类风险独立，判定法互补：ripgrep `set_*_for_tests` 判 swap 接口（决定导入方式），ripgrep `monkeypatch.setattr\|patch.object` 判属性替换（决定 patch 目标迁移）。
- **公共入口留守 + 私有 helper 抽离的零调用方改动模式**：`handle_hello` 作为公共入口留在 ws_handlers，5 个私有 `_` helper 搬到 `hello_helpers`。`test_routes_device_gateway_ws.py` 的 `patch.object(dgws, "handle_hello", ...)` 绑定 WS 路由模块 `device_gateway_ws`（从 `hello_handlers` 导入 `handle_hello` 的下游），patch 的是路由模块的绑定名而非 handlers 模块——抽离 helper 不动 `handle_hello` 自身的定义位置，此类 patch 不受影响。对比 R/S 批整端点搬迁需修局部 app `include_router` + 路由模块 patch 目标，**「公共入口留守 + helper 抽离」是路由/状态模块的低风险拆分姿势**：调用方（含 patch 调用方的测试）零改动，仅需迁移 patch helper 内部依赖的测试。

## 2026-07-03 T 批：device_gateway intent.py LLM planner 子域抽到 intent_llm_planner.py

- **re-export 保持 backward compatibility**：LLM planner 子域搬走后，`DANGEROUS_CAPABILITIES`（生产 `prompt_engineering/layers.py` 导入）和 `_llm_replan`（测试 `dgi._llm_replan(...)` 调用）必须仍可从 `device_gateway.intent` 访问。用 `from device_gateway.intent_llm_planner import DANGEROUS_CAPABILITIES, _llm_replan  # noqa: F401  re-export` 保持——`is` 同一对象身份（非拷贝），特征化测试用 `assert dgi.DANGEROUS_CAPABILITIES is planner.DANGEROUS_CAPABILITIES` 锁定。教训：**抽离被外部依赖的符号时，re-export + noqa: F401 + 特征化测试三件套保证 backward compatibility 不破**。F401 全局门禁会拦未标注的 re-export，`# noqa: F401  re-export` 注释是必需的。
- **纯函数子域抽离 vs 路由/状态类抽离风险对比**：T 批（intent.py 纯函数）零 router/monkeypatch 风险——4 测试文件只 patch 全局 `http_caller.call_api`（抽离后仍生效，因 `_llm_replan` 内部仍 `import http_caller` 调 `call_api`）。对比 R/S 批路由抽离需修局部 app `include_router` + `patch.object` 目标迁移，纯函数抽离只需 re-export + 改导入源。教训：**优先选纯函数子域抽离（零 router 风险），路由/状态类抽离留到纯函数空间耗尽后**。

## 2026-07-03 S 批：routes/device_gateway.py events 端点抽离到 device_gateway_events_routes.py

- **稳定单例 vs 可替换单例的导入策略**：R 批 lesson 是"`set_*_for_tests` 可替换单例必须延迟导入"。S 批验证了反面：`shadow_store` 和 `process_motion_event_core` 是稳定模块级单例（ripgrep 确认无 `set_*_for_tests` / `install_*_for_tests` / `monkeypatch` swap），顶层导入安全。模块 docstring 显式记录此区别，避免未来误把稳定单例也改延迟导入（增加无谓复杂度）或误把可替换单例用顶层导入（重蹈 R 批回归）。判断法：ripgrep `set_<name>_for_tests\|install_<name>_for_tests\|monkeypatch.*<name>` 全库无命中 → 稳定单例可顶层导入；有命中 → 必须延迟导入。
- **patch.object 目标随模块迁移**：`test_routes_device_gateway.py` 的 5 个 events 测试用 `patch.object(dg, "validate_uplink", ...)` patch `routes.device_gateway` 模块属性。events 端点移到 `device_gateway_events_routes` 后，`validate_uplink`/`process_motion_event_core`/`shadow_store`/`ProtocolError` 不在 `dg` 上——`AttributeError: <module 'routes.device_gateway'> does not have the attribute 'validate_uplink'`。修正：patch 目标改指 `events_routes` 模块（`from routes import device_gateway_events_routes as events_routes` + `patch.object(events_routes, "validate_uplink", ...)`）。教训：**路由端点迁移到新模块时，所有 `patch.object(旧模块, "依赖名", ...)` 必须同步改指新模块**，否则 AttributeError。

## 2026-07-03 R 批：routes/device_gateway.py 查询端点抽离到 device_gateway_query_routes.py

- **Python 模块级 `from import` 绑定陷阱**：新模块 `device_gateway_query_routes` 初版用顶层 `from device_gateway.store import task_store` 绑定模块级单例。但 `install_task_store_for_tests()` / `set_task_store_for_tests()` 用 `global task_store` 替换 `device_gateway.store` 模块的 `task_store` 属性指向**新对象**——已顶层 `from import` 的模块仍持有**旧对象引用**，导致测试 `test_sessions.py::test_registry_remove_zombies_requeues_outstanding_tasks` 调 `install_task_store_for_tests()` 后，后续 `test_task_list_returns_tasks` 的 `create_task_from_transcript` 写入新实例、`device_gateway_query_routes` 读旧实例，`count=0` 回归。修正：4 个运行时单例（`task_store`/`task_snapshot`/`artifact_store`/`artifacts_for_device`）改回**函数内延迟导入**，每次调用重新解析模块属性拿当前实例——与原 `routes/device_gateway.py` 行为一致。教训：**涉及 `set_*_for_tests` 可替换单例的导入，必须用延迟导入（函数内 `from ... import ...`），不能用顶层 `from import`**，否则测试隔离回归。
- **局部 app 测试需同步 include 新 router**：5 个测试文件用 `app = FastAPI(); app.include_router(dg.router)` 构造局部客户端（不走 `server.app` 完整注册），抽离新 router 后这些测试需手动加 `app.include_router(query_router)`。用 `server.app` 的测试（`test_registration.py`、`test_json_body_contract.py`）自动获得新路由无需改。POST-only 测试无需改。教训：**FastAPI 路由抽离时，必须审计所有局部 `app.include_router()` 测试客户端**，不只是 `server.app` 集成测试。
- **`APIRoute.path` 含 prefix 拼接**：特征化测试断言新模块 router 路径时，`APIRoute.path` 返回完整路径（含 `prefix="/device/v1"` 拼接），不是相对路径 `/tasks/{task_id}` 而是 `/device/v1/tasks/{task_id}`。断言须用完整路径。

## 2026-07-03 Q 批：device_gateway profiles.py 约束施加抽离到 profile_constraints.py

- **粗粒度尺寸目标耗尽后的发现手段**：P 批闭环后 `check_code_size.py` 全过（0 个 >300 行文件、0 个 >50 行函数），需换更细发现手段。CodeGraph 孤儿审计（`codegraph_orphans.py --fanin`）标 `context_compressor.py` 为 ORPHAN，但 `find` + `grep` 全库核实磁盘已不存在——是 CodeGraph 数据库陈旧，非真死代码目标。教训：**CodeGraph 孤儿标记必须 ripgrep 二次核实**（与 G1b F401 审计 agent 不可信同一原则），图数据库可能滞后于磁盘。最终用"行数逼近上限扫描"定位 `profiles.py` 295 行（距 300 仅 5 行）为最值得抽离目标。
- **TYPE_CHECKING 规避循环引用**：`profile_constraints` 需引用 `profiles.ResolvedProfile` 做类型注解，但 `profiles` → `device_profile` 链若 `profile_constraints` 运行时导入 `profiles` 会形成 `profile_constraints → profiles → device_profile` 与 `task_creation → profile_constraints → profiles` 的潜在环。解法：`ResolvedProfile` 仅在 `if TYPE_CHECKING:` 块下导入，运行时不导入、pyright 仍解析类型。pyright 0 errors 实证规避成功——此模式适用于"纯函数模块需引用上游 dataclass 类型但不需运行时调用"的抽离场景。
- **F401 全局门禁副带收益**：抽离 3 函数后 `profiles.py` 的 `import json` 和 `from device_gateway.device_write_handler import record_simplification` 随之变死（K2+L+M+N 批启用的 F401 全局门禁会拦），第一时间清理——证明 F401 门禁在重构时主动暴露死导入，而非等到 CI 报错。

## 2026-07-03 P 批：本地 pre-commit 加 ruff format --check 守护 + 副 `_run` cwd 透传真 bug 修复

- **根因**：O-3 调试历程暴露本地 pre-commit 入口 `scripts/run_ruff_check.py` 只跑 `ruff check`，CI 跑 `ruff check` + `ruff format --check` 两步——两端命令集合不对称，切片 spacing 漂移、Optional[X]→X|None 整理、EOL newline 等只破 format 不破 check 的差异在本地静默放行、到 CI 才暴露，每次都要补 fix commit + push retry。
- **修复**：`run_ruff_check.py::run_ruff` 改为聚合 `ruff check` + `ruff format --check` 两次 subprocess，第一非零 returncode 即阻塞，stdout/stderr 透传组合；docstring 解释来历 + lesson learned O-3 链接。
- **首次启用即实证价值**：本地空 staging 跑 pre-commit 立即抓出 2 处早已该 format 的长行漂移（`deploy/jdcloud/deploy_jd.py` 长 URL、`tests/device_gateway/test_ws_lifecycle.py` 长函数签名），P 批顺手 format 清掉。
- **副带 P-1 → 抓出 `_run` cwd 透传真 bug (P-2)**：P-1 push commit `c16a4f9d` 触发 CI `Type check changed Python files` 步骤，因 `deploy_jd.py` 被 diff 命中触发 pyright，发现 line 34 `_run("sha256sum -c prometheus.sha256", cwd=INSTALL_DIR)` 传 `cwd=` 但 `_run` 函数签名只有 `check`、`cwd` 被静默忽略——`sha256sum -c` 实际在错误工作目录跑。这是**潜伏已久的真 bug**，校验在错误目录跑可能误判通过。给 `_run` 加 `cwd: Path | None = None` 参数透传 `subprocess.run(..., cwd=cwd)`，pyright 0 errors。
- **教训 (CI 「Type check changed Python files」 是隐式宽覆盖扫描)**：本地只在 `--full` pre-commit 或 user-changed 时跑 pyright 在指定文件，CI 的 `Type check changed Python files` 是 `git diff --name-only HEAD~1..HEAD --diff-filter=ACMRT` 每次自动扫**所有动过的 .py** —— 单一文件可能即使不是改动核心，只要被 diff 命中就 pyright。这是隐藏的"宽覆盖 pyright 扫描"。今后涉及工具脚本（不在权威文件清单）改动应本地手动跑 `pyright <改动文件>` 与 CI 同步，否则 pyright 失败往往伪装成「CI 又红了」回环 retry 浪费。
- **教训 (CI/本地守护对称原则)**：CI workflow 与本地守护脚本必须跑 **同一套** 命令集合（ruff check + ruff format --check），否则本地绿 CI 红会反复发生。重构 grep 双方文件 `.github/workflows/test.yml` 与 `scripts/run_ruff_check.py` 比对 ruff 命令是审守护对称的最简方法。

## 2026-07-03 P 批：本地 pre-commit 加 ruff format --check 守护（CI 与本地守护对称）

- **根因**：O-3 调试历程暴露本地 pre-commit 入口 `scripts/run_ruff_check.py` 只跑 `ruff check`，CI 跑 `ruff check` + `ruff format --check` 两步——两端命令集合不对称，切片 spacing 漂移、Optional[X]→X|None 整理、EOL newline 等只破 format 不破 check 的差异在本地静默放行、到 CI 才暴露，每次都要补 fix commit + push retry。
- **修复**：`run_ruff_check.py::run_ruff` 改为聚合 `ruff check` + `ruff format --check` 两次 subprocess，第一非零 returncode 即阻塞，stdout/stderr 透传组合；docstring 解释来历 + lesson learned O-3 链接。
- **首次启用即实证价值**：本地空 staging 跑 pre-commit 立即抓出 2 处早已该 format 的长行漂移（`deploy/jdcloud/deploy_jd.py` 长 URL、`tests/device_gateway/test_ws_lifecycle.py` 长函数签名），P 批顺手 format 清掉。
- **教训 (CI/本地守护对称原则)**：CI workflow 与本地守护脚本必须跑 **同一套** 命令集合，否则「本地绿 CI 红」将反复发生，每次测试 CI 来确认 commit 行为是慢反馈。重构 grep 双方文件 `.github/workflows/test.yml` 与 `scripts/run_ruff_check.py` 比对 ruff 命令是审守护对称的最简方法。今后若 CI 加新 lint rule（如 Ruff 更新带新 rule），同步加进本地守护。

## 2026-07-03 O 批 CI 修复：pyright authority-files 步骤指向已迁移的 routing_engine 包

- **根因**：K2+L+M+N 推 push 后 GitHub Actions Tests workflow 失败。逐步定位到 `Type check authority files` 步骤 `pyright server.py routing_engine.py routes/chat_endpoints.py` 报 `File or directory "routing_engine.py" does not exist`（exit 4）。`routing_engine.py` 早已在历次抽离中拆成 `routing_engine/` 包（`__init__.py` 为权威 `route()` 入口 + `route_pipeline.py`/`execute_strategy.py`/`intent.py`/`post.py` 等子模块），但 CI 的 authority-files pyright 步骤硬编码了旧单文件路径。
- **关键澄清**：CI 的 pytest / F401 安全门 / testside_f401_safety_gate 全部通过（`4395 passed, 17 skipped`；`pytest --collect-only OK`）—— 即 K2+L+M+N 的 F401 全局门禁与 N 批 pypinyin pin 在 CI 上真实生效（H1/I/J 集测在 CI 上因新装 pypinyin 不再被 importorskip 跳过，skipped 数下降）。失败**仅**在 pyright authority 步骤的过时路径，与瘦身改动无关。
- **修复**：`.github/workflows/test.yml` authority 步骤 `routing_engine.py` → `routing_engine/__init__.py`；顺带更正 3 处其它过时引用 —— `scripts/repo_stats.py` KEY_FILES、`scripts/deploy_unified_common.py` CORE_FILES + phase_a SLICE_FILES。core slice 部署用 `_collect_runtime_files()` 动态收集不受影响（888 files 一直成功），过时引用仅影响 repo stats 显示与极少用的 phase_a slice，非阻塞但一并更正保工具准确。
- **教训**：模块从单文件拆成包时，必须全仓 grep `<旧模块>.py` 字面量引用（CI workflow、部署清单、stats 脚本、文档），而非只改 import。`--diff-filter=ACMRT` 已使 changed-files pyright 步骤天然排除删除文件，但硬编码 authority 清单是盲点——authority 清单应改用包路径或 glob。

## 2026-07-03 深度瘦身 K2+L+M+N 合批结项：F401 全局门禁启用 + 闭环 + CI 同步

- **K2 教训 (e) 型态「fixture 间接依赖链」新发现**：G1b 记录的 F401 失败四型态 (a)(b)(c)(d) 之外，本批又发现第 (e) 型态 —— 「pytest fixture 间接依赖 fixture 链」。`import fake_u1` 在测试函数签名 (`test_xxx(lima_client, fake_device_server)`) 没出现，但 helper 模块下 `@pytest.fixture\ndef fake_device_server(fake_u1: dict)` 依赖 `fake_u1` 作为 fixture 参数；pytest 收集 test 时通过 fixture 依赖图 resolve `fake_device_server` 又递归 resolve 它的 `fake_u1` 参数，需要 `fake_u1` 名字在 helper 模块的 namespace 里可见，而 import 就是为了让 helper 模块加载到 sys.modules 完成 fixture 注册。删了立即 `fixture 'fake_u1' not found`。修复：尽管理论上 import 不必保留（pytest 应自行发现 fixture），实证删 import 即错——保留 import + `# noqa: F401  pytest fixture, transitively required` 注释释明。
- **L 批 grep-误报 lesson**：ruff F401 报告里附带的 dashed-name bare token 用 `\b...\b` grep 验证会命中**字符串字面量 / 注释 / 函数名** —— `pytest` 命中 `"pytest"` 字符串比较 `"pytest"`、`json` 命中 httpx keyword `json={...}`、`asyncio` 命中 `@pytest.mark.asyncio` 装饰器名（**那不是 asyncio 模块用法**）、`http.client` 命中 docstring "WebSocket client"、`sys` 命中 `via sys.modules` 注释。本批 audit 脚本 grep 显示 6 risky 实际全可删。教训：grep `\bNAME\b` 作为 F401 真死判断不够，需配合上下文人工识别（字符串字面量 vs 真模块用法），但配合 ruff --fix 的 pure 删除模式（ruff 不删 active import），可大胆 `ruff --fix` 后立即 pytest 验证。
- **M 批生产侧 exclude reference lesson**：reference/grbl_fix/ 5 个 F401 在 `sys.state` 等 C++ 代码字符串字面量里被 ruff 识为活，但 module sys 真死。决策按 AGENTS.md「禁止暂存参考仓库」改为在 `ruff.toml` `exclude = ["reference/**"]` 直接豁免，不删 F401。这与生产路径 F401 gate 启用后不冲突——exclude 的目录 ruff 完全不扫，对主线行为产线零影响。
- **M 批 ruff format 副作用 lesson**：`ruff --fix --select F401 .` 不会改 format，但本批紧跟的 `ruff format .` 一并规范化了 23 个生产 / tests 文件（EOL 缺尾 newline / 单→双空行 / Optional[X]→X|None 等 G1b 后周期早应做过的格式化）。这些 silent 升级 G1b 时是否有意保留 NO，本批一并打平。教训：每次格式化 repo-wide 各种 small NIT 改动，应单独 commit 或明确记录到 progress，避免 noise 混进 F401 逻辑批的 commit。本批遵守「K2+L+M+N 合一 commit」原则一次过。
- **里程碑意义**：F401 全局 gate 启用 = 从 G1b 提出的「四型态具名失效 + lesson learned」到现在的工程闭环。今后 TDD 抽离批次会有 ruff 全 repo F401 0 报告做 baseline 守护，新的死 import 引入会立即被本地 commit + CI 双门拒收，不再有 F401 静默死代码潜逃空间。H2 的 F401 安全门 (`pytest --collect-only`) 与 M 的 ruff F401 全局 gate 形成两层防线 —— ruff 第一道静态过滤，pytest 收集动态验证字符串匹配/fixture 间接依赖 (d)/(e) 型态。

## 2026-07-03 深度瘦身 K 批次结项：测试侧 mixed 桶 10 文件 39 个真死 imported-name 逐文件清理

- **K 批次审计 agent 不可全信 lesson**：本批再次证明「依靠 Explore/general-purpose agent 给出的 F401 归桶分类绝不可直接作为删除依据」。审计 agent 在 mixed / domain dead 两桶里把 `fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 归为「domain dead imports 可删」—— 但这 6 名都是 G1b 已显式记录的 (d) 「pytest fixture 字符串匹配注入」型态（在测试函数签名作为参数名出现、pytest 收集期注入、ruff 看不见），删了会再现 18 ERROR。**教训**：F401 批量清理的 grader 必须是「亲自 Read + ripgrep 含 `@pytest`/`pytest.`/fixture 名/builtin 装饰器等多重 grep」人工审视，agent 报告只能作为初始引导而非最终删除清单。本批用此方法把 plan 锁定的 37 个删名扩展到 39 个（补了 `os` 与 `verifier as attestation_verifier` 两个我之前 Read 时漏审的真死名）。
- **K 批次 monkeypatch.setattr 字符串属性 ≠ import 别名 lesson**：`test_device_attestation.py` 中 `attestation_verifier` 字符串出现在 `monkeypatch.setattr(handlers, "attestation_verifier", ...)` 多处，第一反应会认为 import 别名 `verifier as attestation_verifier` 是必需的；实际 `setattr` 的第二参数只是属性名字符串，handlers 自己有 `attestation_verifier` 属性，本文件 import 的别名并不被引用，删安全。这种「import 别名 = 已存在 attribute 名」的字符串字面量引用是另一种 F401 隐蔽活跃假象。
- **K 批次新形态「局部变量遮蔽 import」lesson**：`test_provider_automation_model_entry.py` 中 `from provider_automation_helpers import entry` module 与文件内每个测试函数的 `entry = ProviderModelEntry(...)` 局部变量同名，所有 `entry.xxx` 都用局部实例、永远不引用 module import。这意味着 module import 真死可删，但需 visualize 全文件每个 `entry` 出现位置的上下文（`entry = ProviderModelEntry(...)` 分配行 vs `entry.xxx` 使用行）才能区分二者。ruff 默认把 import `entry` 视为活（因为名字 `entry` 在文件中出现），实际是遮蔽假活 —— ruff 此处表现尚算正确报了 F401，但人工审视要小心局部变量同名遮蔽带来的视觉混淆。
- **K 批次不动 6 文件 (d) 注入型态说明**：fake_u1_cloud 4 文件 (`test_fake_u1_cloud_draw_svg.py` / `home` / `rejection` / `write_text`) 与 device_app_sharing 2 文件 (`test_device_app_sharing.py` / `_permissions.py`) 的 `fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 在测试函数签名参数出现，属 (d) pytest fixture 注入型态。这两类真正永久解法：(a) 在 helper 模块 (`fake_u1_helpers.py` / `device_app_sharing_helpers.py`) 的 `# noqa: F401` 上注明 re-export/fixture 用途；(b) 在消费测试文件直接 `# noqa: F401` 后跟 `# fixture injected by pytest` 释明。本批暂留 K2 批处理。
- **K 批次效果**：测试侧 F401 总数从 141 减到 102（删 39）；含 F401 文件数从 91 减到 81（删文件内全部 F401 的进入 0 报告状态）。门禁全程绿，无运行时行为变化。

## 2026-07-03 深度瘦身 J 批次结项：唤醒词握手层抽离到 accept_websocket_upgrade 纯函数

- **J 批次 accept_websocket_upgrade 接缝设计结论**：抽离不另起新模块（Ponytail YAGNI：能不拆就不拆）——握手协议就放在 http_server.py 顶部模块层级，与 `build_handler_class` 工厂并列；接受 duck-typed `handler` 参数注入 `.headers.get / .send_response / .send_header / .end_headers / .send_error / .connection / .wfile` 七个实例 API，返回 `(reader, writer)` 或 `None`（已 send_error 后）。**关键设计点**：_RDONLY 直引 `SimpleHTTPRequestHandler` 类型注解就够（不需要顶层属性 + lazy `_resolve_*()` 兜底链模式，因为 handler 是从类外部注入而不是要在 importlib 无父包环境里相对导入），相比 `websocket_session / bridge_request_handler` 的 callback 注入模式更简单。`_handle_websocket` 从 >20 行收紧到 ~9 行接缝（`upgraded = accept_websocket_upgrade(self)` → `None 则 return` → `reader, writer = upgraded` → `serve_websocket_session(...)`）。
- **J 批次契约特征化测试 lesson learned**：I 批次 plan 在候选清单里提到「Sec-WebSocket-Version 不校验」是潜在改进点，本批 TDD RED-first 把它显式化为特征化测试 `test_websocket_handshake_succeeds_without_sec_websocket_version`——用 `ws_handshake(include_version=False)` 触发握手，断言还能 101 + 收到 bridge_connected ready frame。**教训**：纯结构重构步骤里若有「未来可改进 X」的契约盲点，先把现状显式写成特征化测试，是把隐性契约转成显式契约、避免将来悄悄收紧校验时 silent break 浏览器/客户端的最廉价手段。本测试若将来引入 Version 13 严校验会变红，由改 PR 显式决策契约方向，而非静默回归。
- **J 批次进度同 I 批次一致**：full 4427 → 4428 passed（恰好 +1）、check_code_size PASS、ruff + pyright 全过、http_server.py 170 → 187 行（结构 +17 行新函数 / -9 行 _handle_websocket，净 +1 行，远低于 300 限）。

## 2026-07-03 深度瘦身 I 批次结项：唤醒词 http_server 类工厂抽离 + 握手错误路径特征化测试

- **I 批次死代码诊断结论**：F2 抽离 `frame_codec`、G2 抽离 `bridge_request_handler`、H1 抽离 `websocket_session` 后，`data/digital-human/wakeword_runtime/runtime/http_server.py` 的 `_build_server` 内嵌 `TestRuntimeHandler` 类残留 **7 个一行 delegator wrapper 方法**（`_build_wakeword_config_message` / `_handle_bridge_request` / `_save_wakeword_config` / `_receive_websocket_message` / `_read_exact` / `_send_websocket_text` / `_send_websocket_frame`），方法体都只是 `return <已抽离模块的顶层函数>(...)`，但因 `_handle_websocket` 改成直接调 `websocket_session.serve_websocket_session(...) / bridge_request_handler.handle_bridge_request(...)` 等顶层函数，**全仓 ripgrep `self._<method>` 0 命中**，确认是纯死代码。**教训**：每一次「抽离纯函数模块 + 把调用点委托到顶层」的重构收尾必须 grep `self._<method>` 审计遗留 delegator，否则会静默残留无消费者的一行包装直至下次人工巡察——本批 7 个 wrapper 累积已 ~6 月（跨越 F2/G2/H1 三批，每批抽离后未立即清 delegator，全部留到本批一次性销账）。**改进**：未来抽离批次步骤应固化「5 解析调用点 → 6 调用点委托到顶层函数 → 7 grep `self._<原wrapper>` 删 delegator」三步成链条。
- **I 批次类工厂抽离结论**：原 `_build_server` 把 `class TestRuntimeHandler(SimpleHTTPRequestHandler)` 嵌在闭包体内只捕获 `test_root / event_bridge / schedule_restart` 三个自由变量。抽到模块级 `build_handler_class(test_root, event_bridge, schedule_restart) -> type[SimpleHTTPRequestHandler]` 后——(1) 与三个姐妹模块（`frame_codec` / `bridge_request_handler` / `websocket_session`）「模块级纯函数」风格对齐，handler 类也可在 `http_server.build_handler_class(...)` 直接构造/单测而无需实例化 `TestRuntimeHttpServer`；(2) `_build_server` 收缩到 4 行「调工厂 + ThreadingHTTPServer + daemon_threads + return」；(3) 闭包捕获不变（仍是同 3 个 deps），无新运行时行为，纯结构重构。**保留不抽的部分**：`_handle_websocket` 握手路径仍强依赖 `self.headers / self.send_response / self.send_error / self.wfile / self.connection`，本轮不动；并在模块顶部 ponytail docstring 标注上限「握手层强依赖 SimpleHTTPRequestHandler 实例 API」+ 升级路径「换 wsproto/starlette 框架后将握手层一并下沉」。
- **I 批次握手错误路径特征化测试结论**：H1 端到端集测只覆盖 happy-path 101 握手（通过 support helper `ws_handshake` 的隐式 `"101" in status_line` + `Sec-WebSocket-Accept` 校验），**两 BAD_REQUEST 分支（无 Upgrade 头、无 Sec-WebSocket-Key 头）此前零覆盖**。本批以特征化测试（非新功能、锁现有契约）补 2 个 http.client 测试，跑过即绿，使下一步类工厂抽离有完整回归网。**意义**：TDD 在纯结构重构场景下「先 RED 不可能、改用特征化测试锁现有契约」是正确变体——这是 TDD-not-an-ideology 的可证实用法。
- **I 批次 from-import 收敛结论**：删 7 个 wrapper 后唯一引用 `read_exact` / `send_frame` 的代码消失，把 `from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text` 收敛到 `from .frame_codec import compute_accept, receive_message, send_text`（3 个），减小模块接口表面积、消除 F401 风险。

## 2026-07-03 深度瘦身 H1+H2 批次结项：测试侧 F401 安全门工具化 + 唤醒词 WebSocket 会话抽离

- **H2 F401 安全门工具化结论**：基于 G1b lesson learned（四类具名失效型态，特别是 pytest fixture 字符串匹配 (d) 类对 ruff 完全不可见）建仓化安全门：新建 `scripts/testside_f401_safety_gate.py`——本门在 pre-commit 流程中当且仅当 staged 文件含 `tests/*.py` 时触发 `python -m pytest --collect-only -q`，若收集失败（含 ERROR 等级）按 ERROR 行解析出失败测试文件，跳过 baseline-skip 文件后打印失败列表 + 四型态提示 + 收集尾 30 行 triage 输出，返回非零阻止提交。**设计要点**：(1) 触发型态判定用「file path 是否在 tests/ 子树」简单前缀，不依赖 git staged 列表的 pandas 化；(2) `--baseline-skip-from` 接受已知破损文件清单（不与 stdin 冲突），让渐进清理批可豁免旧债；(3) main() 函数经 `_build_argparser()` + `_print_blocked()` 拆分保持每个函数 ≤50 行通过 check_code_size；(4) 集成入 `run_pre_commit_check.py` 的 `run_testside_f401_safety_gate()`，置于其他快速检查之后、`--full` pytest 之前，保证 fixture-removal 类失败被快速捕获而非慢跑后才察觉。10 个 gate 单测验证纯 helper 行为（path 过滤、ERROR 解析、baseline 过滤、main 早早返回路径），不调用 pytest 本身避免依赖。**意义**：把 G1b 的「人工 lesson learned」永久固化为门禁，使下一批测试侧 F401 清理工作时即便是不同执行人，也能在误删 fixture 时直接被本地 commit 拒收，不再依赖运行时 pytest 才发现 18 errors 类型的灾难。
- **H1 wakeword WebSocket 会话抽离结论（了结 G2 「`_handle_websocket` 仍需先补端到端测试」遗留）**：以 TDD 方式补 `tests/test_wakeword_session_integration.py`（5 个端到端集成测试）：用 importlib + sys.modules alias package（`wakeword_runtime_pkg.{runtime,bridge}` 合成包）让 hyphen 路径 `data/digital-human/...` 可导入；fixture 在 ephemeral port 0 起 TestRuntimeHttpServer + 内嵌 plumbing（seed config.json/models/keywords.txt），测试驱动 raw socket + http.client + 手写 RFC6455 client handshake 跑 `/health`、握手 Ready 帧、`set_wakeword_config` round-trip、restart、unknown type fallback 五例。`pytest.importorskip("pypinyin")` 跳过外部依赖缺失环境以保证集测可跑。集成测试通过后（守住现有行为），抽 `_handle_websocket` 内嵌 46 行事件循环体（post-handshake 的 client_queue.add → greeting → 双向轮询 → finally remove）到 `websocket_session.py`（99 行纯函数模块 `serve_websocket_session(reader, writer, bridge, test_root, schedule_restart, send_text_writer, receive_reader_writer)`），http_server 仅保留 HTTP/WebSocket 握手（强 self.send_response/headers 依赖），178→164。沿用 frame_codec/bridge_request_handler 模式：`handle_bridge_request` 与 `build_wakeword_config_message` 顶层属性（非 from-import）链入由 http_server.py import 后 setattr 真实实现；测试可 setattr 注入 fake。集成测试在抽离前后全过，证明运行时行为不变。**关键 lesson learned 沉淀**：导入 plumbing（cosmetic alias package 注册 + http_server 加载 + WS frame helpers 计 130+ 行）必须在独立 `_wakeword_integration_support.py`（pytest 不收集因 `_` 前缀），保持 test 主文件 193 行 / support 191 行双双 ≤300；并验证 check_code_size 不漏判 scripts/testside_f401_safety_gate.py（73 行 main 函数拆 helper 通过 50 限）—— 两起台护在 H1+H2 落地中 ÷ 落林 met 限制反弹。
- **门禁全程绿**：`ruff check .` / `ruff format --check` clean（仅格式化本批新增/修改的 4 个 production G2/H1 文件 + 6 个 H2 测试/脚本文件）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50，需拆 `_print_blocked` 与 `_build_argparser` 后通过）；`pyright` 本批 4 个相关文件 0 errors 0 warnings；全量 `pytest --tb=short -q` → **4425 passed / 3 skipped / 2 deselected / 0 failed**（较 G1+G2 的 4410 +15，与 H2 +10 gate 单测 + H1 +5 集成测试 一致）。pypinyin==0.55.0 已 pin 入 `.venv310` 测试环境（与 `data/digital-human/wakeword_runtime/requirements.txt` 一致）使 H1 集成测试可正常运行。

## 2026-07-03 深度瘦身 G1+G2 批次结项：台账销账 + 测试侧 F401 精选 + 唤醒词桥接请求抽离

- **G1a PONYTAIL-DEBT 台账销账结论**：`check_code_size.py 残留 12 个 51-54 行函数`条目经独立 AST 扫描（51-55 行范围、全仓非排除目录）确认实际已 **0 个超限函数**（E6-E9 等早批已清理），条目陈旧。删除条目并补「已结清」记录，无代码改动。**教训**：PONYTAIL-DEBT 触发条件「触发下一个生产函数超 50 行时一并清理」始终未触发，但债务实际已被前批隐式清偿，台账与代码事实脱节 6 个月以上。台账需周期性自检（如 CI 阶段对每个「当前标记」条目跑一次 AST 验证），不能只等触发条件。
- **G1b 测试侧 F401 精选清理结论**：测试侧 F401 共 202 处，分两群：(1) port-target / 隐式 fixture 用法（`pytest`/`os`/`time`/`unittest.mock.{MagicMock,AsyncMock,patch}`/`asyncio`/`importlib`/`builtins`/`threading` 共 ~80，多为 ruff 看不到的间接使用）—— 保留；(2) domain dead imports（`device_voice.exceptions.{AuthenticationError,ConfigurationError,VoiceProviderError}`、`device_gateway.attestation.*`、`client_keys.models.ClientKey`、`chat_models.{ChatRequest,Message}` 等 ~120，可安全删）。本批采用 STYPE 分类清理：49 个 STYPE_CLEAN 文件（safe-only）经 F1 别名感知审计全过 0 danger，逐文件 `ruff --fix` 移除共 84 处。剩 143 处为 KEEP-infra + mixed 文件留待后续批逐文件人工核对。
- **G1b 二轮 + 三轮审计盲点 + 修复**：F1 提炼的「别名访问」具名失效风险再加上 pytest 用 conftest 把 `tests/` 加到 sys.path，消费者写 `from fake_u1_helpers import ...`（**前缀基名**而非 dotted path `tests.fake_u1_helpers`）。审计脚本的 `module == file_dotted_path` 严格相等漏掉此模式，`tests/fake_u1_helpers.py` 经 `--fix` 误删 `motion_task_to_u1_commands` 后下游 `test_fake_u1_protocol_translation.py` 收集失败。**修复**：恢复 import 附 `# noqa: E402,F401`，说明 re-export。
- **三轮审计盲点（pytest fixture 字符串匹配）+ 修复**：恢复后仍 18 ERROR：`test_device_app_sharing.py`/`test_device_app_sharing_permissions.py` 用 `accept_share`/`client`/`seed_guest` 作 pytest fixture（在测试函数签名声明为参数），`test_fake_u1_cloud_*.py` 4 文件用 `fake_device_server`/`fake_u1`/`lima_client` 作 fixture。pytest 在**收集期**通过参数名字符串匹配发现 fixture，**对静态分析完全不可见** —— ruff 看不出这些 import 是 fixture 注入而非死导入。我的 INFRA_KEEP 列表只覆盖 `pytest`/`patch` 等内建 fixture，未覆盖测试模块自定义 fixture。修复：回退 6 个消费测试文件到 HEAD。**关键教训**：测试侧 F401 具名失效有四种型态 —— (a) `from <module_dotted> import <name>` 直引；(b) 模块别名访问 `<alias>.<name>`；(c) pytest sys.path 根基名引用 `from <baseline> import <name>`；**(d) pytest fixture 字符串匹配注入**（import 名作为测试函数参数名，由 pytest 收集期发现，ruff 完全不可见）。统一经验：**「批量 F401 清理安全门 = 删除前先 `pytest --collect-only` 通过全测试套件」**，而非单靠静态审计；或在 INFRA_KEEP 列表里把所有 `@pytest.fixture` 注解函数名 + 所有测试函数签名参数名全部动态加入 KEEP 集合。
- **G2 唤醒词桥接请求 handler 抽离结论**：F2 抽离 WebSocket 帧编解码后，http_server.py 嵌套类内剩余 44 行 `_handle_bridge_request`（捕获 `test_root`/`schedule_restart` 闭包，结构清晰）是合适的下一抽离粒度。以 TDD 方式补 6 个 RED 测试（importlib 加载、含 fake save_wakeword_config 注入验证 publish/build_message 契约、save 异常降级路径、restart 调度、unknown/empty 类型 fallback），新建 `bridge_request_handler.py`（121 行纯函数模块，`handle_bridge_request` 主入口 + 2 个 helper）。**关键解耦**：`save_wakeword_config` 不在顶层 from-import（避 importlib 无父包相对导入失败），改为顶层 `save_wakeword_config: Any = None` + `_resolve_save()` 延迟相对导入兜底；http_server.py 在 import 后 `bridge_request_handler.save_wakeword_config = save_wakeword_config` 显式链入真实实现，测试用 `setattr` 注入 fake。`WakewordEventBridge` 类型注解改 `Any`（duck-typed 避开 F821）。http_server.py 213→178 行，闭包依赖与 `_handle_websocket` 事件循环不动。**遗留**：`_handle_websocket`（46 行，与 `client_queue` 紧耦合）仍需先补端到端 WebSocket 集成测试再考虑抽离。
- **门禁全程绿**：`ruff check .` / `ruff format --check` clean（仅格式化本批改动的 4 个 G2 文件 + 7 个 G1b 测试文件因 `--fix` 后 ruff format 建议合并括号）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50）；`pyright` 本批 3 个相关文件 0 errors 0 warnings；全量 `pytest --tb=short -q` → **4410 passed / 3 skipped / 2 deselected / 0 failed**（较 F1+F2 的 4404 +6 = G2 新增 6 个 bridge_request 测试）。

## 2026-07-03 深度瘦身 F1+F2 批次结项：死导入清理 + 唤醒词 WebSocket 帧编解码抽离

- **F1 生产路径 F401 死导入清理（精选策略）结论**：`ruff --select F401` 全库 341 处分布无序，但测试侧 ~253 处多为 patch-target 导入（曾导致 85 个收集错误），本批**只动生产侧**。采用「AST 审计 + 别名感知 + noqa 保留 re-export」两轮策略：第一轮扫测试 `from <module> import <name>` 与点号 `<module>.<name>`，识别 9 个 must-keep re-export，标 `# noqa: F401` 后逐文件 `ruff --fix`；首轮跑 pytest 出现 12 failed / 22 errors，根因是 server_bootstrap.MODEL_ID（被 server.py 生产侧 `from server_bootstrap import MODEL_ID` 重新引用）等 re-export 实际经**模块别名访问**（`dg._reset_for_tests()`、`_a.BACKENDS`、`hs.flush_pending_save()`、`text_to_path.list_handwriting_fonts()`），第一轮纯文本扫描漏检。第二轮「别名绑定 → 别名点号访问」双向解析审计覆盖全仓未改文件，补出 9 个 must-keep，全用 noqa 恢复后门禁转绿。**关键教训**：模块别名（`import M.sub as A` / `from pkg import sub`）会把 re-export 使用方从源模块全名变成短别名，单测「import 一次 = 可被 patch」不是高危机型态；「re-export 被下游模块别名访问」才是更高危且更隐蔽型态。安全审计必须同桌双向解析。统计：清理 ~97 处（91 真死导入 + 17 noqa 保留 re-export，少数原有重叠）。剩余测试侧 F401 ~253 处留待后续单独批逐文件人工核对。
- **F2 唤醒词 WebSocket 帧编解码抽离结论**：E8 批次曾保守地把自我/socket 依赖的 WebSocket 帧实现留在内嵌 handler 中（无测覆盖、不敢盲拆）。本次以 TDD 方式补齐：先全 16 个 RED 测试（`tests/test_wakeword_frame_codec.py`，用 importlib.spec_from_file_location 加载避开 hyphen 路径不可直接 import 问题，覆盖 compute_accept RFC6455 范例向量、read_exact 短 EOF、receive_message masked/unmasked 解掩码/ping 自动 pong/close 抛 ConnectionAbortedError/pong 忽略/未知 opcode/126 扩展长度/空载荷、send_frame <126/126/127 三种长度编码、round-trip），再新建 `data/digital-human/wakeword_runtime/runtime/frame_codec.py`（118 行纯 stdlib 函数模块包含 compute_accept/read_exact/receive_message/send_frame/send_text 五个纯函数，模块头附 ponytail 注释说明上限「仅 RFC6455 最小帧子集，无分片/RSV」与升级路径「换用 wsproto」），最后 REFACTOR http_server.py 委托：`_handle_websocket` accept 计算、`_receive_websocket_message`、`_read_exact`、`_send_websocket_text`、`_send_websocket_frame` 全部委托 frame_codec。**闭包依赖 `test_root`/`event_bridge`/`schedule_restart` 与 `_handle_websocket` 事件循环主逻辑不动**，仅 codec 抽离；WebSocket 帧读写仍由 `self.connection`（reader）/`self.wfile`（writer）传递，运行时行为不变。http_server 274→212，新模块 118 行附 ponytail: 标记。**正式了结 E8 遗留**「WebSocket 帧实现仍为内嵌 284 行函数，未来需补测后再考虑拆分」。
- **F3 test_jdcloud_push_probe.py 贴顶下移结论**：300 行贴顶的测试文件尝试提取 `monkeypatch_post` shared-feature 合并 3 处 `monkeypatch.setattr(push_probe_results, "_post_payload", ...)`：实测反而增至 305 行（fixture 定义净增 11 行，仅每个 test 删 3 行），未达瘦身目标，**回退**保持 300 行现状（贴顶但未破门禁，符合 ≤300 限额）。下次若需进一步降行，需用更紧凑 fixture + 函数尾部断言合并，或重排测试以合并相似前缀，但收益微小，优先级低。
- **门禁全程绿**：`ruff check .` clean；`ruff format --check` clean（仅格式化本批改动的 4 个 routes/router_v3 文件，未触碰既有 10 个 pre-existing format-dirty 文件以避免污染 diff）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50）；`pyright` 对本批改动的 8 个生产文件 0 errors（仅 `routes/device_gateway.py` 2 个与 F1 无关的既有 JSONResponse.get 误警，与 HEAD 相同）；全量 `pytest --tb=short -q` → **4404 passed / 3 skipped / 2 deselected / 0 failed**（较 E6-E9 的 4388 +16，与 F2 新增 16 个 frame codec 测试一致）。

## 2026-07-02 深度瘦身 E6-E9 批次结项：长函数/退役端点/唤醒词抽离/台账同步

- **E7 eval_internal 退役端点移除结论**：`routes/eval_internal.py` 自 v3.0 起为 410 Gone 桩（`/internal/v1/eval/call`，原用于 FRP 本地代理直连后端评估，编码能力退役后保留作占位）。经全库 grep 核实，生产代码与测试中仅路由注册 + 退役测试两处引用，**无任何运行时调用方**。确认安全删除：文件删除 + `route_registry.py` 注册行移除 + `test_eval_internal_is_retired` 测试移除。删除后 `route_registry` import OK，23 个 routing authority 测试全过（删除前 23→删除后 22，与移除单测一致）。
- **E8 唤醒词运行时抽离结论**：`data/digital-human/wakeword_runtime/runtime/http_server.py` 是独立运行的唤醒词本地 HTTP 服务（含内嵌 `TestRuntimeHandler` + WebSocket 帧实现）。该文件位于 `data/` 目录（被 `check_code_size.py` 排除审计）且**无任何测试覆盖**。本次仅抽离「无 socket/self 依赖的纯逻辑」（配置读/写/拼音转换）到 `wakeword_config.py`，保留强依赖 `self.connection` 的 WebSocket 帧逻辑在内嵌 handler 中以免破坏未经测试的闭包语义。http_server 347→274，新模块 96 行并附 `ponytail:` 标记记录 pypinyin 依赖上限。**遗留**：WebSocket 帧实现仍为内嵌 284 行函数，未来需补测后再考虑拆分。
- **E9 PONYTAIL-DEBT 台账同步结论**：核对源码后发现台账中 6 条标记对应代码已物理移除（capability_matrix/task_creation/task_events/mqtt_client/quota 的 lazy-import 解耦已落地、chat-web config.js 文件已不存），属「已结清但台账未销账」的脱节。同步删除 6 条失效条目、修正 3 条偏移行号、补录 1 条新标记。**教训**：台账应与每次解耦落地同步销账，否则会累积失真。
- **门禁**：ruff/format clean；pyright 0 errors（pypinyin 可选依赖 warning 与抽离前一致）；check_code_size PASS；全量 pytest **4388 passed / 3 skipped / 2 deselected**（exit 0，149.56s）。
- **下一步**：commit/push origin → VPS 部署 + 公网冒烟。

## 2026-07-02 系统瘦身 P2-17/18/19/20 + 参考改善 T1/T2 全部闭环

- **范围**：P2-17/18（UI 合并）、P2-19（settings 瘦身）、P2-20（except:pass 审查）+ T1-1（语义分类器）、T1-2（管道架构）、T1-3（Hershey 字体）、T2-2（健康探针）、T2-3（任务时间线）、T2-1（FluidNC 迁移准备）
- **P2-20 发现**：83 处 `except:pass/continue` 中仅 3 处是真正的宽泛异常静默吞掉（违反硬规则 #1），其余 80 处是特定异常类型（`json.JSONDecodeError`、`KeyError` 等）的合法控制流。审查脚本需区分 `except Exception:` 与 `except SpecificError:` 才能准确识别违规。
- **P2-19 发现**：6 种语言中 4 种（de/vi/pt_BR/zh_TW）是臆测添加——无实际用户、翻译不完整、i18n 键覆盖率低。裁到 zh_CN+en 后无任何功能损失。
- **P2-17/18 发现**：mine 页面本质是「设置页的子集」——声纹入口、退出登录、关于、设置跳转，全部可合并进 settings。WorkshopHome 与 device-list 数据源相同（`v2GetDevices`），Hero 卡片设计相似，合并为零信息损失。write-draw-panel 已是 2 步简化流，create/ 是高级模式，两者并存合理。
- **T1-1 发现**：n-gram TF-IDF 方案在不引入 sentence-transformers 重型依赖的前提下实现了毫秒级语义匹配（< 1ms），准确率覆盖核心意图（coding/chat/explanation/translation）。比正则规则维护成本低一个量级。
- **T2-3 发现**：Ledger 事件流已天然支持时间线查询，无需 schema 变更——`events_for_task` 已有事件记录，只需聚合视图层。
- **验证**：Python 4391 passed / 0 failed；ruff check clean；pyright 0 errors；vue-tsc 0 errors；mp-weixin 编译成功。

## 2026-07-02 小程序 UI 审查配合核实纠偏：三项指控两项伪判一项属实（BACKLOG-P2-1）

- **背景**：瘦身审查报告提三项 UI 指控（create 937 行嵌套两层 tab、3 首页重叠、settings 744 行杂物），并附「chat 与 create 重叠」隐含问题。逐项核实源码后真伪分明。
- **属实项**：`create.vue` 937 行嵌套两层 tab — **属实**。`mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 两层切换，且两路走不同 API（`generateImage` 云生图 vs `v2SubmitTask` 设备任务），合成 937 行（script 254 + template 240 + style 430，style 占 46% 大头）。应拆两页，已拆（M2）。
- **部分属实项**：3 首页重叠 — **部分属实**。mine 统计卡（设备/在线/任务 3 数字）与 index 智能体页 Hero 设备卡的数据重复；mine「设备管理」「设备配网」两菜单跳底栏已有的 tab（多 1 步冗余跳转）。已去重（M3：mine 删统计+删冗余菜单，转纯账号页；index Hero「设备 X 台」改为「在线 X/总 Y 台」吸收在线统计）。
- **伪判项 1：settings 744 行「杂物」** — **不属实**。逐区块核实，全部是设置页职责（网络设置/缓存管理/隐私权限/通知订阅/注销账号/关于我们/语言设置），无一非设置功能混入。臃肿源于 7 个 section 的标题+卡片壳样式重复未抽组件，加 `useConfigStore`/`systemInfo` 2 处死代码。已抽 `SectionCard` 组件去样式重复 + 删死代码（M1），744→655 行。
- **伪判项 2：chat 与 create 重叠** — **不属实**。chat 用 `chatCompletionStream`(文本流式 LLM)、create 用 `generateImage`+`v2SubmitTask`(生图/设备任务)，零交叉导入，入口逻辑不重复。不动。
- **教训**：审查「行数/嵌套层数」计数可信，但「杂物/重叠」定性不可信。改 UI 前必须逐区块核实每个功能点的归属（是否真在该页职责范围、是否真与它页重复），不能按行数或审查措辞盲改。

## 2026-07-02 agent 配置树合并纠偏：审查「8 棵树 9300 行重复」多数被 gitignore 不入库（BACKLOG-P1-4）

- **背景**：瘦身审查报告称「~9300 行 agent 指令跨 8 棵配置树（`.agent`/`.claude`/`.kimi-code`/`.cursor`/`.joycode`/`andrej-karpathy-skills`/根），Ponytail 规则重复 6 处」，建议合并。
- **纠偏结论**：8 棵树中 **5 棵被 `.gitignore` 忽略、不入库**（`.agent`=行361、`.claude`=行130、`.kimi-code`=行28、`.continue`=行363、`andrej-karpathy-skills`=行47）——这些是各 IDE/Agent 工具的**本地私有配置**，重复是工具生态正常现象，不应也不能「合并」。
- **真正入库的 agent 树**仅 5 个：`.cursor`(2 rules)、`.joycode`(2 memory)、`skills`(14)、`AGENTS.md`、`CLAUDE.md`。其中真正冗余的只有 `.cursor/rules/` 两份：
  - `ponytail.mdc`（`alwaysApply:true`）与 `docs/AGENTS_PONYTAIL.md`（被 `AGENTS.md` 引用为权威 Ponytail 顾问规则源）内容重复。
  - `ecc-workflow.mdc`（`alwaysApply:true`）与 `docs/ECC_WORKFLOW_CN.md`（被 `AGENTS.md` 引用为权威 ECC 流程源）内容重复。
- **处置**：删除 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`，`AGENTS.md` 保持单一权威源；保留 `.cursor/rules/lima-*.mdc`（未入库的本地 Cursor 私有 rules，不影响入库面）。
- **教训**：审查把「本地工具私有配置」也算入「跨树重复」是口径错误。合并前必须 `git ls-files <tree>` 区分入库与本地私有——后者重复无害、前者才是可统一项。

## 2026-07-02 静默降级审查纠偏：审查报告「16 处」实际一等生产路径仅 4 处（BACKLOG-P1-2）

- **背景**：瘦身审查报告称生产路径有 16 处 `except: pass/continue` 静默降级，点名 `voice_pipeline_ws.py`/`mqtt_client.py`/`store_voiceprint.py` 各 2 处。用 Explore 子代理逐点实地核查。
- **纠偏结论**：审查的「计数」准确（这些文件确各有 2 处 pure-swallow），但「严重度」错误——被点名的 6 处**全部合规**：
  - `voice_pipeline_ws.py`：`asyncio.TimeoutError`→continue（队列轮询超时，正常循环）、`asyncio.CancelledError`→pass（关闭时等待已取消 worker）；两处广义 `except Exception`（L123/L131）不是吞——它们 `_send_error` 后 return，worker 广义 handler（L169）有 `warning(exc_info=True)`。
  - `mqtt_client.py`：`asyncio.CancelledError`→pass（stop 时任务取消，兄弟 `except Exception`（L105）有 warning）、`asyncio.TimeoutError`→pass（消息泵 `wait_for` 超时后 drain，惯用法）；`except ImportError`（L187）不是静默——前面有两条 `_log.info`。
  - `store_voiceprint.py`：两处 `sqlite3.OperationalError`→pass 均是 schema 迁移幂等（`# column may not exist yet` / `# Column already exists`），有注释；所有广义 `except Exception`（L51/L150/L185/L208）都有 warning。
- **真正违反 AGENTS.md「禁止静默降级」的一等生产路径 = 4 处**（广义 `except Exception` 裸吞、零日志），本轮已全部修复补日志：
  - `routing_executor_parallel.py`（并行降级执行器）、`speculative_execution.py`（推测竞速内层 future）、`observability/jsonl_store.py`（读遥测文件）、`provider_automation/adapters/cloudflare.py`（编码评分循环）。
- **边界项（本轮不改，记录待排期）**：`packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`、`pricing_probe.py:74` 各 1 处——冷离线提供商探测工具，不在生产请求路径，风险低。若后续要求「全仓零裸吞」再统一处理。
- **教训**：修静默降级不能按 grep pattern 计数盲改。窄化异常（`asyncio.TimeoutError`/`sqlite3.OperationalError`/`json.JSONDecodeError`）做控制流是合规的；只有「广义 `except Exception` + 无日志 + 无重抛」才是违规。审查报告的计数可作线索，严重度判定必须逐点复核。

## 2026-07-02 系统瘦身审查：四维度过度设计诊断 + DEPRECATED 标记误标发现

- **背景**：用户质疑「小程序交互复杂化」+「后端过度设计」。对固件/后端/文档/小程序四维度做了量化审查，确认过度设计系统性存在。详见 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。
- **关键发现（误标 bug）**：`speculative_policy.py` 和 `capability_matrix.py` 顶部标 `# DEPRECATED v3.0 — coding capability retired`，但实际：
  - `speculative_policy.py` 的 `AFFINITY`/`classify_complexity`/`get_affinity_backends` 被 `speculative.py`（请求流水线推测执行步骤）和 `context_pipeline/complexity.py` **活跃 import 使用** —— 是热路径，非死代码。
  - `capability_matrix.py` 的 `classify_intent` 仍被 `tests/test_capability_matrix_intent.py` 测试。
  - **直接删除会导致生产崩溃**。真实情况是「coding 能力退役，但模块本身未退役」。
- **处理**：已修正两个文件的顶部注释，明确区分「coding 退役」与「模块退役」。`routes/eval_internal.py` 确为退役态（返回 410，测试断言），保持原状。
- **教训**：「DEPRECATED」标记的语义必须精确 —— 标记某个能力的退役 ≠ 标记整个文件可删。删前必须 grep 调用方 + codegraph impact 双重确认。
- **其他 P0 已完成**：修 AGENTS.md 3 处断链（reference/ECC→.claude/ecc、reference/ponytail/ 不存在）；修 STATUS.md Telegram 措辞矛盾（通知通道退役 vs gallery 存储 API 复用，两者不同）；删 `.claude/skills/gitnexus/`（与 AGENTS.md「禁止 GitNexus」冲突）；P0-2 U8 音频协议已选方案 A 并改代码。
- **U8 音频协议矛盾（P0-2，已选方案 A，代码已改）**：用户选择方案 A「固件改 PCM」。已在 U8 固件实现上下行 PCM 透传，同时保留 MQTT/Xiaozhi 的 OPUS 编解码路径不破坏：
  - `AudioStreamPacket` 新增 `format` 字段（默认 `"opus"`）；
  - `protocol.h` 新增 `UsesPcm()` 接口，`WebsocketProtocol` 返回 `true`，`MqttProtocol` 继承默认 `false`；
  - `application.cc` 在协议初始化后调用 `audio_service_.SetSendPcm(protocol_->UsesPcm())`；
  - `websocket_protocol.cc` 对下行音频包设置 `format="pcm"`；
  - `audio_service.cc` 的 `OpusCodecTask` 中：上行按 `send_pcm_` 选择 PCM 透传或 OPUS 编码；下行按 `packet->format` 选择 PCM 透传或 OPUS 解码；`PlaySound` 保持 `format="opus"`。
  - **结果**：U8 连接 LiMa 时，hello 帧 `format="pcm"` 与实际发送格式一致；后端无需新增 OPUS 解码依赖。待实际烧录 U8 后验证实时语音/TTS 回放的端到端效果。
- **BACKLOG-P0-1 已关闭**：`deploy_unified.py` 已支持 `--target {aliyun,jdcloud}`，默认 `jdcloud`，避免默认部署到旧 Aliyun pilot 而生产入口在 JDCloud 的错误。详见 `progress.md` 同日期条目。

## 2026-07-01 前端匿名聊天请求已分流至阿里云 pilot

- **结论**：chat-web、`www.donglicao.com` playground、manager-mobile H5 的匿名简单聊天请求现在会发送到 `https://aliyun.donglicao.com/v1/chat/completions`，由阿里云 `lima-router-pilot`（仅免费后端）处理。
- **实现机制**：
  - **chat-web**：`chat-web/js/app-config.js` 运行时判断无 API Key + 默认模型 + 无 tools/图片时选择 pilot；`chat-api.js` 统一通过 `LiMaConfig.getApiUrl()` 获取 URL；`sendMessage()` 在 pilot 返回 429/503/5xx 或网络错误时自动回退主节点一次。
  - **官网 playground**：`donglicao-site-v2/app/developer/playground/page.tsx` 在 API Key 为空且 endpoint/model 为默认 chat 时自动切换 baseUrl。
  - **manager-mobile**：`utils/index.ts` 新增 `getChatBaseUrl()`，未登录且默认模型时返回 `aliyun.donglicao.com`；`api/chat/chat.ts` 流式/非流式 chat 均使用该 baseUrl。
  - CSP `connect-src` 已增加 `https://aliyun.donglicao.com`。
- **部署**：
  - GitHub Actions `Deploy Chat Web` / `Deploy Next.js Site` workflow 已自动部署到 Cloudflare Pages。
  - 京东云 `/opt/lima-router/chat-web` 源文件已同步，作为 FastAPI `/chat/` 静态回源。
  - 京东云 tunnel 入口由直连 `:8080` 改为 `https://127.0.0.1:443`（跳过 TLS 校验），恢复 nginx 作为入口，从而支持 `/mobile/` H5 目录。
  - manager-mobile H5 构建 base 设为 `/mobile/` 并通过 `scp -r` 部署到 `/var/www/chat/mobile/`。
- **验证**：
  - `https://app.donglicao.com/` 与 `https://www.donglicao.com/developer/playground/` 均引用 `aliyun.donglicao.com`。
  - `https://chat.donglicao.com/mobile/index.html` 返回 H5 入口，资源路径以 `/mobile/assets/` 开头。
  - 直接 POST `aliyun.donglicao.com/v1/chat/completions`（Origin: chat.donglicao.com）返回 200，CORS 正常，后端为 `pollinations_openai`。
- **风险与后续**：
  - Cloudflare Worker 兜底/灰度方案已实施并验证：新增 `cloudflare/workers/chat-router.js`，部署到 `chat.donglicao.com/v1/chat/completions*`；无 Authorization 的匿名 chat 由 Worker 代理到 pilot（响应头 `X-Lima-Backend: aliyun`），pilot 异常时自动回源京东云（`X-Lima-Backend: jdcloud`）。
  - manager-mobile 微信小程序包尚未重新上传发版；H5 已部署。

## 2026-07-01 全栈深度质量检查（LiMa + Web + chat-web + 小程序 + 固件）

### 检查范围与结果

- **LiMa 后端**：pytest 4249 passed / 0 failed；ruff clean；pyright 0 errors；code size PASS（修复后）。
- **donglicao-site-v2**（Next.js 官网）：XSS 0、密钥泄漏 0、SEO 正确、apex→www 重定向安全。发现 1 个 MEDIUM：`public/_headers` 缺 CSP/HSTS/X-Frame-Options（仅 X-Content-Type-Options + Referrer-Policy），加固版仅存在于未启用的 `nginx-headers.conf.example`。
- **chat-web**（Cloudflare Pages 前端）：Turnstile 服务端验证正确（fail-closed）、SRI 完整、无密钥泄漏。发现 5 个 MEDIUM：(1) `_headers` 无 HSTS；(2) `'unsafe-inline' script-src` + sessionStorage token 提升 XSS 影响；(3) Turnstile site key 配置但 secret 缺失时静默放行；(4) `hash-assets.mjs` 遗漏根级 `chat-*.js`（immutable 缓存无 bust）；(5) devices.js status 插值未 escape（当前数据安全）。
- **小程序 manager-mobile**：Bearer bug 已修复、AppID 一致、HTTPS/WSS 全覆盖。发现 4 个 MEDIUM：(1) 设备转移 unionid 发送为 `toPhone` 字段（后端契约待核实）；(2) 上传文件类型验证被注释掉；(3) 登录态基于 accountId 而非 token（可能误跳转登录）；(4) 非 WeChat 端 chat streaming fallback 为死代码。
- **固件 esp32S_XYZ**：AUDIT-12 全部 6 项控制（OTA 签名/URL 白名单/WS 鉴权/坐标边界/日志脱敏）均 PRESENT 且无回归。发现 1 个 MEDIUM：`McpServer::DoToolCall` 跳过 `user_only` 执行门禁（未认证本地 WS 可 `tools/call self.reboot` DoS，固件安装仍被 F1 签名门禁阻断）。4 个 LOW：control_ws_token 无写入者（默认开放）、token 比较非常量时间、activation 失败日志含完整响应体、IDF floor 5.5.2 可升 5.5.3。

### 本次修复（3 项）

1. **`config/settings_core.py` 301 行 → 280 行**（违反 ≤300 硬规则）：提取 `get_key_pool_raw`/`resolve_backend_key`/`get_env` 三个纯函数到新 `config/settings_helpers.py`；`config/settings.py` 更新导入源。code size 检查从 FAIL → PASS。
2. **Turnstile fail-open 警告**（`device_logic/turnstile.py`）：当 `TURNSTILE_SITE_KEY` 已配置但 `TURNSTILE_SECRET_KEY` 为空时，启动日志输出 `WARNING`（之前静默放行，无任何日志）。
3. **死代码清理**（`server_lifespan_phases.py`）：移除 `start_auto_indexer`/`stop_auto_indexer` 定义（commit `ba3d64ee` 已移除调用但保留了函数定义）。

### 待跟进项（需独立排期）

- ~~**donglicao-site-v2 `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 CSP/HSTS/X-Frame-Options/Permissions-Policy）。
- ~~**chat-web `hash-assets.mjs`**~~：✅ 已完成（2026-07-01 第二轮修复：扩展哈希覆盖根级 `chat-*.js`）。
- ~~**chat-web `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 HSTS）。
- ~~**6 个 SAFE dependabot PR**~~：✅ 已手动应用（fastapi 0.138.2、python-multipart 0.0.32、pyright 1.1.411、pytest-timeout 2.4、httpx 0.28.1、websockets 16.0）。
- **小程序设备转移 `toPhone` 字段**：核实后端契约是否期望 unionid。
- **固件 `DoToolCall` user_only 门禁**：在执行路径增加 `user_only` 检查。
- **4 个 RISKY dependabot PR**（torch/torchaudio/dashscope/onnxruntime）建议关闭。
- **7 个需独立审查 PR**（eslint-10/typescript-6/types-node-26/react/tailwindcss/vue/wrangler-action/setup-node）。

### 第二轮修复（2026-07-01，commit 49f55b61）

- **`client_keys/storage.py`**：`update_usage()` 改为 raise `ClientKeyStorageError`（不再静默吞 sqlite3.Error）；`import json` 提到模块级。
- **`access_guard.py`**：`_dynamic_auth_configured` 从 bare `Exception` 收窄为 `(ImportError, AttributeError)`。
- **`device_logic/wechat_gateway.py`**：`response.json()` 移入 try/except（ValueError 捕获）；`import time` 提到模块级。
- **`routes/client_keys.py`**：4 个 mutation 端点返回 typed `KeyMutationResponse`（`response_model_exclude_none=True`）。
- **合并重复测试**：`test_security_headers.py` 删除，唯一 `csp_is_strict` 测试并入 `test_routes_security_headers.py`。

## 2026-07-01 Dependabot / pip-audit 依赖漏洞修复

- **扫描结果**：本地 `.venv310` 运行 `pip-audit --local` 发现 5 个包共 17 个已知漏洞：
  - `cryptography 48.0.0` → GHSA-537c-gmf6-5ccf（OpenSSL 静态链接漏洞）
  - `Pillow 10.4.0` → CVE-2026-25990 / CVE-2026-40192 / CVE-2026-42308 / CVE-2026-42310 / CVE-2026-42311
  - `pip 23.0.1` → CVE-2023-5752 / CVE-2025-8869 / CVE-2026-1703 / CVE-2026-3219 / CVE-2026-6357 / CVE-2026-8643
  - `python-multipart 0.0.30` → CVE-2026-53540（负 Content-Length 导致无界读取）
  - `starlette 1.2.1` → CVE-2026-54282 / CVE-2026-54283（urlencoded 表单限制绕过、URL 主机欺骗）
- **修复操作**：
  - 升级本地 venv：`pip==26.1.2`, `cryptography==48.0.1`, `Pillow==12.2.0`, `python-multipart==0.0.31`, `starlette==1.3.1`。
  - 收紧 `requirements_server.txt`：
    - `python-multipart>=0.0.31,<1.0`
    - `Pillow~=12.2.0`
    - 新增显式下限：`starlette>=1.3.1`（FastAPI 传递依赖）、`cryptography>=48.0.1`（Paramiko 传递依赖）。
- **验证**：
  - `pip-audit --local` → `No known vulnerabilities found`。
  - 聚焦 Pillow 相关测试：`tests/test_svg_converter.py`, `tests/test_svg_converter_sketch.py`, `tests/test_svg_binarize.py` → 33 passed。
  - 聚焦 FastAPI/Starlette 相关测试：`tests/test_device_app_auth.py`, `tests/test_routes_chat_preflight.py`, `tests/test_routing_engine_post.py` → 25 passed。
  - 完整门禁 `scripts/run_pre_commit_check.py --full` → 4239 passed, 3 skipped, ruff 通过。
- **扩展修复（esp32S_XYZ 子模块）**：
  - 子模块仓库同步提交并 push 到 `zhuguang-ZFG/esp32S_XYZ`。
  - `esp32S_XYZ/requirements.txt`：`pytest>=9.0.3`（CVE-2025-71176）。
  - `esp32S_XYZ/firmware/u8-xiaozhi/scripts/Image_Converter/requirements.txt`：`Pillow~=12.2.0`。
- **扫描工具误报说明**：
  - 运行 `pip-audit` 时，本地杀毒软件将 `cyclonedx-python-lib` 的 `vulnerability.cpython-310.pyc` 误报为 `HEUR:HackTool/VulnScan.a` 并删除。
  - 已执行 `--force-reinstall pip-audit` 恢复，`pip-audit --local` 再次运行正常。
- **扩展修复（前端与容器）**：
  - `donglicao-site-v2/package.json`：添加 `overrides` 强制 `postcss>=8.5.10`；`npm audit` 归零，`npm run build` 成功。
  - `docs-site/pnpm-workspace.yaml`：添加 `overrides` 强制 `vite ^6.4.3`、`esbuild ^0.25.0`；`pnpm audit` 归零，`pnpm run build` 成功。
  - `Dockerfile`：基础镜像从浮动 `python:3.10-slim` 固定为 `python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455`。
- **额外修复**：
  - `.github/workflows/test.yml`：将错误的 `actions/checkout@v7`、`actions/setup-python@v6`、`actions/cache@v6` 改为正确的 v4/v5/v4。
  - 2026-07-01 新增 CI `pip-audit -r requirements_server.txt` 门禁（`PYTHONUTF8=1`），与 `bandit` 合并到 `Security scan` 步骤。
- **仍未修复的告警**：
  - GitHub push 后仍提示 default branch 有 16 个漏洞（7 high, 9 moderate）。本地可扫描的 manifests 已全部 clean，剩余可能来源：
    - GitHub Dependabot 计数存在延迟/缓存。
    - `esp32S_XYZ` 子模块中其他未扫描的旧 npm/pnpm/Dockerfile manifests（如 `u1-grbl/embedded` 仍有 33 个高危/严重级漏洞，`xiaozhi-esp32-server/main/manager-mobile` 因私有 registry 无法 audit）。
    - Dockerfile 固定 digest 后仍可能存在 Debian 系统级未修补 CVE。
- **风险与后续**：
  - Pillow 大版本 10→12 已确认通过全部图像处理测试；生产部署后需观察 `xiaozhi_drawing/svg_converter.py` 与 `device_logic/captcha.py` 行为。
  - pip 大版本 23→26 仅影响包安装流程，未引入运行时变更。
  - ~~建议后续在 CI 中加入 `pip-audit --requirement requirements_server.txt` 门禁。~~ ✅ 已完成（2026-07-01）：`.github/workflows/test.yml` 新增 `pip-audit -r requirements_server.txt` 步骤，环境变量 `PYTHONUTF8=1` 规避 Windows 编码问题。
  - 子模块中遗留的旧前端构建链（gulp/cheerio/underscore 等）如需继续修复，涉及直接依赖大版本升级，可能破坏 ESP32 固件构建流程，需单独评估。


## 2026-07-02 external_enrichment provider 占位状态确认

- `external_enrichment/providers/nager_date.py` 与 `open_meteo.py` 方法体仅返回硬编码 mock（`# TODO: Actual API call would go here`）。
- 确认：两文件被 `tests/test_external_enrichment.py` 明确用作离线测试 mock（docstring 标注 "offline tests with mock"）。
- 结论：保留，不为瘦身删除测试依赖。真实 API 接入留待功能驱动时再做（YAGNI）。

## 2026-07-02 CodeGraph 死函数复审（13 个候选）

> 候选来自瘦身审查「疑似 0 调用点函数」清单。用 CodeGraph `edges.target` fan-in + 全库 grep 双重确认。

### 删除（12 个，CodeGraph fan-in=0 且 grep 全库无调用点、无装饰器、无同文件引用）

| 文件:行 | 函数 | 说明 |
|---------|------|------|
| token_health.py:110 | `alert_expired_tokens` | 疑似未接 cron，无调用方 |
| model_registry.py:108 | `get_active` | 与 key_pool.get_active_count 名字近但无关联 |
| backends_registry/__init__.py:85 | `get_backend` | 与 health_state.get_backend_* 名字近但无关联 |
| device_gateway/mqtt_client.py:34 | `is_mqtt_enabled` | 调用方直接读 DEVICE.mqtt_enabled |
| device_gateway/mqtt_client.py:46 | `mqtt_send_to_device` | async 投递函数，无调用方 |
| context_pipeline/cache.py:74 | `build_cached_prompt` | 仅改 _metrics 统计，无调用方 |
| route_scorer.py:97 | `task_fit_score` | 编码退役后纯函数无调用方 |
| user_identity/lessons.py:66 | `apply_lesson` | 有文件写副作用但无任何调用方 |
| context_compressor.py:165 | `estimate_context_usage` | 纯计算，无调用方 |
| session_memory/compactor.py:121 | `llm_summarizer_factory` | 工厂函数，无注入式调用方 |
| channel_retirement.py:17 | `is_retired_route_path` | 纯函数，无调用方 |
| key_pool.py:251 | `provider_snapshot` | 委托 pool_snapshot，无调用方（与 provider_automation/snapshot_store 模块名近但无关联） |

### 保留（1 个）

| 文件:行 | 函数 | 保留原因 |
|---------|------|----------|
| observability/prometheus_metrics.py:199 | `record_backend_error` | 有测试覆盖（test_observability_metrics.py:90），疑似预留 prometheus 调度入口，YAGNI 保守保留 |

### 验证
- ruff check 11 个文件 clean
- check_code_size PASS
- 聚焦测试 64 passed（test_token_health/test_model_registry/test_backend_registry/test_route_scorer/test_channel_retirement/test_key_pool）

---

## 2026-07-06：固件 U8 plotter MCP 工具 + 小程序 v3.9.0 + MCP 部署脚本

### 固件端发现

1. **Token 存储方案**：U8 固件原本无 DLC API token 存储机制。采用 NVS（Non-Volatile Storage）存储 `dlc_api_token`，通过 `GetDlcApiToken()` 统一读取（SEC-007）。配网时由小程序下发写入。
2. **HTTPS 强制**：ESP32 HTTPClient 默认不校验证书。新增 `https://` scheme 检查，非 HTTPS 直接返回错误（SEC-007）。
3. **响应大小限制**：dlc_api 返回的路径 JSON 可能非常大（复杂图画）。新增 `DLC_API_MAX_RESPONSE_BYTES=131072`（128KB）硬限制，防止 OOM（SEC-005）。
4. **SoftAP SSID 统一**：原 SSID 前缀 `Xiaozhi` 与 DLC 产品定位不符，统一为 `DLC`。BluFi 设备名同步改为 `DLC-Blufi`。
5. **MCP 工具注册位置**：`write_text` / `draw_generated` 注册在 `self.plotter` 命名空间下，与小智云 MCP tool schema 对齐（`plotter.write_text` / `plotter.draw_generated`）。
6. **路径执行防呆**：设备端调 dlc_api `/dlc/tasks/preview` 仅获取路径数据，不触发服务端 dispatch。路径通过 `RunPathWithTaskId` 本地执行，task_id 用于状态追踪。

### 小程序端发现

1. **chat 页面删除范围**：需同步删除 `pages.json` 中的路由注册、`useHomeNavigation.ts` 中的 `goChat`/`goDigitalHuman` 导航函数、`index.vue` 中的 AI 对话/数字人卡片组件。遗漏任何一处都会导致编译错误。
2. **`getChatBaseUrl` 简化**：原函数含 `aliyun.donglicao.com` 分流逻辑，DLC 定位下对话统一走小智云，分流逻辑已删除。
3. **配网主路径**：SoftAP 配网更适合 DLC 场景（用户现场无路由器时可直接连设备配网），作为主路径。BluFi 保留为备选。
4. **版本号递增**：3.8.7 → 3.9.0（minor bump，因功能变更：删除对话 + 配网重构）。

### MCP 部署发现

1. **模式 A（官方云直连）为首选**：小智官方云提供原生 MCP endpoint `wss://api.xiaozhi.me/mcp/?token=<JWT>`，无需自建 mcp-endpoint-server。`dlc_mcp/mcp_pipe.py` 以 WebSocket 客户端身份连入。
2. **systemd 服务依赖**：`dlc-mcp.service` 依赖 `dlc-drawing.service`（After=），确保 dlc_api 先启动。
3. **环境变量**：`MCP_ENDPOINT`（WebSocket URL）和 `DLC_API_URL`（内部 HTTP 地址）必须在 `.env` 中配置。已在 `.env.example` 中补入。

### 待验证项

- [ ] 小智云控制台获取 MCP endpoint token
- [ ] VPS `.env` 配置 `MCP_ENDPOINT`
- [ ] `install_dlc_mcp.sh` 在 VPS 上执行
- [ ] 设备端 NVS token 写入流程验证（配网时小程序下发）
- [ ] 端到端：语音 → 小智云 → MCP → dlc_api → 路径生成 → 设备执行

## 2026-07-06 阶段D 前置验证：发现 3 个切流阻塞（诚实 block）

- **现象**：准备把 nginx 生产流量从旧 `:8080` 切到瘦身版 `server_dlc:8081` 前，逐一验证小程序 v3.9.0 所需端点，发现 3 个问题，全部会在切流时断掉小程序，故 STOP 未切。
- **阻塞 1（缺失端点，🔴 硬阻塞，需产品决策）**：小程序活跃页面 `ai-draw.vue`（AI 绘图）调 `/device/v1/app/images/generations`，`useVoiceStream.ts`（语音）调 `/device/v1/app/voice/ticket` + `/voice/transcribe`。提供这些的 `routes/device_app_images.py`、`device_app_voice.py`、`device_app_chat.py` **在 P4/P5 瘦身（commit 89f59be7 / 992afa0f）时已被删除**，当前仓库无实现。这些端点现由 VPS 旧 `:8080` 系统承载；一旦切流到 `:8081` 会 404。**决策点**：这三个功能（AI 绘图 / 语音 ticket / 语音转写）是保留还是废弃？保留则需从旧系统恢复/重写这三个模块并注册进 server_dlc；废弃则需先改小程序移除对应页面再切流。
- **阻塞 2（双前缀 bug，我引入，可自修）**：阶段A 聚合器 `dlc_api/device_app_router.py` 把 `device_app_api.router` 顶层注册，而 `device_app_api.py:255` 又 `include_router(device_app_sharing)`——两者都带 `prefix="/device/v1/app"`，导致 sharing 路由变成 `/device/v1/app/device/v1/app/devices/{id}/share`（前缀叠加）。根因：`device_app_sharing` 被父 include 时已自带完整 prefix，不应再有自己的 prefix，或聚合器不应重复。**修复方向**：改 sharing router 去掉自带 prefix（因它总是被 include 到已有 prefix 的父下），或在 device_app_api include 时不传 prefix。需单独 TDD 修复。
- **阻塞 3（VPS 代码陈旧）**：两节点 `:8081` 跑的是旧 server_dlc（无 device_app 注册，`dlc_api/device_app_router.py` MISSING）。阶段A/B/C 的仓库变更尚未部署到 VPS。切流前必须先 `deploy_unified.py` 推送新代码并重启 `dlc-drawing`，验证 `:8081` 健康。
- **根因（共性）**：P4/P5 瘦身"删旧系统模块"时，把小程序仍在用的 `device_app_images/voice/chat` 当死代码删了，但小程序前端并未同步移除这些调用——前后端瘦身不同步。这也是"瘦身不彻底/不一致"的一个具体实例。
- **预防**：删除任何 `device_app_*`/对外 API 模块前，必须 grep 小程序 `manager-mobile/src` 的真实 HTTP 调用（不是 `@/api` 源码别名）确认无引用；切流生产入口前必须端点级 diff（旧 `:8080` openapi vs 新 `:8081` openapi）而非仅路由计数。

## 2026-07-05 Aliyun pilot 免费 chat 链路退役（入站流量为 0）

- **现象**：Aliyun `lima-router-pilot.service`(:8080) + 6 个后端 sidecar（mimo/longcat/kimi/hermes/tts）常年运行，占 `/opt/lima-router-pilot` 1.1G，但疑似无真实用户。
- **复现/取证**：过去 24h 全部 nginx access log 中 `POST /v1/chat/completions` 入站命中 = **0**；pilot uvicorn 入站 access 行（journal last 3000）= **0**；pilot access log 唯一非监控客户端 IP 是 `117.72.118.95`（JDCloud 主节点自己）；established 连接到 :8080 为空。pilot 出站 chat/completions 787 条全是 `backend_probe_loop` 探测（大量 401/dead）。
- **根因**：前端匿名 chat 分流早已名存实亡——CF Worker `lima-chat-router` 曾把匿名 chat 转 pilot，但 (1) manager-mobile v3.9.0 已删 aliyun 分流；(2) JDCloud 主节点 `/v1/chat/completions` 本身已随瘦身退役（现返回 410 Gone）。pilot 在无人使用的情况下 24h 空转探测失效后端。
- **修复**：先切前端引用后停后端。① CF Worker 移除 pilot 分支（恒回源 JDCloud）；② `wrangler.toml` 删 `PILOT_ORIGIN`；③ chat-web `app-config.js` `shouldUsePilot` 恒 false；④ 官网 playground `selectBaseUrl` 恒主节点。经 GitHub Actions 部署（Worker/Pages/Next.js 三条 workflow success）。验证 `chat.donglicao.com/v1/chat/completions` 响应头 `X-Lima-Backend: jdcloud`（不再 aliyun）。随后 Aliyun 停 pilot + 6 sidecar，unit 改名 `.retired-20260705`（可逆），:8080 端口释放。
- **如何预防**：退役前先做入站流量取证（access log + established conns + journal），用数据而非推测判断服务死活；停服用 unit 改名而非 rm，保留可逆回滚。
- **连带修复的既存 CI 债**：① `deploy-chat-web.yml` 缺 `npm install`（自 7-03 连续 4 次失败，esbuild ERR_MODULE_NOT_FOUND）；② `test.yml` pyright 仍引用已删的 `server.py`/`routing_engine/__init__.py`/`routes/chat_endpoints.py`（改为 `server_dlc.py`）。
- **未做**：`/opt/lima-router-pilot`（1.1G）目录仅停服未删；彻底删除属独立任务。


## 2026-07-07 GitHub 同类项目对照审查：核查结论与 P1 修复

- **背景**：参考 GitHub 上类似 AI 路由/MCP 服务端项目做一次项目级代码审查，初版列出 4 个发现；逐条核查后纠正前提。
- **P0 SSRF（draw_from_image 裸 fetch）— 误报，已防护**：初查怀疑 `svg_converter._download_image` 裸 `httpx.get(image_url)` 无内网过滤。核查发现：(1) `svg_converter.py` 在当前仓库**不存在**（审查时引用了幻觉/旧路径）；(2) 真实入口 `dlc_api/routes.py:_validate_image_url`（line 102）已实现三层防护——① 字面私有/loopback/link-local IP 拦截（`_is_private_ip`），② `ALLOWED_IMAGE_HOSTS = {api.telegram.org}` 白名单，③ `_resolve_hostname` DNS rebinding 防护（解析到私有 IP 即拒）；(3) 在 `/dlc/tasks/preview` 与 `/dlc/tasks/dispatch` 两入口的 `draw_from_image` 分支都调用该校验；(4) `tests/test_sec04_ssrf_hardening.py` 5 passed（DNS rebinding、白名单、字面私有 IP、localhost 全覆盖）。**结论：SSRF 防护已完整且正确，无需修改。**
- **P1 /docs 暴露 — 真实，已修**：`server_dlc.py:25` 与 `dlc_api/app.py:9` 的 `FastAPI(title=...)` 未设 `docs_url/redoc_url/openapi_url=None`，公网入口暴露交互文档，可被枚举 API surface。`tests/test_server_docs_disabled.py` 早期删除后无回归保护。**修复**：两处 `FastAPI(...)` 显式 `docs_url=None, redoc_url=None, openapi_url=None`；新增 `tests/test_p1_security_hardening.py` 断言两个 app 的三个 URL 均为 None。
- **P1 MCP 异常泄露内网 — 真实，已修**：`dlc_mcp/server.py` 的 `_submit`(line 94)/`_get_json`(line 109) 把 httpx 异常原样拼进返回 `error` 字段，含 `127.0.0.1:8081`，对外暴露内网拓扑。MCP endpoint 经小智云可达外部。**修复**：4 处 `f"...{exc}"` 改为通用文案（"dlc_api unreachable" / "invalid response from dlc_api"），详细 `exc` 仅 `logger.warning` 不返回；新增 2 个测试 mock `httpx.ConnectError` 断言返回文案不含 `127.0.0.1`/`8081`。
- **P2 MCP 子进程 5s 终止窗口 — 误报**：初查引用 `mcp_pipe._run_session` finally 的 `terminate→wait(5s)→kill`。核查发现 `mcp_pipe.py` 当前仓库**不存在该函数**（审查引用了已删/幻觉路径）。MCP 子进程由 systemd 管理，无硬编码终止窗口。无需修改。
- **核查通过的既存项**：SQL 注入（全参数化/ORM）、IDOR（account_id 作用域）、静默降级（生产路径无 `except: pass`）、secret 日志（无明文 token 落日志）。
- **教训**：审查时引用的文件名/行号必须先 `Read` 确认存在，不能凭记忆/旧快照下结论；本次 P0/P2 两个误报都源于引用了不存在的符号。修正流程：先 `grep` 定位真实符号 → `Read` 全文 → 跑既有测试 → 再下结论。\r
\r
### 补充纠正（2026-07-07 部署后公网验证）\r
\r
- **现象**：部署修复后，`https://chat.donglicao.com/docs` 仍返回 200。\r
- **核查**：(1) 上游 `curl 127.0.0.1:8081/docs` → 404（FastAPI docs 已正确关闭）；(2) nginx `location /` 是 `try_files $uri $uri/ /index.html`（SPA catch-all），任何未知路径都 fallback 到前端 `index.html` 返回 200。\r
- **结论**：公网 `/docs` 的 200 **不是** FastAPI 交互文档暴露（响应体是前端 SPA HTML，不是 Swagger UI），是 SPA 路由的正常行为。FastAPI 层的 docs 关闭仍然有价值——防御纵深，即使 nginx 配置变更或直连上游也无法访问交互文档。本次修复有效，但"公网暴露 API surface"的风险评级从 P1 下调为"非漏洞 + 防御纵深保留"。\r
- **无需额外动作**：SPA fallback 行为是前端路由设计，不应改。\r
\r
## 2026-07-07 项目级代码审查（参考 GitHub 同类项目）：4 视角并行 + 修复 Top5\r
\r
- **方法**：4 个 explore subagent 并行从「安全/并发可靠性/边界健壮性/可维护性」4 视角审查核心生产代码（dlc_api/dlc_core/dlc_mcp/device_gateway/routes），参考 OWASP、FastAPI 官方安全建议、asyncio 陷阱、Redis 队列最佳实践。收敛去重后逐条 `Read`/`grep` 核查真实性（吸取上次 SSRF 误报教训），修复 Top5。\r
- **P0 #1 DashScope 同步阻塞事件循环（3 视角独立发现）— 真实，已修**：`device_draw_handler.py:85` 与 `routes/images_backends.py:272` 在 `async def` 内裸调 `client.generate()`（`ImageSynthesis.call` 同步 HTTP，5-30s），会卡死整个 asyncio 事件循环，期间所有设备 WS 心跳/健康检查/其他请求全停摆。DashScope 一次慢响应 = 全站假死。`asyncio.wait_for` 对同步阻塞无效（无法中断）。**修复**：两处改 `await asyncio.to_thread(client.generate, ...)`，同步调用丢线程池，事件循环不再被占。\r
- **P1 #3 Redis 客户端无 socket_timeout — 真实，已修**：`redis_store_helpers.py:33` `Redis.from_url(redis_url, decode_responses=True)` 未设超时（redis-py 默认 `socket_timeout=None` 无限阻塞）。Redis 慢响应/断连/主从切换时同步调用挂住几十秒，叠加 P0 #1 时全站卡死无 fail-fast。**修复**：加 `socket_timeout=2.0, socket_connect_timeout=2.0, health_check_interval=30, retry_on_timeout=True`。\r
- **P1 #5 MCP 畸形 JSON 崩主循环 — 真实，已修**：`dlc_mcp/server.py:247` `handle_request` 在 `try` 外，合法 JSON 但非对象（`["list"]`/`"str"`）时 `req.get` 抛 `AttributeError` → 整个 stdio 主循环退出 → mcp_pipe 频繁重连，MCP 工具持续不可用。**修复**：`handle_request` 入口加 `isinstance(req, dict)` 校验返回 -32600；`main()` 把 `handle_request` 纳入 try，异常返回 -32603 不退出主循环。\r
- **P2 #4 routes.py 重复定义（3 视角发现）— 真实，已修**：`_quota_for`（`:45`/`:141`）与 `_claim_idempotency_key`（`:50`/`:148`）各定义两次，后者覆盖前者；常量 `_TASK_QUOTA_PER_MIN=30`/`_IMAGE_TASK_QUOTA_PER_MIN=6`/`_IDEMPOTENCY_TTL=600` 因此全部失效（实际生效的是 `DEVICE.dlc_*_per_min` 配置）。合并冲突未解干净的典型残留。**修复**：删除第一组（常量+两个函数），保留实际生效的配置版。\r
- **核查确认的真实但未修（P2，记入待办，避免本次范围蔓延）**：\r
  - async 端点全表 `hgetall` + 同步 SQLite/Redis 未下线程池（`redis_store.py:80,102`、`device_app_tasks.py:180`、`dispatch.py:26`）——需加 per-device 索引 + to_thread，改动面大，独立任务。\r
  - CAS 重试耗尽静默丢弃（`redis_store_helpers.py:189`）+ recover 的 lrem/lpush 非原子——可能导致绘图机重复执行或任务丢失，需 Lua 脚本原子化。\r
  - 幂等键先占位后执行，dispatch 失败后同 key 重试被判 duplicate——违反幂等语义，需失败回滚 key。\r
  - 应用层无 body size 上限（`server_dlc.py` 未挂中间件）——依赖 nginx 兜底，建议恢复最小 ASGI body limit。\r
  - `path_validator` 无类型校验/点数上限，非数值坐标触发 500。\r
- **误报排除（参考上次教训，每条先核查再下结论）**：SQL 注入全参数化、IDOR 按 owner/account 收紧、SSRF 三层防护完整、Redis 用 JSON 非 pickle（无反序列化 RCE）、`record_simplification` 路径拼接（device_id 经正则校验禁 `/`，不可利用）、`auth.py` 空 token 兜底（已显式标注 CRITICAL 默认关闭）。\r
- **测试**：新增 `tests/test_hidden_issues_review.py`（6 用例，静态+行为双校验），全量 1373 passed（含新测试 + 既有回归），ruff/CI gate/check_code_size 全过。

## 2026-07-06 P2 技术债处理（幂等键回滚 + recover 原子化 + CAS 核查降级）

- **背景**：项目级审查记录的 3 项 P2 技术债，逐条建立证据链后处理。参考同类 FastAPI + Redis 队列项目的幂等/原子化惯例，复用仓库已有 `device_gateway/redis_cas.py` 的 Lua `register_script` 模式。
- **P2-a 幂等键先占位后执行 — 已修**：`dlc_api/routes.py::dispatch_task_endpoint` 在 `_build_dispatch_payload` / `dispatch_task` 之前就 `SET NX EX` 占用幂等键，一旦 payload 构建或下发失败（设备离线、路径生成异常、dispatch rejected），key 已被消费，客户端用同一 `Idempotency-Key` 重试会被判 `duplicate`，命令永久丢失。**修复**：新增 `release_idempotency_key`（Redis DEL，best-effort，失败靠 TTL 兜底），在三条失败路径（result 非 success / motion_task None / dispatch status 不在 `{sent,queued}`）释放 key；成功路径保留 key 维持去重语义。新增 `tests/test_p2_idempotency_rollback.py`（失败释放可重试 + 成功保留判重双向覆盖）。
- **P2-c recover 的 LREM+LPUSH 非原子 — 已修**：`device_gateway/redis_store_recover.py::recover_stale_processing` 原先先 `lrem(proc)` 再 `lpush(pending)`，两步之间崩溃会导致任务既不在 processing 也不在 pending，永久丢失（at-most-once）。**修复**：在 `redis_cas.py` 新增 `requeue_item_atomic`（Lua 单次 LREM+LPUSH+EXPIRE 原子化，仅当 LREM 命中才 LPUSH，避免与并发 pop 竞争误删兄弟副本后重复入队；带 fallback 供无 `register_script` 的测试 fake）。新增 `tests/test_p2_recover_atomic.py`（命中迁移 + 未命中不 LPUSH + recover 回归）。
- **P2-b CAS 重试耗尽静默丢弃 — 核查降级，不改**：审查怀疑 `_cas_update` 耗尽 3 次重试返回 None 时，`ack_processing` 未清 `processing_started_at` 会被 recover 误判 stale 重新入队 → 绘图机重复执行。**核查发现**：`ack_processing` 经 `_remove_processing_task` 先 `lrem` 把 item 从 processing **队列 list** 移除，之后才 `_cas_update` 改 state hash；而 `recover_stale_processing` 遍历的是 processing **队列 list**（`lrange`），item 已不在其中，recover 扫不到 → **不会重复入队，无物理重复执行风险**。CAS 失败的真实影响仅是 state hash 元数据字段（`processing_started_at`/status/retry_count）不同步，且耗尽时已有 `_log.warning`（符合禁止静默降级）。全面改 8 个调用方返回值语义波及大、收益低。**结论：队列正确性不依赖 CAS 返回值，属可观测性问题非安全问题，不改。**
- **P2-d 全表 hgetall — 记入待办不做**：`redis_store.py` 的 `active_tasks_for_device`/`list_tasks_for_device` 全表 `hgetall` + Python 过滤，O(N) 扫描。属纯性能优化，需在所有写入点维护 per-device 反向索引 + 现有数据迁移，改动面最大、回归风险高；当前设备量下 O(N) 可接受，规模到了再做。
- **文件行数约束**：`dlc_api/routes.py` 加 `release_idempotency_key` 后达 322 行超 300 硬限，把幂等键逻辑（client 单例 + claim/release）抽到新模块 `dlc_api/idempotency.py`，routes.py 降到 254 行；routes.py 用 `import as _claim_idempotency_key/_release_idempotency_key` 别名保持既有测试 patch 目标稳定。
- **测试**：全量 816 passed（含新增 2 个 P2 测试文件 + 既有回归），ruff/check_code_size 全过。
- **教训**：延续「审查高估 → 核查降级」模式——P2-b 与之前的 SSRF/子进程误报同理，审查提出的"物理重复执行"风险经证据链核查（队列 list vs state hash 的职责分离）证伪。真实修复只落在证据充分的 P2-a/P2-c。

## 2026-07-06 P2-d 全表 hgetall 优化：实测生产数据后否决

- **背景**：4视角审查提出 `active_tasks_for_device`/`list_tasks_for_device` 用 `hgetall(lima:device:tasks)` 全表扫描 + 逐条 decode，担心"任务随历史累积 → O(N) 拖垮事件循环 / Redis OOM"，建议改 per-device 反向索引。记入 P2 待办。
- **决策方法**：不凭猜测做优化，先采集 VPS 生产 Redis 真实规模（阿里云 `47.112.162.80`，`LIMA_DEVICE_REDIS_URL` 生产确用 Redis backend，非 memory）。
- **实测数据（2026-07-06）**：
  - 阿里云 `HLEN lima:device:tasks` = **19 字段**，hash 内存 **24280 bytes（约 24KB）**。
  - 京东云 tasks hash = 1 字段。
  - 无 processing/pending 队列堆积；整库 `dbsize` = 2 个 key。
- **结论：否决 P2-d，不做**。19 字段的 hgetall + decode 是微秒级，per-device 索引在此规模是典型过早优化，违背 Ponytail 第一原则（不做投机性优化 / YAGNI）。审查的"O(N) 拖垮"前提在真实生产不成立。
- **重新评估触发条件**：仅当 `HLEN lima:device:tasks` 增长到数千字段量级（可作为运维监控指标）时，才作为独立性能任务重启。届时优先考虑：终态任务字段的后台 reaper（`hscan`+`hdel`）或活跃任务有序集合索引，而非一次性大重构。
- **附带修正**：redis_task_ttl 默认 30 天 + 每次写刷新整键 TTL 的"永不过期"隐患（审查 P1-1 提及）在当前 19 字段规模无实际影响，同样待规模增长后再评估。

## 2026-07-06 S10 幂等去重：Redis 不可用时的 fail-open vs fail-closed 决策

- **背景**：Cursor 第三方复审提出，Redis 不可用时当前 fail-open（放行）可能导致 ESP32 物理设备重复画/写，建议改为 fail-closed（拒绝）。该建议属于产品策略，需定夺。
- **调研方法**：参考开源项目/工程实践对 fail-open vs fail-closed 的决策框架，而非凭直觉。
  - [Stripe 幂等设计](https://stripe.com/blog/idempotency) 强调对关键操作做幂等保护，但未主张所有操作在存储不可用时都拒绝。
  - [Spring Boot REST API Idempotency-Key Guide](https://springboot-123.mizucoffee.com/en/blog/spring-boot-rest-api-idempotency-key-guide/) 明确框架："按业务影响分级——支付等关键操作 fail-closed，其他 fail-open"。
  - [Algoroq / Plexobject 十二大致命反模式](https://www.algoroq.io/blog/idempotency-distributed-systems/) 强调"金融操作永远 fail-closed"，限定在高风险/不可逆场景。
  - 工业机器人 fail-safe 原则针对人身伤害或设备损毁风险。
- **应用到本项目**：
  - 操作对象：ESP32 绘图机/写字机，消费者玩具级设备。
  - 重复执行后果：浪费纸张/耗材、轻微笔迹重叠——**可逆、低严重**。
  - 拒绝执行后果：用户语音指令被静默丢弃，设备"不响应"——**直接伤害用户体验**。
  - 现状已改善：本轮已补 L1 进程内二级屏障，Redis 挂时同 worker（单节点几乎全部流量）重复请求会被拦住，风险已从"零去重"收窄到"仅跨节点重复才漏网"。
- **决策**：**保持 fail-open + L1，不改 fail-closed**。理由与现有 `claim_idempotency_key` docstring 一致："a duplicate is less harmful than a dropped command"。消费者绘图动作的重复成本低于命令丢失的可用性损失，符合 Spring Boot 指南的"按业务影响分级"原则。
- **可配置开关（未做，可选）**：若未来进入高价值/不可撤销场景（如收费打印、雕刻机等），可通过环境变量 `IDEMPOTENCY_FAIL_CLOSED=1` 切换为 fail-closed；当前默认保持 fail-open，不增加复杂度。
- **关联修复**：本轮同步修复了 `_get_idempotency_client()` 的永久粘滞问题——首次 Redis 连接失败后加入 30s 冷却窗口，窗口过后自动重连，避免进程终身 fail-open（详见同日提交）。

## 2026-07-06 代码层加固闭环：path_validator 类型守卫 + server_dlc body 上限（findings 待办核查）

- **背景**：逐条核查设计文档/STATUS/progress/findings 里记录但未闭环的代码层待办，参考业界惯例做精确改善。
- **#1 path_validator 非数值坐标 500（findings.md:585 指摘属实）— 已修**：`dlc_core/path_validator.py::validate_path` 的 `path: list[dict[str, Any]]` schema 允许 x/y 为任意类型，传 `{"x":"abc","y":5}` 会在 `x < 0` 比较处抛 `TypeError` → 500。**修复**：加 `_is_number`（int/float 且排除 bool 子类）守卫，非数值坐标返回 error 而非抛异常；非 dict 点也拒绝；新增硬点数上限 `MAX_PATH_POINTS=5000`（超过即 error，200 仍是软 warning 阈值）。新增 `tests/test_path_validator_type_guard.py`（6 用例：非数值 x/y、bool 坐标、非 dict、硬上限、正常路径）。
- **#2 server_dlc 无 body 上限（findings.md:584 指摘属实）— 已修**：`server_dlc.py` 无任何中间件，请求体大小完全依赖 nginx `client_max_body_size 32M` 兜底；直连 :8081（内网/调试/nginx 配置漂移）则无上限。**修复**：新增 `dlc_api/middleware.py::BodySizeLimitMiddleware`（纯 ASGI，先查 Content-Length header 快速 413，无 header 时累计读取超限也拒绝），`add_body_size_limit(app, max_bytes=32*1024*1024)` 挂到 `server_dlc:app`（与 nginx 阈值对齐）。新增 `tests/test_body_size_limit.py`（3 用例：超限 413、正常放行、生产入口已挂中间件）。
- **#3 external_enrichment mock（findings.md:466）— 已过时，无需处理**：核查确认 `external_enrichment/` 目录在 P4/P5 瘦身时已物理删除（主仓库 0 git 跟踪文件，仅 `.worktrees` 旧分支副本残留）。原 TODO「真实 API 接入」的模块已不存在，记录作废。
- **U8 音频协议 bug（STATUS.md:160）— 已过时，2026-07-02 已修**：progress.md:820 标 ✅，方案 A（固件改 PCM 上下行透传，保留 MQTT/Xiaozhi 的 OPUS 路径）已实现。剩余仅「真机端到端验证」需硬件在环；且该自托管 WS 语音链在「对话走小智云」架构下已退役。
- **测试**：全量 **1396 passed / 3 skipped / 0 failed**（1387 + 6 path_validator + 3 body_size）；ruff check + format + check_code_size 全过。提交 `51ce39cf` push origin main，双节点部署（阿里云 474 uploaded / 京东云 paramiko 核实最新代码 + 重启），公网 `/health` 200。
- **教训**：延续「审查记录会过时」模式——findings 待办里 2/4 项（external_enrichment、U8）经核查已作废，真实修复只落在证据充分的 path_validator + body limit 两项。落地前先核查目录/代码现状，避免为过时记录制造投机工作（Ponytail 第一原则）。
## 2026-07-06 lima-router-pilot 彻底退役：VPS 死配置 + 前端死代码清理

- **背景**：pilot（aliyun.donglicao.com 免费 chat 分流）逻辑已于 2026-07-05 退役（shouldUsePilot 恒 false、CF Worker 分流移除），但残留死配置/死代码。本轮彻底清理。
- **VPS 侧（阿里云）**：`lima-router-pilot.service` unit 已不存在、:8080 无监听，但 nginx `aliyun-pilot.donglicao.com.conf` 仍 proxy_pass 到死端口 :8080，导致 `aliyun.donglicao.com/health` 返回 502。备份到 `/root/aliyun-pilot.donglicao.com.conf.retired-20260706` 后改名 `.retired-20260706`，`nginx -t` + reload，502 消除。主入口 `chat.donglicao.com/health` 仍 200。
- **前端侧（chat-web，commit 855e01fd）**：`app-config.js` 删除 PILOT_ORIGIN 常量 + pilot 分流辅助死函数（hasImageContent/isDefaultChatModel/getApiOrigin），shouldUsePilot 保留恒 false 仅兼容 chat-api.js 调用；`app-boot.js` 删 pilotOrigin；`index.html` CSP connect-src 移除 aliyun.donglicao.com（安全收益：收紧白名单）。chat-api.js 依赖的 PRIMARY_ORIGIN/shouldUsePilot/getApiUrl 均保留，零回归。
- **验证**：3 个 JS node --check 语法通过；hash-assets 重建 dist 无 aliyun 残留；CI Deploy Chat Web 成功（29s）；公网 app.donglicao.com CSP 已无 aliyun，chat.donglicao.com/health 200。
- **可逆性**：nginx conf 改名保留（`.retired-20260706`），前端删除的是恒不生效死代码，随时可从 git 恢复。
