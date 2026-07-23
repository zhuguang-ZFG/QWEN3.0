# 全量深度 Code Review — 2026-07-22

> 范围：329 个 Python 文件，7 组并行审查（main @ `6447fb4f`）。
> 结论：**0 CRITICAL / 15 HIGH / ~47 MEDIUM / ~67 LOW**。
> 无密钥入库、无 SQL 注入（查询均参数化 / 列名白名单），未见文件行数规则违反。
> 格式：`file:line — 严重度 — 类别` + 失败场景。

---

## HIGH（15）

### 安全 / 认证

- **`routes/device_app_auth.py:72-77` — HIGH — 认证后门**
  `LIMA_XIAOZHI_WECHAT_DEV_LOGIN=1` 且未配 appid/secret 时 `openid = f"wx:{code}"`。
  该 flag 泄漏到生产 → 任意 `code` 冒充任意微信用户，账号接管。仅 env 门禁，无运行时 prod 守卫。

- **`config/settings_core.py:242` — HIGH — 密钥 fail-open**
  `UploadConfig.token_secret = env(LIMA_UPLOAD_TOKEN_SECRET) or env(LIMA_JWT_SECRET, "")`。
  两者皆缺时密钥为 `""` → 上传 token 用公开空 key 签名，可任意伪造。与 JWT（缺密钥 fail-closed 503）不一致。

- **SSRF allowlist 绕过（两处，同根因）— HIGH — 安全**
  - `xiaozhi_drawing/image_url_validation.py:75-111`：实际取图路径 `validate_and_pin_ip`/`fetch_pinned` 只挡私网 IP，**从不调用 `allowed_image_hosts()`**。
  - `device_gateway/device_draw_handler.py:214`：仅 `len<2000 且 startswith(http/https)` 即交给 `convert_url_to_svg → fetch_pinned`，绕开 `validate_image_url` 的主机 allowlist + http opt-in。
  主机 allowlist（SEC-04）被静默架空，绘图端点变公网取图代理（私网 IP 仍挡）。

- **`deploy/path_proxy.py:215` — HIGH — 无认证网络暴露**
  `HTTPServer("0.0.0.0", port)`（8901-8908）无认证转发到固定上游，可当开放中继。应绑 loopback/Tailscale（同兄弟 worker）。

- **`device_gateway/task_events.py:121-139` — HIGH — 越权**
  `process_motion_event_core` / `record_motion_event` 不校验上报 session 的 `device_id` 是否拥有 `message["task_id"]`。
  设备 A 可为设备 B 的 task 上报 motion_event → 改 B 的状态/工作流/账本/触发通知（`ack` 的 LREM 是无害 no-op，但状态/工作流/ledger 变更全部落地）。

- **`device_gateway/auth.py:99-115` — HIGH（已知/门禁）— 认证**
  空 token + registered-device fallback。已由 `LIMA_WS_REGISTERED_DEVICE_FALLBACK=1` + prod 覆盖 + `assert_device_auth_safe_for_runtime` 拒启守护，视为可接受风险，仅提示。

### 安全（运动物理）

- **`device_policy/engine.py:85-88` — HIGH — fail-open**
  `decide` 的 profile/safety 门仅 `if profile is not None` 执行。`profile is None` 时跳过全部 workspace/`max_feed`/`max_path_points` 检查直接 `allow`。profile 加载失败的设备可获无限制运动。

- **`device_gateway/path_validator.py:19-20,79-80` — HIGH — fail-open（条件）**
  `profile=None` 时 `profile_limit_error` 返回 `None`，不做 `[0,bound]` 约束；`_axis_value_error` 允许 `[-500,500]`。
  `run_path` 负坐标或至 ±500mm 可通过服务端校验，仅靠固件兜底。负坐标低于任何真实 workspace 地板 0。

### 并发 / 一致性

- **`device_gateway/redis_store_queue.py:188-226` — HIGH — TOCTOU 双花**
  `ack_processing` 先非原子读状态再判 `recovered_at`/`dispatch_gen`。`dispatch_gen` 严格模式默认关，唯一防线 `recovered_at` 与 `recover_stale_processing` 竞态：gen-N 迟到 ack 在 recovery 标记前被读入 → 通过守卫 → 其 LREM 移除已重投的 gen N+1 条目 → 任务从 processing 消失且再不会被恢复 → 静默丢任务。

- **`device_ledger/redis_store.py:37-48` — HIGH — 一致性/持久性**
  `append_event` 的 dedup（`sadd event_ids`）与事件写（`rpush` task/device 双表）非原子（无 MULTI/pipeline）。
  崩溃于 sadd 后 rpush 前 → 事件 id 永久标记已见，重试被当重复拒绝，事件从 append-only 真源丢失；部分写 → 双投影不一致。

- **`device_workflow/orchestrator.py:202-208` — HIGH — 状态机**
  `_terminal_phase` 映射 `COMPLETED→"done"`，但 `_status_to_task_state` 做 `TaskState("done")`（枚举实为 `"completed"`，非法值）。
  → 任务永不经 `get_state`/`snapshot`/`history` 报 COMPLETED，且仍读作 IN_PROGRESS → 可被再次 advance（二次完成）。FAILED/CANCELED 往返正常，仅 COMPLETED 坏。

### 性能 / 正确性

- **`device_voice/asr.py:28-36` + `providers/registry.py:69-78` — HIGH — 性能**
  `transcribe_audio` 每次请求 `get_asr_provider()` → 新建 provider 实例。本地 FunASR/Whisper 的 `self._model` 缓存在实例上 → 每次转写从磁盘重载数 GB 模型，每请求数秒延迟 + RAM 尖峰。

- **`device_gateway/path_pipeline.py:40-68` — HIGH — 运动正确性**
  `text_to_path` 丢弃 pen-up 信息：字形用 `(None,x,y)` 编码抬笔，但函数把所有项以 `z=0`（本仓即落笔）追加，`pen_down` 局部变量算了却不写输出。
  → 每笔画间 / 每字母间的重定位移动被当作落笔线绘制，`write_text`/handwriting 输出有连接垃圾线。`device_write_handler.handle_device_write` 直接返回此 path。

---

## MEDIUM（择要，~47 条）

### 认证生命周期
- `device_logic/admin_auth.py:156-179` — admin token 无吊销 / 无 DB 复核，与 device token 共用 `LIMA_JWT_SECRET`，仅靠 `typ` 分域；typ allowlist 过宽（仅拒 `device`），非 prod 接受无 typ 令牌 → 跨域可用。
- `device_logic/activation.py:58-62` — 静态激活码 `settings.DEVICE.activation_code` 不绑 MAC，`check_activation_code` 从不校验 MAC，泄漏即全队永久激活绕过。

### 限流可绕过 / 静默降级
- `routes/request_tracking.py:100-114` — 信任 `cf-connecting-ip`/`x-real-ip`/XFF（当直连在 `TRUSTED_PROXIES`），边缘不剥离即可伪造 IP 绕过登录/注册限流或锁定受害者。`TRUSTED_PROXIES` 硬编码。
- `rate_limiter.py:59-79` — `_redis_client_failed` 首次 Redis 失败后进程内永久置真、不重试，keyed 限流静默降级为按 worker 计数（有效上限 ×worker 数）。与 `idempotency.py` 的冷却重试不一致。
- `device_logic/rate_limit.py`（整模块）— 纯进程内 RateLimiter，多 worker 下限流可 ×worker 绕过（安全用途时）。

### 枚举 / 越权暴露面
- `routes/device_app_auth_email.py:35-36` 注册 409 枚举邮箱；`:67-69` 登录短路 → timing 枚举。
- `routes/device_app_misc.py:33-61` — 转账按 phone/openid 查收件人返回 404 → 枚举注册账号；`toAccountId` 不校验存在/激活。
- `routes/device_app_provision.py:90-104` — 认证用户可触发服务端 UDP 广播扫内网（`255.255.255.255` 4 端口），无限流 → 内网侦察 + 广播洪泛 + 收集未绑定设备 SN。
- `routes/device_app_chat.py:36-48,109-141` + `device_app_members.py` — view-share 访客可读设备语音转写 / 下载原始音频 / 家庭成员与声纹元数据。确认 view 信任边界。

### 读前不限流（内存 DoS）
- `routes/device_app_gallery.py:151-154`、`device_app_voice.py:31-41`、`device_voice/asr.py:34-36` — 先 `await file.read()` 全量入内存再判大小；需确认上游 body cap。

### 路径 / 输入安全
- `device_logic/audio_store.py:62` — `str(path).startswith(str(root))` 缺分隔符前缀漏洞（`/data/x-backup` 通过 `/data/x`），且绝对 `storage_path` join 丢左操作数；应同 writer 用 `is_relative_to`。
- `xiaozhi_drawing/svg_validator.py:161-164,20` — `_is_dangerous_uri` 仅 `startswith`，`java\nscript:` 及 `data:image/svg+xml` 未挡 → 存储型 SVG 服到浏览器可执行脚本。

### SVG / 运动正确性（多为静默降级）
- `device_gateway/svg_parser.py:173-189` — 隐式重复坐标（`L x y x y`）后续点静默丢弃；`:8-25` 紧凑数字 `M10-20` / 科学计数 `1e3` 解析错并截断路径；`:134-153` 二次贝塞尔按 `C,C` 错误升阶(几何偏差)；`:87-89` 相对 `m` 后 `Z` 闭合到 (0,0) 而非子路径起点。
- `device_gateway/path_data.py:97-107` — `clamp_path` 不夹 z（违背 docstring 安全契约）；`:93` `MAX_WORKSPACE=200` 与真实 300×300 冲突，且允许负坐标至 -200 / 截断 200–300mm / NaN→200。
- `device_gateway/path_validator.py:21` vs `device_gateway/safety.py:12` — 两个同名 `validate_run_path_params`，feed 上限 2000 vs 1200 分歧,取决于调用点 import 谁。
- `device_intelligence/safety.py:33-37` — 仅 `isinstance(list)`/`isinstance(int,float)` 才校验，`feed="999"` 字符串或非 list path 静默跳过 → 超限运动过关（bool 也漏）。
- `device_memory/recall.py:52-65` — feed 偏好硬编码夹到 `[100,3000]` 而非设备 `profile.max_feed`，可返回超设备上限的 hint。

### 数据一致性 / 持久化
- `device_ledger/store.py:115-145` — `_replay_from_events` 不按 `created_at` 排序，与 `projection.rebuild_state`(排序) 对乱序事件得出不同终态。
- `device_memory/redis_store.py:28-34` — 索引集 TTL(~30d) < 条目 TTL(90/60d)，空闲设备记忆索引先过期 → recall 静默返回空。
- `device_memory/consolidation.py:80-98` — `store.create` 绕过 `quality_gates.should_learn_entry`，低于反学习阈值(0.2)仍写入。
- `config/sqlite_pool.py:91-105,138-140` — 代理 `close()`/`pool_release()` 不 commit/rollback，脏连接回池 → 跨请求状态泄漏。
- `device_gateway/family_approval_store.py:84-167` — `_connect` 无显式 commit，写入是否持久取决于 `pooled_sqlite_conn` 语义(需确认)；revoke SELECT-then-UPDATE 无事务边界。
- `device_gateway/redis_store_queue.py:34-45` — enqueue RPUSH 先于 CAS 设 `queued`，与消费者竞态致队列/状态背离。
- `device_gateway/redis_store.py:56-74` — `append_event_atomic(new_status=phase)` 直写设备上报 phase 无 allowlist → 设备可置任意生命周期状态。
- `device_gateway/redis_cas.py:89-104` — Script 缓存按 `id(client)`,GC 后 id 复用 → 指向陈旧客户端;字典不淘汰。

### 崩溃 / 资源
- `device_gateway/coordinator.py:78-83` — 空 `device_ids` → `_grid_split(bounds,0)` 除零。
- `device_gateway/sessions.py:135-152` — `remove_zombies` 在持 `self._lock` 时做同步网络 Redis 调用(requeue),Redis 慢则阻塞整个 registry / 事件循环。
- `device_voice/asr.py:36` — `wait_for` 超时取消协程但 `to_thread` 线程仍跑，慢上游耗尽线程池;`funasr_local.py`/`whisper_local.py` 惰性加载无锁 → 并发首请求重复构建模型。
- `device_voice/audio_format.py:35-50` — `wave.open` 于不可信字节，`wave.Error`/`EOFError` 非 `ValueError` 子类 → WS 上未处理异常。

### 观测 / SSRF / 泄漏
- `observability/prometheus_metrics.py:67-78` — `_ensure_instruments` 无锁,并发首用建双 registry;`:83-88` `error_type`/`reason` 若来自自由文本 → label 基数爆炸。
- `integrations/telegram_bot/client.py` — API URL 内嵌 `/bot{token}/`,`raise_for_status` 把 token 带进异常/日志;`download_file` 全 URL 直取无主机限制(SSRF)。
- `sdk/python/lima_sdk/_base.py:27` — `body.get("error",{}).get(...)` 假定 error 是 dict,`{"error":"str"}` → AttributeError 掩盖真错。
- `xiaozhi_drawing/image_url_validation.py:124` — IPv6 pin netloc 缺方括号 → urlunparse 不可解析;`:114-144` 无响应体大小上限 + `Image.open` 无 `MAX_IMAGE_PIXELS` → OOM/解压炸弹。
- `xiaozhi_drawing/path_optimizer.py:134-156` — Douglas-Peucker 无界递归,近单调长路径 → `RecursionError` 崩溃。
- `xiaozhi_drawing/pipeline.py:83-85` — `cv2.cvtColor(...RGB2GRAY)` 假定 3 通道,灰度/RGBA 常见输入报错。
- `client_keys/quota.py:105,179-187` — RPM 检查在锁外做读改写 → 竞态可超限 + deque 状态损坏(日/月计数是原子的)。
- `dashscope_image_client.py:68-79` — `generate_async` 声明 async 却直调阻塞 `ImageSynthesis.async_call`,阻塞事件循环。

---

## LOW（~67 条，择要）

- `dlc_api/routes.py:129-138` — `/health`、`/health/ready` 无认证,泄漏后端名 / Redis 健康 / reaper 状态 / 版本。
- `dlc_api/middleware.py:71-98` — `BodySizeLimitMiddleware` 流式响应先 start 后判超限则不发 413,截断响应外泄。
- `dlc_mcp/server.py:177` — `device_id` 未 URL-encode 插入路径;`mcp_pipe.py:69-75` WS 消息含 `\n` 会被子进程按行拆成多条 JSON-RPC。
- `dlc_core/device_status.py:48` — `shadow_store.snapshot` 同步调用紧跟 `to_thread` 之后,若命中 Redis 仍阻塞事件循环(部分抵消 CORE-O3)。
- `dlc_core/dispatch.py:14-22`、`device_gateway/task_recorder.py`、`device_workflow/{orchestrator,lock}.py` — 按 device_id/task_id 累积锁字典,永不淘汰,进程寿命内无界增长。
- `async_utils.py:17-34` — 单 worker ThreadPoolExecutor 桥;嵌套 `run_coro_sync` 自死锁风险 + 高并发瓶颈。
- `device_gateway/redis_store.py:35-38` — `reset` 用 `scan_iter` + `delete` 无守卫,误调清空前缀下全部设备状态。
- `device_gateway/redis_store_recover.py:52-59` — 无 state 且缺时间戳的 processing 项永不被回收,无界泄漏。
- `device_gateway/task_events.py:152-161` — `record_motion_event_side_effects` 似死代码,`task_acknowledged`/`task_progress` 账本事件可能从不触发(确认)。
- `xiaozhi_drawing/text_to_path.py:26-31` — `_glyph_advance` 吞异常返回 0.6em fallback 无日志(违反无静默降级);`:125-137` H/V 命令截断路径;`:198` 调用方 `font_path` 逐字加载 → 任意文件读原语(若路由暴露)。
- `xiaozhi_drawing/image_url_validation.py:30-35`、`device_gateway/image_url_validation.py:29-34` — `_is_private_ip` 未挡 `0.0.0.0`/unspecified 与 IPv4-mapped IPv6。
- `observability/prometheus_startup_metrics.py:54-71` — `sync_retired_backends` 置 0 但不清 labelset,churn 名累积陈旧 series。
- `sdk/python/lima_sdk/_streaming.py:28` — 未防护 `json.loads`,单条坏 SSE 行中断整个流。
- `deploy/path_proxy.py:138`、`deploy/jdcloud/pure_mysql_mig.py:151`(shell GRANT 插值 user)、`push_probe_results.py:240`(ingress 可 http 明文送 token) — 部署脚本零散加固点。
- `device_gateway/auth.py:79-85` — `_token_matches_env` compare_digest 早退泄漏长度(低价值,可接受)。
- `device_gateway/health_score.py:81-102` — `_parse_semver` 与 `parse_version` 对非数字段处理不一致(`v1.2.0-rc` → `(1,2)` vs `(1,2,0)`)。
- `device_intelligence/shadow.py:118-144` — voiceprint `audio_data` 仅判非空,无大小/base64 校验,deepcopy 入 shadow → 无界内存;`simulator.py:42-73` truthy-but-invalid path 静默模拟空 / `feed="nan"` → nan 入运行时。
- `device_artifacts/store.py:86-143` — 读路径不淘汰过期记录(仅写时 evict),可返回超保留期 artifact;无记录数上限。
- `device_logic/notifications.py:181,189` — `json.loads` 无守卫,单条坏订阅行使整批通知失败;`:66-106` WeChatNotifier token 缓存并发竞态。
- `device_logic/db_migrations.py:216-247` — email 唯一索引迁移遇存量重复邮箱 → 启动中止(响亮失败,脏数据可 brick 部署)。
- `routes/device_app_assets.py:117-131` — `get_asset` 每次 GET `UPDATE use_count+1` 无限流 → 写放大;`:100-104` LIKE `%{tag}%` 通配符语义(已参数化,无 SQLi)。
- `routes/device_app_tasks.py:183-213` — `batch_draw` 只计一次配额却 fan-out 到 N 设备;`device_ids` 无长度上限。
- `routes/device_app_voice_ws.py:238-262` — ticket 双用竞态(已在 docstring 承认),败者已起 ASR 会话。

---

## 交叉验证为安全 / 无发现（不是问题）

- SQL：`crud.py:158`、`db_migrations.py:227`、`client_keys/*`、`align_claude_beta_header.py` 均确认参数化 / 列名白名单,无注入。
- `routes/images*.py`：i2i `image_url` 经 `validate_image_url_async`(SEC-04)挡私网/非 allowlist;`/v1/images/generations` 有 `require_private_api_key`。无 SSRF。
- ticket 存储(`ws_ticket`/`device_ws_ticket`/`app_status_ws_ticket`/`voice_app_ws_ticket`)：锁 + TTL + 容量淘汰 + 单用 consume,正确。
- `server_dlc.py` lifespan fail-closed(task-store/ledger/auth 配置失败重抛)。
- `deploy/jdcloud/jdcloud_worker.py`：`hmac.compare_digest`、剥离客户端 Authorization 服务端注入 key、Content-Length 必需且限长。
- `turnstile.py` / `captcha.py`：fail-closed;captcha SHA-256 + compare_digest + 一次性。
- `client_keys/*`：128-bit token,`ClientKeyStorageError` 不吞异常。
- 文件行数(最大 `images_backends.py` 296 行)与函数长度规则未见违反;fallback 路径均有 warning 日志(除上列少数 LOW)。

---

## 建议处理顺序（生产风险优先）

1. **SSRF allowlist 绕过**(`xiaozhi_drawing/image_url_validation.py` + `device_gateway/device_draw_handler.py:214`,同根因)— 违背 SEC-04。
2. **运动安全 fail-open**(`device_policy/engine.py:85-88` + `device_gateway/path_validator.py:79-80` 的 `profile=None`)— 违反「运动安全第一」硬规则。
3. **认证 fail-open**(`config/settings_core.py:242` 空上传密钥 + `device_logic/admin_auth.py` admin token 无吊销)。
4. **越权**(`device_gateway/task_events.py:121-139` motion_event 缺 ownership)。
5. **写字画错**(`device_gateway/path_pipeline.py:40-68` pen-up 丢失)。

配置门禁类(微信 dev-login backdoor、空-token WS fallback、静态激活码)建议加运行时 prod 守卫,而非仅靠 env 约定。

数据一致性(ack 双花 / ledger 非原子 / workflow COMPLETED 态)建议在真机 E2E(P0-3)前修,避免掩盖真机丢任务。
