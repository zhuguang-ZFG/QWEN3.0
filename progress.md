# Personal Coding Assistant Progress

> 历史归档：2026-06-30 及更早条目 → [`docs/archive/progress-2026-06.md`](docs/archive/progress-2026-06.md)

## 2026-07-14 A2A 逐文件全项目审查 + P0/P1/P2 修复（123 文件）

- **审查**：Atom/Reasonix 初审 123 文件（高 150/中 281/低 289）→ Claude/Atom/Reasonix 三路交叉复核 153 项高危（确认 119/证伪 20/存疑 14）。产物：`.tmp/a2a_review/`（QUEUE/REVIEW_REPORT/findings/cross）
- **P0**（`770d82eb`）：NaN 物理防御 4 处（path_validator/safety/handwriting_params/path_optimizer）、JWT typ 隔离（device/admin 双域）、token 吊销 fail-closed（deps `_DB_UNAVAILABLE` sentinel）、calibrate→home 误映射删除、audio 路径穿越（先检后写）、SSRF pin-IP（`xiaozhi_drawing/image_url_validation.py`）。Claude 独立复核：0 阻塞 2 建议
- **P1 第 1 波**（`b7b80647`）：redis recover 双花、流式 413 中断、TOCTOU（activation/captcha/dispatch）、出网脱敏 5 处（params/error/shadow/wechat）
- **P1 第 2 波**（`68598020`）：caller_model 白名单、text 长度上限（MAX_TEXT_LENGTH=5000）、captcha 哈希存储
- **P2 第 1 波**（`c50aec75`）：测试函数移出 `__all__`+TESTING 守卫、固件版本语义化比较（`device_gateway/_version_compare.py`）、registry 电话 PII 脱敏+分页、sms DeprecationWarning、auth/store 静默降级补 warning
  - 决策：profile 层空 fw_rev 保持 fail-open+warning（老设备兼容），registry 层 `assert_firmware_compatible` 在有 fw_rev 时严格
- **门禁**：全量 1701 passed / 3 skipped；ruff + check_code_size 全过

## 2026-07-13 F5：MCP 幂等键内容寻址（跟进 a9e44bc7）

- **改动**：`dlc_mcp/server.py` 新增 `_dispatch_idem_key(endpoint, payload)` → `sha256(canonical)[:32]`；`Idempotency-Key: mcp-<32hex>`，与 JSON-RPC id 解耦
- **测试**：同 payload 不同 id 同 key；不同 payload 不同 key；金丝雀 digest；`tests/test_dlc_mcp_server.py` 16 passed
- **门禁**：ruff / format / check_code_size PASS
- **实现方**：Grok A2A（Reasonix 忙时分流）

## 2026-07-13 安全加固：batch/render 限流、voice 会话字节、approve 失败回滚、MCP 幂等头、私网 IP 不外发

- **提交**：`a9e44bc7` + docs `669be471`
- **改动**：
  - `routes/device_app_task_extras.py`：batch-tasks 按条数预扣 `device_app_task:{account_id}`（中途 429 已扣不退回，防绕过）
  - `routes/device_app_assets.py`：render-asset 同桶单次限流
  - `device_gateway/coordinator.py`：`execute_coordinated` 经 `asyncio.to_thread` 卸阻塞派发
  - `routes/device_app_voice_ws.py`：会话累计音频 `VOICE.max_audio_bytes*10`，超限 close 1009；`client_state`→`application_state`
  - `dlc_mcp/server.py`：初版 `Idempotency-Key: mcp-<req_id>`（已由 F5 内容寻址替换）
  - `routes/request_tracking.py`：`get_ip_location` 私有 IP →「内网」，非法/空 →「未知」，不外发 ip-api
  - `routes/device_app_tasks.py` + `task_store.py`：approve 后 dispatch 失败 `revert_task_to_pending` + 500
  - 测试：F1–F7 覆盖；新增 `tests/test_device_app_assets.py`；相关文件 autouse `rate_limiter.reset()`
- **门禁**：ruff 改动文件 All checks passed；定点 pytest **92 passed**
- **第三方复核（Grok A2A，只读）**：总体 **可以提交**；无必须返工硬伤
- **建议后续（非阻断）**：
  1. ~~高：MCP 幂等键勿只绑 JSON-RPC `req_id`~~ → **已修（F5）**
  2. 中：`revert` 与「已入队」语义对齐，避免稀有双投窗口
  3. 中：补 batch 预扣次数、voice close 1009 断言；sharing 测可选 reset
  4. 低：`render_asset` 压回 ≤50 行；`not is_global` 收紧 geo；status_ws 状态字段统一

## 2026-07-12 审查 MEDIUM：否决 to_thread/hgetall；固件 user_only DoToolCall 门禁

- **决策（ponytail）**：
  - **不做** async 全表 `hgetall` + 全路径 `to_thread`：findings 2026-07-06 生产实测 `HLEN lima:device:tasks≈19`、hash ~24KB，属 YAGNI；索引开关 `LIMA_REDIS_TASK_INDEX` 已存在默认关，规模到数千再开
  - **做** 固件 MCP `user_only` 执行门禁（审查 MEDIUM 真问题；上游 [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) DoToolCall 同样只 list 过滤、call 不挡）
- **改动**（子模块 `esp32S_XYZ` `cc9875a`）：
  - `ParseMessage(..., allow_user_only_tools=false)` 默认
  - `DoToolCall`：`user_only && !allow` → error `Tool requires user channel`
  - 本地控制 WS（握手已 token 鉴权）传 `true`；云端 AI 通道保持默认 `false`
- **未刷机**：需真机 OTA/烧录后生效；安装路径仍有 F1 签名门禁兜底

## 2026-07-12 审查 MEDIUM：provision 不回显 WiFi 密码 + app 任务写路径限流

- **提交**：`9a2b6be1`（已 push `origin/main`）
- **改动**：
  - `routes/device_app_provision.py`：`configPayload` 去掉 `wifi_password`；请求体仍可带 password 供客户端本地 SoftAP/BLE，服务端不存不回显
  - `routes/device_app_tasks.py`：`POST /devices/{id}/tasks` 按 `account_id` 走 `check_key_limit`（`DEVICE.dlc_task_per_min`，默认 30/min）
- **测试**：`test_device_app_provision` + `test_routes_device_app_tasks` + `test_device_app_tasks` → 28 passed；ruff / size PASS
- **双节点**：
  - jdcloud：md5 对齐，`/health` ok
  - aliyun：文件 md5 对齐；冷启动较慢（~数十秒才 listen 8081），最终 `/health` ok + `task_store=redis`
- **已决策不做 / 已闭环不重复**：health redis 503、token_epoch 吊销、voice consume_if、幂等 fail-open+L1（`9974bec4`）；async 全表 hgetall+to_thread 改面大，独立任务
- **审查债剩余**：async SQLite/Redis to_thread 热点、前端/小程序/固件历史 MEDIUM（headers/CSP、mcp user_only 等，跨仓）

## 2026-07-12 审查 HIGH：任务 approve 原子性 + busy 含 queued + free-text 审批门

- **提交**：`a5735e53`（已 push `origin/main`）
- **改动**：
  - `approve_task_row` / `reject_task_row`：条件 `UPDATE ... AND status='pending'` + `rowcount==1`，并发双 claim → 409
  - `_ACTIVE_STATUSES` 含 `queued` / `dispatching`，设备 busy 检查不再漏排队中任务
  - `create_and_route_task`：`workflow_state==waiting_approval` 时不入队，与 free-text/structured 审批对齐
  - free-text 创建后 `insert_task_row` 落 `v2_task`；`DB_TASK_SOURCES` 增加 `app→api`
- **测试**：相关 60 项 pytest 全绿；ruff check 通过
- **双节点部署**（tar-over-ssh，密钥 `jdcloud_ed25519` / `lima_deploy_ed25519`）：
  - jdcloud + aliyun：4 文件 md5 与本地一致；`/health` → `status=ok`、`task_store=redis`
- **说明**：`deploy_unified.py` 默认 `id_ed25519` 对两节点 Authentication failed，本轮绕过脚本直传；未改 deploy 配置（YAGNI）
- **审查债剩余（MEDIUM，本批不做）**：写路径限流、provision wifi 回显、async to_thread、health memory 恒 ok、幂等 Redis fail-open、JWT 24h 无吊销、voice ticket 竞态等

## 2026-07-05 阶段 D：VPS 旧系统退役 + JDCloud 标准化

- **背景**：阶段 A/B/C 完成后，新入口 `server_dlc.py` 已可承载全部生产路径（DLC + 小程序 + 图像）。但 VPS 上旧 `lima-router.service`(:8080) 仍在跑，nginx 仍把大量路径代理到它；JDCloud 还用旧目录 `/opt/lima-router` 启动 `dlc-drawing`，与 Aliyun 的 `/opt/dlc-drawing` 不一致。
- **Aliyun 旧主路由退役**：
  - 侦察发现 nginx 配置早已把 `/dlc/*` 与 `/device/*` 代理到 `:8081`，其余退役路径（`/chat/ /admin /api/ /agent/ /v1/voice /digital-human/ /fleet/`）已 `return 410`——无需改 nginx。
  - `systemctl stop + disable lima-router.service`（备份 unit 文件为 `.retired-YYYYMMDD`）；`nginx -t && reload`。
  - 退役后 `:8080` 端口被另一个独立服务 `lima-router-pilot.service`（Aliyun 辅助节点，子域名 `aliyun-pilot.donglicao.com`）接管，非本次退役目标，保留。
  - `/opt/lima-router` 目录保留：`lima-scnet-reverse.service`（SCNet 反代 sidecar，:4505，仍活跃）依赖它工作。
- **JDCloud 标准化**：
  - `deploy_unified.py --target jdcloud --slice core` 上传 485 文件到 `/opt/dlc-drawing`（首次创建该目录）。
  - 复制 `lima.db` + wal/shm 到 `/opt/dlc-drawing/data/`；`.env` 由 `_prepare_service` 自动从 `/opt/lima-router/.env` 复制（仅当目标不存在时）。
  - 复制 `/opt/lima-router/.venv`（513M，含 dashscope/fastapi/uvicorn 等已装包）到 `/opt/dlc-drawing/.venv`。
- **Aliyun venv 补齐**：
  - Aliyun 原用 `/usr/local/bin/uvicorn`（指向 `/usr/local/bin/python3.10`，dashscope 装在系统 site-packages），但 JDCloud 无 `/usr/local/bin/python3.10`，两节点 Python 环境结构不同。
  - 解决：`/usr/local/bin/python3.10 -m venv --system-site-packages /opt/dlc-drawing/.venv`（继承系统包），两节点统一用 `/opt/dlc-drawing/.venv/bin/python -m uvicorn`。
  - `deploy/aliyun/dlc-drawing.service` 的 `ExecStart` 从 `/usr/local/bin/uvicorn` 改为 `/opt/dlc-drawing/.venv/bin/python -m uvicorn`，让两节点共享同一份 unit 文件。
- **端到端冒烟验证**：
  - `:8081/health` 两节点 → `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`。
  - `POST :8081/v1/images/generations`（真实 `LIMA_API_KEY`）两节点 → HTTP 200，返回 Agnes/Pollinations 图片 URL。
  - `POST :8081/device/v1/app/images/generations`（VPS 自身 `.env` 的 `LIMA_JWT_SECRET` + 数据库 active 账号 id 签 JWT）Aliyun 本地 → HTTP 200，返回图片 URL + `backend:"LiMa 生图"`；`device_logic.auth.authorize()` 直调诊断确认 secret 一致（28 字节，`xiaozhi-prod-secret-key-2026`）、账号 `fdb6a72b-...` active。
  - 公网 `https://chat.donglicao.com/health`（本地发起）→ 200 dlc-drawing，确认 nginx→:8081 链路通；VPS 自访问公网域名被 Cloudflare 拦截（1010），非服务问题。

## 2026-07-05 图像生成路由恢复完善：/v1/images/generations + /device/v1/app/images/generations

- **背景**：P4/P5 系统瘦身时旧 `server.py` 退役，`/v1/images/generations` 与小程序 `/device/v1/app/images/generations` 随旧入口一起丢失。Chat Web、SDK、小程序 AI 绘图功能依赖这两个端点，需在新入口 `server_dlc.py` 下恢复。
- **恢复的文件**：
  - `routes/images.py`：OpenAI-compatible `/v1/images/generations`，主后端 xmiaom `gpt-image-2`，降级链 Agnes → SiliconFlow → Zhipu → Baidu → Tencent → Volcengine → FreeTheAi，最终兜底 Pollinations.ai。
  - `routes/images_backends.py`：各后端具体实现；**替换已删除的 `http_async.call_raw_async` 为直接 httpx 调用 `https://ai.xmiaom.com/v1/chat/completions`**，避免运行时 `ImportError`。
  - `routes/images_cache.py`：进程内生图缓存（TTL + 最大条目驱逐）。
  - `routes/images_pollinations.py`：Pollinations.ai URL builder + 中文 prompt 翻译兜底。
  - `routes/device_app_images.py`：小程序认证版 `/device/v1/app/images/generations`，对外统一返回品牌标签 `LiMa 生图`。
- **注册与测试**：
  - `server_dlc.py` 显式 `app.include_router(images_router.router)`，恢复公网 `/v1/images/generations`。
  - `dlc_api/device_app_router.py` 已注册 `device_app_images`（阶段 A 工作），本次补测试覆盖。
  - 新增 `tests/test_routes_images.py`：11 个用例覆盖公网端点成功/鉴权失败/参数校验/缓存命中、小程序端点成功/鉴权失败/空 prompt、`server_dlc` 路由暴露断言。
  - 更新 `tests/device_app_helpers.py`：把已恢复的 `device_app_images` 路由重新 include 进测试 app。
- **门禁**：pytest **1408 passed / 3 skipped / 0 failed**；ruff check + format clean；pyright 改动文件 0 errors；`check_code_size.py` PASS。
- **VPS 部署与冒烟（选项 A）**：
  - 修复 `scripts/deploy_unified_restart.py`：把 `lima-router`（旧 :8080）改为 `dlc-drawing`（新 :8081），健康检查从 `:8080/health/ready` 改为 `:8081/health`。
  - 修复 `scripts/deploy_unified_preflight.py`：容量检查前自动 `mkdir -p` 新目录。
  - 修复 `config/deploy_config.py`：`REMOTE_PATH` 默认改为 `/opt/dlc-drawing`，`router_root()` 同步指向新目录。
  - 修复 `scripts/deploy_unified_common.py`：从 `CORE_DIRS` 删除已物理删除的 `device_ota`。
  - 新增 `deploy/aliyun/dlc-drawing.service`：独立 `WorkingDirectory=/opt/dlc-drawing` + `EnvironmentFile=/opt/dlc-drawing/.env`。
  - 更新 `tests/test_deploy_unified.py`、`tests/_deploy_mocks.py` 以匹配新目标目录/服务名。
  - 首次部署到 Aliyun `47.112.162.80` 的 `/opt/dlc-drawing`，485 文件上传成功，`dlc-drawing` 重启后 `/health` 返回 `{"status":"ok","service":"dlc-drawing"}`。
  - 真实 key 冒烟：
    - `POST :8081/v1/images/generations` → HTTP 200，返回 Agnes 图片 URL（xmiaom 未命中时自动降级）。
    - `POST :8081/device/v1/app/images/generations`（用 VPS `.env` 中真实 `LIMA_JWT_SECRET` 签发的测试账号 JWT）→ HTTP 200，返回图片 URL + `backend: "LiMa 生图"`。
  - 备注：VPS 上旧 `lima-router`(:8080) 仍在运行（nginx 尚未切流），但新 `dlc-drawing`(:8081) 已在独立目录跑最新代码并承载图像端点。

## 2026-07-06 系统瘦身彻底化 A/B/C：补注册小程序路由 + 删死代码 + 清死配置

- **背景**：调查确认"瘦身声称完成但未彻底"——Strangler Fig 只"建新入口"（`server_dlc`），从未"退役旧系统"。VPS 上旧 `server:app`(:8080) 仍是生产主处理器；仓库里大量模块因旧入口（`server.py`/`route_registry.py` 已删）失去可达性但从未物理删除。实测应用 py 规模 294 文件 / 34,983 行（旧 STATUS 记录「280/18000」失真，已更正）。
- **可达性方法**：从 `server_dlc.py` 出发做 AST 全导入闭包遍历（含函数体内惰性 import），逐一裁决活/死/补注册，跳过 `.worktrees`/`tests`。
- **阶段 A（`040d72bb`）补注册小程序路由**：`device_app_*` 从 `server_dlc` 静态不可达，但微信小程序 v3.9.0 在用（当前靠旧 :8080）——是漏注册而非死代码。新建 `dlc_api/device_app_router.py` 聚合器，`register_device_app_routes()` 显式 include 15 个顶层 router。`server_dlc` 现注册 ~127 条路由（5 DLC + ~70 device_app + 子路由）。新增 `tests/test_dlc_device_app_router.py` 护栏。
- **阶段 B+C（`078d49be`）删死代码 + 死配置**：
  - WS 语音网关链（8）：`device_gateway_ws*`、`device_gateway.py`、`device_gateway_hello_helpers`、`device_gateway_query_routes`、`device_gateway_events_routes`（保留 `device_gateway_dispatch.py`——经 `dlc_core.dispatch` 可达）。
  - OTA 链：`routes/device_ota*`(3) + `device_ota/` 包(8)。
  - 旧中间件/WS 工具：`request_id_middleware`、`security_headers`、`stream_handlers`、`upload_tokens`、`ws_common`、`ws_lifecycle_helpers`、`ws_task_helpers`、`async_compat`、`client_keys_store`、`device_admin`、`device_timeline_routes`、`handwriting`。
  - 连带删 20 个仅测死模块的测试 + `tests/conftest.py` 引用已删 `device_gateway_hello_helpers` 的 autouse attestation fixture。
  - 死配置：`ObservabilityConfig.structured_logging` + 4×`routing_guard_*`；`node_role.py` 的 `alert_evaluator_enabled()`/`structured_logging_enabled()`；`tests/_env_sync_observability_maps.py` 对应映射；删死测试 `test_observability_structured_logging.py`。
  - 死部署脚本 `deploy/deploy_prometheus_metrics.py`（引用已删 `prometheus_exporter`）；`deploy_unified` 的 `SLICE_FILES` phase_a/phase_b（引用已删 `routing_engine`/`context_pipeline`）+ argparse choices。
  - 门禁配置修复：`.tmp` 加入 `.gitignore` + ruff exclude；清理悬空的 `reference/**` exclude。
- **本次累计删除**：约 -5,600 行（阶段 B+C 提交 62 文件 -5643）。加上更早的 cloud_services/reference/device_support(`ca600dff`)、observability/ops_metrics(`4ac2ca33`)，本轮瘦身共移除约 11,500 行 / ~98 文件。
- **门禁**：阶段 A 1523 passed；阶段 B+C 1397 passed / 3 skipped / 0 failed；ruff check + format clean；check_code_size PASS。




- **阶段 D（生产切流）——已核实完成（2026-07-06）**：
  - 双节点 nginx 配置 `/etc/nginx/conf.d/chat.donglicao.com.conf` 已把 `/device/`、`/dlc/`、`/health` 切到 `:8081`；旧路径 `/chat/`、`/api/`、`/admin/`、`/agent/`、`/fleet/`、`/digital-human/`、`/v1/`、`/v1/live`、`/v1/voice`、`/device/v1/ws` 显式 `return 410`。
  - 阿里云：`lima-router.service` inactive；`/opt/lima-router/` 目录不存在；:8080 无监听。
  - 京东云：`lima-router.service` disabled/inactive；`/opt/lima-router/` 目录不存在；:8080 被 code-server 占用（非 lima-router）。
  - 公网冒烟：`/health` → 200；`/chat/`、`/api/v1/status`、`/admin` → 410；生产切流已实际生效。



- **阶段 D 后续清理（2026-07-06）**：

  - 删除 `/etc/nginx/conf.d/chat.donglicao.com.conf.pre-*` 历史备份（两节点均已无此文件，无需清理）。

  - 备份并删除 `/etc/systemd/system/*.retired-20260705` 退役 unit 文件（阿里云 8 个、京东云 1 个），备份存于 `/root/retired-units-20260706.tar.gz`。

  - 备份并删除阿里云 `/var/www/chat/*.bak*` 共 245 个历史备份文件，备份存于 `/root/chat-web-bak-20260706.tar.gz`。

  - 清理后公网冒烟：`/health` → 200，`/chat/` → 410，服务正常。## 2026-07-06 固件端改造 U8：新增 plotter MCP 工具 + 配网 SSID 前缀变更

## 2026-07-06 MCP 接入部署 + 小程序上传 + Git 提交推送

- **范围**：§6 MCP 接入部署（模式 A 官方云直连），小程序一键上传，子模块和父仓库提交推送。
- **创建的部署文件**：
  - `deploy/aliyun/dlc-mcp.service`：systemd 服务模板，`dlc_mcp/mcp_pipe.py` 作为持久 WebSocket 客户端连接小智云 MCP endpoint
  - `deploy/aliyun/install_dlc_mcp.sh`：一键安装脚本，检查 `.env` 中 `MCP_ENDPOINT` / `DLC_API_URL`，安装 systemd 服务
- **小程序上传**：
  - 微信开发者工具 CLI 上传成功
  - AppID: `wxbf3c1e0013b46343`，版本 `3.9.0`，大小 1.2MB
  - 提交说明：「LiMa瘦身版：对话走小智云，绘图走DLC」
- **Git 提交推送**：
  - 子模块 `esp32S_XYZ`：commit `bf1152c`，23 files changed (+197 / -2086)
  - 父仓库 `QWEN3.0`：commit `9143e90c`，4 files changed (+114 / -1)
  - 均已推送到 GitHub `origin/main`
- **MCP 部署待操作**（需用户手动）：
  1. 登录 `https://xiaozhi.me` → 智能体 → 配置角色 → MCP 接入点，复制 endpoint URL
  2. 在 VPS `.env` 中添加 `MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=<JWT>` 和 `DLC_API_URL=http://127.0.0.1:8080`
  3. 在 VPS 执行 `sudo bash deploy/aliyun/install_dlc_mcp.sh`
  4. 验证：`systemctl status dlc-mcp` + 对小智设备说"写你好"测试链式调用

## 2026-07-06 小程序端改造：删除 chat 页面 + 配网主路径切换 SoftAP + 版本号 3.9.0

- **范围**：按设计文档 `docs/xiaozhi-cloud/lima-slimdown-design.md` §5 实施小程序端改造，删除对话相关页面/API，简化配网为 SoftAP 主路径，版本号升级。
- **删除的文件/目录**：
  - `src/pages/chat/`（chat.vue + 3 个 composables）
  - `src/pages/chat-history/`（index.vue + detail.vue）
  - `src/api/chat/`（chat.ts）
  - `src/api/chat-history/`（chat-history.ts + index.ts + types.ts）
- **修改的文件**：
  - `src/pages.json`：移除 chat/chat-history 的 3 条页面注册项
  - `src/pages/index/composables/useHomeNavigation.ts`：删除 `goChat` / `goDigitalHuman`，移除 `@/i18n` 导入
  - `src/pages/index/index.vue`：删除 AI 对话和数字人两个创建入口卡片，解构中移除 `goChat` / `goDigitalHuman`
  - `src/utils/index.ts`：简化 `getChatBaseUrl` — 删除 `aliyun.donglicao.com` 分流逻辑，统一返回 `getEnvBaseUrl()`
  - `src/pages/device-config/provisioning-contract.ts`：`primaryChannel` 从 `ble_blufi` 改为 `softap_http`；`submitPayloadFields` 简化为 `['ssid', 'password']`
  - `manifest.config.ts`：`versionName` 3.8.7 → 3.9.0，`versionCode` 387 → 390
- **设计决策**：
  - API 前缀方案 1（保持 `/device/v1/app`）：`dlc_api` 保持旧前缀，小程序端 API 路径不变
  - SoftAP 为主配网路径：不需要蓝牙权限，步骤更少，固件已有稳定实现
  - `submitPayloadFields` 简化为仅 `ssid` + `password`：与 `78/esp-wifi-connect` 组件 `/submit` 端点实际解析逻辑对齐
- **验证**：
  - `npx vue-tsc --noEmit`：0 errors
  - `npx uni build --platform mp-weixin`：Build complete ✓
- **待执行**：微信开发者工具 CLI 上传 + 版本号 bump 提交（需用户确认后执行）

## 2026-07-06 固件端改造 U8：新增 plotter MCP 工具 + 配网 SSID 前缀变更

- **范围**：按设计文档 `docs/xiaozhi-cloud/lima-slimdown-design.md` §4 实施固件端改造，新增两个高层 MCP 工具让小智云 LLM 可以直接调用写字/绘图，并更新配网 SSID 前缀。
- **修改的文件**：
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/config.h`：新增 `DLC_API_BASE_URL` 宏 + `DLC_API_MAX_RESPONSE_BYTES` 安全限制
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/Kconfig.projbuild`：新增 `CONFIG_DLC_API_BASE_URL` Kconfig 项（默认 `https://chat.donglicao.com`）
  - `esp32S_XYZ/firmware/u8-xiaozhi/sdkconfig.defaults`：追加 `CONFIG_DLC_API_BASE_URL` 配置
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc`：
    - 新增 `#include "system_info.h"` 和 `#include <nvs.h>`
    - 新增私有方法 `GetDlcApiToken()`：从 NVS namespace `dlc` key `api_token` 读取 per-device token（SEC-007：token 不烧录进镜像）
    - 新增私有方法 `PostDlcApi()`：HTTPS POST 到 dlc_api，强制 https://（SEC-007），响应大小限制 128KB（SEC-005）
    - 注册 MCP tool `self.plotter.write_text`：设备端先调 dlc_api `/dlc/tasks/preview` 生成路径，再本地 `RunPathWithTaskId` 执行
    - 注册 MCP tool `self.plotter.draw_generated`：同上流程，用于 AI 绘图
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/provisioning_contract.h`：`kSoftApSsidPrefix` 从 `"Xiaozhi"` 改为 `"DLC"`；`kBlufiDeviceName` 从 `"Xiaozhi-Blufi"` 改为 `"DLC-Blufi"`
- **设计决策**：
  - 实现策略一（推荐）：设备端 tool 调用服务端 dlc_api 生成路径 → 再本地执行。对 LLM 行为不敏感，最稳健。
  - 使用 cJSON（固件已有依赖）而非 nlohmann::json（设计文档建议但固件未引入）
  - `Property` 构造函数无 description 参数，工具描述放在 `AddTool` 第二参数
  - device_id 使用 `SystemInfo::GetMacAddress()` 与 dlc_api token 验证对齐
- **安全审计对应**：
  - SEC-007：token 从 NVS 读取，不编译进镜像；强制 HTTPS
  - SEC-005：响应体大小限制 128KB，防止 OOM
  - SEC-004：使用 cJSON_Parse 安全解析，解析失败返回错误字符串
  - 防呆机制：`MotionExecutor` 已有 `motion_busy_` 原子锁 + RAII guard（P3 已实现）
- **服务端测试验证**：`pytest tests/test_dlc_*.py` — 55 passed, 0 failed
- **待验证**：固件需在 ESP32 硬件上编译和功能测试（本地无 ESP-IDF 编译环境）

## 2026-07-05 小智云瘦身 P5 深度死代码清理

- **范围**：P4 修复残留导入后，深度扫描并删除所有未被 `server_dlc.py` 生产路径引用的死代码。
- **删除的根目录文件（26 个）**：
  - `pipeline_graph.py`、`skills_registry.py`、`speculative_execution.py`、`think_plan_context.py`
  - `channel_retirement.py`、`health_probe.py`、`server_lifespan_state.py`、`token_health.py`、`device_mode.py`
  - `chat_models.py`、`chat_request_utils.py`、`healthcheck_ping.py`、`lima_context.py`、`response_builder.py`
  - `safe_command.py`、`http_body_limit.py`、`lima_constants.py`、`brand_config.py`
  - HTTP 传输链：`http_caller.py`、`http_async.py`、`http_sync.py`、`http_stream.py`、`http_stream_core.py`、`http_errors.py`、`http_response.py`、`http_retry.py` + `http_request_builder/` 目录
- **删除的 routes 文件（19 个）**：
  - 全部 `routes/admin_*.py`（16 个）、`routes/facade.py`、`routes/system_endpoints.py`、`routes/admin_v1_auth.py`
- **删除的死代码目录（21 个）**：
  - `agent_contracts/`、`agent_eval/`、`agent_evolution/`、`agent_roles/`、`agent_runtime/`
  - `channel_gateway/`、`external_enrichment/`、`lima_mcp/`、`lima_fc_tools/`、`local_retrieval/`
  - `monitor/`、`notify/`、`ops_entrypoint/`、`prompts/`、`routing/`
  - `routing_loop/`、`routing_ml/`、`tool_gateway/`、`user_identity/`、`deployment/`
  - `lima_mcp_stdio/`、`fleet/`
- **删除的关联测试/脚本（16 个）**：
  - `tests/test_pipeline_graph.py`、`tests/test_chat_models.py`、`tests/test_chat_request_utils.py`
  - `tests/test_healthcheck_ping.py`、`tests/test_lima_context.py`、`tests/test_response_builder_usage.py`
  - `tests/test_safe_command.py`、`tests/test_semantic_router.py`
  - `tests/test_local_retrieval_*.py`（4 个）、`tests/test_safe_math.py`、`tests/test_tool_gateway_governance.py`
  - `tests/test_user_identity.py`、`tests/test_external_enrichment.py`
  - `scripts/generate_pipeline_graph.py`、`scripts/healthcheck_ping.py`
  - `tests/test_fleet_*.py`（3 个）
- **保留的根目录文件**（经引用分析确认仍被生产路径使用）：
  - `access_guard.py`、`app_status_ws_ticket.py`、`async_utils.py`
  - `dashscope_image_client.py`、`device_protocol_registry.py`、`device_ws_ticket.py`
  - `rate_limiter.py`、`rate_limiter_redis.py`、`runtime_env.py`、`ws_ticket.py`
- **门禁验证**：
  - `pytest`：1565 passed, 3 skipped, 0 failed
  - `ruff check .`：All checks passed
  - `scripts/check_code_size.py`：PASS
- **VPS 部署验证**：
  - JDCloud (117.72.118.95)：`dlc-drawing` active，`/health` 返回 200
  - Aliyun (47.112.162.80)：`dlc-drawing` active，`/health` 返回 200

## 2026-07-05 小智云瘦身 P4 物理删除旧系统代码 + 残留导入修复

- **范围**：P4 物理删除 LiMa 旧系统冗余代码后，修复所有残留的 `ModuleNotFoundError` 和 `ImportError`，清理失效测试文件，确保全量测试通过。
- **删除的模块**：
  - `routes/device_app_chat.py` — 聊天路由（依赖已删除的 `routes.upload`）
  - `observability/capability_evidence.py` — 能力证据记录（依赖 `session_memory`）
  - `session_memory/outcome_ledger.py` — 会话记忆 outcome 分类账
  - `lima_mcp_stdio/lima_ops_mcp.py` — 运维 MCP（已失效）
  - 150+ 个引用已删除模块的测试文件
- **修复的残留引用**：
  - `routes/device_gateway_helpers.py`：`_record_device_task_evidence()` 中 `observability.capability_evidence` → stub（debug 日志）
  - `routes/ws_task_helpers.py`：`record_outcome_ledger()` 中 `session_memory.outcome_ledger` → stub（debug 日志）
  - `routes/device_gateway_ws_handlers.py`：语音相关函数 stub 处理
  - `device_gateway/device_draw_handler.py`：移除 `image_fallback` 导入
  - `tests/device_app_helpers.py`：移除 `chat_router`/`images_router`/`voice_router` 导入
  - `pyrightconfig.json`：清理已删除路径（`context_pipeline/`、`session_memory/`、`routing_engine/` 等），替换为 `dlc_api/`、`dlc_core/`、`dlc_mcp/`
  - `tests/test_testside_f401_safety_gate.py`：更新引用从 `test_routing_bridge.py` → `test_dlc_deps.py`
- **门禁验证**：
  - `pytest`：1696 passed, 3 skipped, 0 failed（84s）
  - `ruff check .`：All checks passed
  - `ruff format --check`：All checks passed
  - `scripts/check_code_size.py`：PASS — all size constraints satisfied
- **VPS 部署验证**：
  - JDCloud (117.72.118.95)：`dlc-drawing` active，`/health` 返回 200
  - Aliyun (47.112.162.80)：`dlc-drawing` active，`/health` 返回 200
  - 公网 `https://chat.donglicao.com/dlc/` 路由正常（403 = Cloudflare WAF 对无 token 请求的预期行为）

## 2026-07-05 小智云瘦身 P3 VPS 部署与验证

- **范围**：将 P3 安全加固代码部署到 VPS，创建独立 systemd 服务，配置 nginx 路由。
- **本地冒烟**：
  - `server_dlc.py` 独立启动成功（端口 18080），`/health` 返回 `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`。
  - `/dlc/tasks/validate` 带认证返回 `{"ok":true}`。
  - SSRF 防护：`169.254.169.254` 被 `_is_ssrf_host` 拦截，返回 `"image_url hostname is blocked"`。
- **VPS 部署（Aliyun 47.112.162.80）**：
  - `deploy_unified.py --slice core --target aliyun`：910 文件上传成功，主服务重启健康。
  - 创建 `/etc/systemd/system/dlc-drawing.service`：独立 systemd unit，端口 8081，`/usr/local/bin/python3.10`。
  - `dlc-drawing` 服务 `active`，`/health` 返回 200。
  - nginx `chat.donglicao.com.conf` 新增 `location ^~ /dlc/` → `proxy_pass http://127.0.0.1:8081`。
  - nginx `-t` 通过，reload 成功。
- **认证格式修复**：
  - VPS `.env` 中 `LIMA_DEVICE_TOKENS` 使用 `device_id=token` 格式（device-gateway 兼容），而非 DLC 代码期望的 `token:device_id`。
  - 更新 `dlc_api/deps.py` 的 `_load_device_tokens()` 同时支持 `:` 和 `=` 分隔符。
  - 新增 2 个测试：`test_verify_accepts_equals_format_env`、`test_verify_accepts_mixed_formats_env`。
  - 重新部署 `deps.py` 到 VPS，重启 `dlc-drawing`，认证通过。
- **VPS 冒烟结果（Aliyun localhost:8081）**：
  - ✅ `dlc-drawing` active
  - ✅ `/health` → `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`
  - ✅ `/dlc/tasks/validate` 带认证 → `{"ok":true,"errors":[],"warnings":[]}`
  - ✅ SSRF 阻断 → `"image_url hostname is blocked (private/loopback/link-local)"`
  - ✅ 无认证 → 401 `"Field required"`
  - ✅ 主服务 `lima-router` 不受影响 → `{"status":"ok","version":"2.0"}`
- **公网路由待解决**：
  - `chat.donglicao.com` DNS 解析到 Cloudflare（198.18.2.214），通过 Cloudflare Tunnel 路由到 JDCloud。
  - DLC 服务部署在 Aliyun（port 8081），JDCloud 上尚未部署。
  - JDCloud SSH 认证失败（`deploy_config.jdcloud_password()` 未配置或已过期），无法自动部署。
  - **解决路径**：用户提供 JDCloud SSH 凭据 → 部署 DLC 到 JDCloud；或配置 Cloudflare 将 `/dlc/*` 路由到 Aliyun。
- **测试**：`pytest tests/test_dlc_deps.py` → 15 passed（+2 新增格式兼容测试）。

## 2026-07-05 小智云瘦身 P3 安全与可运维实施

- **范围**：按 P3 路线图实施服务端安全加固、MCP tool 扩展、生产入口与超时保护。
- **安全加固**：
  - `dlc_api/routes.py` 新增 SSRF 防护：`_is_ssrf_host()` 使用 `ipaddress` 标准库拒绝私网/回环/链路本地地址（含 `169.254.169.254` 云元数据端点）和 `localhost`。
  - `dlc_api/routes.py` 新增 `POST /dlc/tasks/validate` 端点：接收 path 数组，调用 `dlc_core.validate_path` 做工作区边界 + 点数上限校验。
  - `dlc_core/draw.py` 新增 T1 超时保护：`handle_draw_from_image` 内部用 `asyncio.wait_for(timeout=25.0)` 包裹图片矢量化，超时返回 `{"status":"timeout"}`。
- **MCP tool 扩展**：
  - `dlc_mcp/server.py` 新增 `dlc.draw_from_image` 和 `dlc.get_device_status` 两个 tool，tool 列表从 2 扩展到 4。
  - 重构为 `TOOL_HANDLERS` 字典分发模式，每个 tool 有独立 handler 函数，`_handle_tools_call` 只做路由。
  - 新增 `_get_json()` 辅助函数支持 GET 请求（设备状态查询）。
- **生产入口**：
  - 新增 `server_dlc.py`：精简 FastAPI 入口，只注册 `dlc_router`，不含 chat/admin/voice/provider 路由。版本 `0.3.0-p3`。
- **测试新增**（5 个）：
  - `test_preview_draw_from_image_ssrf_private_ip`：5 种私网/元数据 URL 全部被拒绝。
  - `test_validate_path_valid`：合法路径返回 `ok=True`。
  - `test_validate_path_out_of_bounds`：越界点返回 `ok=False` + errors。
  - `test_tools_call_draw_from_image_validates_args`：MCP tool 参数校验。
  - `test_tools_call_get_device_status_validates_args`：MCP tool 参数校验。
- **验证结果**：
  - `pytest tests/test_dlc_*.py` → **53 passed**（+5 新增）
  - `ruff check` → All checks passed
  - `ruff format` → 全部已格式化
  - `check_code_size.py` → PASS（所有文件 ≤300 行，所有函数 ≤50 行）

## 2026-07-05 小智云瘦身 P2 实施（S1~S4 + M + T）

- **范围**：按已批准的 P2 路线图完成 `dlc_api` / `dlc_core` 服务收口、小程序 busy 防呆与配网入口补丁，并补足验证证据。
- **服务端实现**：
  - `dlc_core/draw.py` 新增 `handle_draw_from_image(image_url, device_id)`，把 `device_gateway.device_draw_handler.handle_device_draw(..., image_url=...)` 统一封装为 `{status, svg_path, preview_svg, width, height, model, error}`。
  - `dlc_api/routes.py` 新增 `draw_from_image` preview/dispatch 分支；新增 `GET /dlc/devices/{device_id}/status`，复用 `dlc_core.device_status.get_device_status` 返回在线/工作/当前任务/影子状态。
  - `dlc_core/device_status.py` 新增 facade，复用 `routes.device_app_api._build_device_status` + `device_intelligence.shadow_store.snapshot()` 聚合状态。
  - `dlc_api/deps.py` 新增 P2 per-device token 占位：优先查 `v2_device_token(token_hash)`，失败时回退到 `LIMA_DEVICE_TOKENS`。
- **小程序实现**：
  - `useDeviceEvents.ts` 暴露 `isDeviceBusy`（`running/accepted/progress`）。
  - `useDeviceActions.ts` 在 `home`/`write_text`/`draw_generated`/`run_path` 前增加 busy 早退 toast，避免重复下发。
  - `write-draw-panel.vue` / `voice-command.vue` 接入 `deviceBusy`，写字/画图/语音按钮在设备忙时禁用并显示提示。
  - `device-list/index.vue` 新增「配置网络 / 一键配网」入口，直达 `/pages/device-config/index`。
  - `i18n/en.ts`、`i18n/zh_CN.ts` 补充 `deviceBusy` / `deviceBusyHint` / `provisionDevice` 文案。
- **测试新增**：
  - `tests/test_dlc_core_draw.py`：补 `handle_draw_from_image` 成功/失败/非法 URL。
  - `tests/test_dlc_core_status.py`：补 `get_device_status` 聚合/空 shadow。
  - `tests/test_dlc_api.py`：补 `draw_from_image` preview/dispatch 与 `/dlc/devices/{device_id}/status`。
  - `tests/test_dlc_deps.py`：补 DB token 命中/缺失/异常/环境变量回退。
- **验证结果**：
  - `.venv310/Scripts/python -m pytest tests/test_dlc_*.py tests/test_dlc_deps.py -v --tb=short` → **48 passed**
  - `ruff check dlc_api dlc_core tests/test_dlc_api.py tests/test_dlc_core_draw.py tests/test_dlc_core_status.py tests/test_dlc_deps.py --fix` → **All checks passed**
  - `npx pyright dlc_api/routes.py dlc_api/deps.py dlc_core/draw.py dlc_core/device_status.py dlc_core/__init__.py` → **0 errors, 0 warnings**
  - `pnpm exec vue-tsc --noEmit`（`manager-mobile/`）→ **0 errors**
  - `pnpm exec eslint ...`（变更前端文件）→ **0 errors，剩余 UnoCSS 排序 warning 4 条，未阻塞**
- **文档同步**：`docs/xiaozhi-cloud/lima-slimdown-design.md` 已勾选 `/dlc/tasks/preview`、`/dlc/tasks/dispatch`、`/dlc/devices/{device_id}/status`、`vue-tsc --noEmit` 验收项。

## 2026-07-05 仓库规则升级：Ponytail 第一原则 + ESP32 skills 强制加载

- **范围**：按用户要求把 Ponytail 原则写入仓库原则，强调"能去 GitHub 找高可靠代码就尽量不要写代码"、"降低测试风险"、"会偷懒的 agent 才是合格 agent"。
- **修改文件**：
  - `AGENTS.md`：新增「Ponytail 第一原则（最高优先级）」章节，放在「代码质量规则」之前；硬规则第 1 条改为 Ponytail 第一原则；底部 Ponytail 章节改为索引。
  - `docs/AGENTS_PONYTAIL.md`：完全重写，详述核心信条、决策阶梯、ESP32/固件/小程序改动必须加载对应 skills、不可妥协边界、自检问题。
- **新增硬规则**：
  - ESP32 / 固件 / 小程序 / 嵌入式相关代码改动前，必须主动加载对应领域 skills（`esp32`、`esp-idf-handling`、`jlink`、`openocd`、`serial`、`workbench-*`、uni-app / Vue 相关 skills 等）。
  - 不加载对应 skill 就动手改固件/小程序是禁止的。
- **核心信条落地**：
  - Ponytail 是第一原则，优先级高于编码冲动与炫技式实现。
  - 优先复用 GitHub 高可靠代码，降低测试风险与维护面。
  - 最小变更、最小文件、最小函数。

## 2026-07-05 LiMa 瘦身设计文档复核与证据补全

- **范围**：按用户要求消除 `docs/xiaozhi-cloud/lima-slimdown-design.md` 中的架构不确定性，通过权威仓库/官方资料补充证据链。
- **关键查证结论**：
  - 小智官方控制台为 `https://xiaozhi.me`（非 `xiaozhi.dev`）；官方云原生 MCP endpoint 为 `wss://api.xiaozhi.me/mcp/?token=<JWT>`，自定义 MCP 服务以客户端身份直连，无需强制部署 `mcp-endpoint-server`。
  - `mcp-endpoint-server` 配置文件为 `data/.mcp-endpoint-server.cfg`，INI 格式，固定 section：`[server]`、`[websocket]`、`[security]`、`[logging]`；自定义 MCP 服务同样以客户端连 `/mcp_endpoint/mcp/`。
  - U8 固件已存在稳定的 outbound HTTP/HTTPS 先例：`ota.cc:211`、`mcp_server.cc:209`、`assets.cc:436`、`boards/common/esp_video.cc:945`、`boards/common/esp32_camera.cc:237` 均使用 `Board::GetInstance().GetNetwork()->CreateHttp()`。
- **文档修改**：
  - §1/§2 架构图中所有 `xiaozhi.dev` 控制台引用改为 `xiaozhi.me`，并补充模式 A/B 双部署模式。
  - §4.2 固件示例改为复用现有 `CreateHttp()` 抽象，删除"无 outbound HTTP 先例"警告，给出 `PostDlcApi()` 帮助函数与配置项。
  - §6 重写为「模式 A：官方云直连」和「模式 B：自托管 mcp-endpoint-server」两种确定部署方式，含配置示例、决策表、证据来源清单。
  - §7 P0 验证项更新为模式 A/B 实测步骤；§9 风险表更新；§10.4 小智云验收标准更新；§12 复核记录新增 B8/B9/W12 修正项并删除"待验证"尾巴。
- **链式调用代码证据补充**：用户指出 LLM 链式调用应可通过官方代码确定。已读取 `xinnan-tech/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py`：
  - `MAX_DEPTH = 5` 设置最大工具调用递归深度；
  - `_handle_function_result()` 将 `Action.REQLLM` 结果以 `role="tool"` 写回对话历史；
  - `self.chat(None, depth=depth + 1)` 让 LLM 基于工具结果再次决策。
  - **结论**：自托管服务器架构原生支持多轮 tool call 链式调用；官方云大概率复用同一机制，但闭源官方云仍需 P0 实测确认真实 LLM 行为。§2.3/§4.2/§6.5/§7/§12 已据此更新。
- **剩余 intentional 不确定性**：仅剩下官方云真实 prompt/模型下的 LLM 实际行为，属于 P0 实测项而不再是不确定性；文档默认仍按方案 A（固件端 tool 直接调 dlc_api）实现以规避风险。
- **配置校验**：`~/.kimi-code/config.toml` 已存在 `labs100x` Anthropic provider（url/key 与用户给定一致），注释说明 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 需作为环境变量设置；TOML 校验通过。

## 2026-07-04 M4 延后债务清理（D1~D4）

- **范围**：清理 M4 结项时明确延后的 4 项债务，覆盖小程序、Chat Web、固件 CI 三端。
- **D4 固件 native 单测 CI 首跑验证**：核查 `esp32S_XYZ` CI `firmware-native-tests` job 首跑结果为 **success**（含 `test_u8_ota_allowlist` + `test_u8_mqtt_hex_decode`）。但发现 `manager-mobile-tests` job 因 P3.1 composable 提取 + P3.3 timeout 常量化后，`tests/ci/test_manager_mobile_device_info.py` 仍只读 `index.vue` 且断言旧字符串而整体失败。修复：将设备详情相关断言指向新的 `useDeviceEvents.ts`/`useDeviceActions.ts`（读取 DEVICE_DETAIL + composable 文件拼接），SoftAP 断言 `timeout: 15000` → `timeout: SOFTAP_SUBMIT_TIMEOUT_MS`，移除已不存在的 `connectXiaozhiHotspot` 断言。本地 pytest **23/23 passed**。
- **D1 `chat/chat.vue` 拆分**：635 → 130 行。提取 `useChatMessages`（历史加载/保存/清空 + genMsgId）、`useChatStream`（流式发送/中断/regenerate）、`useChatHelpers`（滚动/时间格式化/markdown 渲染/长按/复制）三个 composable + 独立 `chat.scss`。模板 byte-identical（diff 验证），仅 `<script>` 与 `<style src>` 变更。
- **D2 `index/index.vue` 拆分**：604 → 238 行。提取 `useHomeData`（设备/任务加载 + primaryDevice/onlineCount 派生）、`useHomeNavigation`（8 个跳转入口）、`useTaskFormatters`（任务状态 label/color/progress 三态）+ 独立 `index.scss`。模板 + 样式 byte-identical（diff 验证）。
- **D3 Chat Web `styles.css` 按页面拆分**：2060 行单文件 → 5 个 `css/*.css`：`common.css`（重置/变量/滚动条/焦点/媒体查询/全局微交互）、`chat.css`（sidebar/main/topbar/messages/input/toast/modal/mobile + welcome orb）、`playground.css`、`auth.css`（login/register）、`pages.css`（keys/usage/devices/handwriting + P4 页面级项）。8 个 HTML 页面按需加载对应组合；`hash-assets.mjs` 适配 `css/` 目录 minify + 哈希；`deploy_chat_web.py` FILES 移除 `styles.css` 改为 5 个 `css/*.css`。
- **门禁**：小程序 `vue-tsc` 0 errors + `uni build -p mp-weixin` 通过；`vitest` 4 passed；`check-i18n-keys.mjs` 803 keys OK；主仓库 `pytest tests/ci/test_manager_mobile_device_info.py` 23 passed；Chat Web `node scripts/hash-assets.mjs` 构建通过（23 assets minified，5 CSS + 18 JS 哈希，9 HTML 重写）。
- **部署**：Chat Web 经 `deploy_chat_web.py` 部署到主 VPS，origin 5 个 `css/*.css` + 拆分后 HTML 全部 200（`--resolve` 绕 CDN 验证），nginx reload OK。旧 `styles.css`（68KB）保留在 origin 作为 CDN 缓存 HTML 的兜底，过渡期两态均可用。CDN 对新 `css/*` 路径的负缓存随 4h TTL 自然失效（`common.css` 已 `Cf-Cache-Status: HIT`）。
- **小程序上传**：版本 `3.8.6` → `3.8.7`，微信开发者工具 CLI 上传成功（1.2 MB / 1289312 字节）。
- **Git**：子模块 `esp32S_XYZ` `f785da5` 已 push origin main；主仓库更新子模块指针 + Chat Web/脚本/文档改动。
- **结论**：M4 全部延后债务清理完毕，全项目改善计划 P0→P3 无剩余债务。

## 2026-07-04 M4 里程碑完成（P3 重构/技术债）

- **审计收尾**：承接 M3（P2 LOW），完成全项目 P3 重构/技术债，覆盖小程序、Chat Web、固件三端。后端 P3 项在 M2/M3 已提前闭环。
- **P3 改进项**（6 项完成 + 2 项延后）：
  - P3.3 超时魔法数字统一：散落在 alova/chat/v2/useServerUrl/wifi-config/blufi-config/wifi-selector 的 8 处 timeout 数字收敛到 `src/config/timeouts.ts`（8 个语义命名常量），全部引用替换为常量。
  - P3.5 i18n CI 强制校验：`check-i18n-keys.mjs`（803 keys）与 vitest 接入 `esp32S_XYZ/.github/workflows/ci.yml` 的 `manager-mobile-tests` job，CI 强制一致。
  - P3.6 非微信端流式完整实现：`chat.ts` 抽公共 `parseSSEBuffer`，微信端走 `uni.request(enableChunked)`，非微信端走 `fetch` + `response.body.getReader()` + `AbortController`，保持 `{ abort }` 接口；替换 P0.4 的 fail-loud 占位。
  - P3.2 Chat Web 去重 + esbuild：`escapeHtml`/`escapeAttr`/`isAllowedImageUrl` 7 处重复收敛到 `js/utils.js`（`window.LiMaUtils`，含 backtick 转义补全），8 个 HTML 页面加载顺序调整；引入 esbuild 0.25.12 压缩 pass（styles.css 68KB→49KB，JS 全部 minify），`chat-web/package.json` + `hash-assets.mjs` 集成。CSS 按页面拆分（2060 行）作为债务延后（终端环境无法视觉验证）。
  - P3.1 小程序超大组件拆分：3 个逻辑臃肿组件提取 composable — `device-detail/index.vue` 761→331（`useDeviceEvents` + `useDeviceActions`）、`voiceprint/index.vue` 691→399（`useVoicePrintCrud` + `useAudioPlayer`）、`ultrasonic-config.vue` 667→266（`afskAudio` 纯函数 + `useUltrasonicAudio`）；模板/样式逐字节不变（git diff 验证）。`chat/chat.vue`(635) 与 `index/index.vue`(604) 以模板/样式为主、脚本已精简，盲拆风险高于收益，延后为债务。
  - P3.4 固件 native 单测 + CI 编译矩阵：新增 `test_u8_ota_allowlist.cpp`（25 用例：OTA 主机白名单/SHA-256 hex 校验/base64 形状）与 `test_u8_mqtt_hex_decode.cpp`（10 用例：hex 解码），接入 CI `firmware-native-tests` job；U1/U8 编译矩阵（`pio run` / `espressif/esp-idf-ci-action`）已存在。本机工具链损坏未本地验证，依赖 CI 首跑。
- **门禁验证**：
  - 主仓库 `pytest -q` → **4463 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check .` clean。
  - 小程序 `vue-tsc --noEmit` 0 errors + `uni build -p mp-weixin` 通过；`pnpm test`（vitest）4 passed；`check-i18n-keys.mjs` OK（803 keys）。
  - Chat Web `node scripts/hash-assets.mjs` esbuild 压缩 + 哈希构建通过（19 assets minified，9 HTML 重写）。
  - 固件 native 单测未本地编译（g++ 可用但按用户决策「只加代码不本地验证」），CI 首跑验证。
- **小程序上传**：版本 `3.8.5` → `3.8.6`，微信开发者工具 CLI 上传成功（1.2 MB / 1285697 字节），AppID `wxbf3c1e0013b46343`。
- **Git 提交与推送**：子模块 `esp32S_XYZ` `223bef7` 已 push；LiMa 主仓库更新子模块指针 + Chat Web 改动 + 文档同步。
- **下一步**：全项目改善计划 P0→P3 全部闭环。剩余债务：chat/index .vue 模板/样式拆分、Chat Web styles.css 按页面拆分、固件 native 单测 CI 首跑验证。

## 2026-07-03 M3 里程碑完成（P2 LOW 技术债/体验打磨）

- **审计收尾**：承接 M1（P0 安全）+ M2（P1 质量），完成全项目 P2 LOW 技术债与体验打磨，覆盖后端、Chat Web、小程序、固件（U1/U8）四端。
- **P2 改进项**（15 项全部完成并提交）：
  - P2.1 新增 `tests/test_http_caller_reexports.py`：断言 `http_caller.py` thin re-export 门面的全部符号（30 个）可从子模块正常导出，防止拆分后回归。
  - P2.2 `probe_loop.py` 与 `backend_probe_loop.py` docstring 增加交叉引用，说明两者职责边界（主动探活 vs 批量健康探测）。
  - P2.3 `.env.example` 占位密钥去敏化：形似真实密钥的占位符改为明显占位格式，降低误用/泄露面。
  - P2.4 移除 `requirements_dev.txt` 的 `httpx2~=2.5`：确认 `httpx 0.28.1` 已满足 starlette testclient；卸载后相关用例仍 GREEN（保留 starlette 弃用 warning，无功能影响）。
  - P2.5 小程序清理：`tabbarList.ts` 移除 TODO 占位；`utils/index.ts` 清理注释掉的 `console` 调试语句。
  - P2.6 抽公共 `getMode()` 到 `scripts/get-mode.ts`，`manifest.config.ts` 与 `pages.config.ts` 共用，消除重复实现。
  - P2.7 子模块移除已跟踪的 `unpackage/res/icons/*.png`（17 个构建产物），并在 `.gitignore` 增加 `unpackage/` 忽略规则。
  - P2.8 压缩主包图标 `src/static/app/icons/1024x1024.png`（458KB → 433KB，Pillow optimize）。
  - P2.9 `scripts/deploy_chat_web.py` 的 FILES 列表补充 `_headers`（含 HSTS / X-Content-Type-Options / 缓存策略），确保部署后安全头随静态资源上线。
  - P2.10 新增 `scripts/check-i18n-keys.mjs`：校验 `zh_CN.ts` 与 `en.ts` 的 key 一致性（当前 803 keys 一致），并接入 `package.json` 脚本。
  - P2.11 U1 固件分区表文件入库：`firmware/u1-grbl/extra/min_spiffs.csv` 从 Arduino-ESP32 框架复制标准版，`platformio.ini` 指向本地文件，避免依赖框架内置路径。
  - P2.12 U8 固件生产日志裁剪：`sdkconfig.defaults` 增加 `CONFIG_LOG_DEFAULT_LEVEL_INFO=y`，降低默认运行日志冗余。
  - P2.13 确认 `Makefile` 已无 `build-server`/`test-java` 等悬空 help 文本（P0.10 清理完成）。
  - P2.14 `docs/getting-started.md` 移除前置条件表中的「manager-api 编译」与 CI 章节「Java 测试 — manager-api 76+ 测试」（服务端已迁移至 LiMa 主项目）。
  - P2.15 小程序依赖清理：移除未使用的 `@tanstack/vue-query`（同步移除 `main.ts` 的 `VueQueryPlugin`）及 8 个非目标平台 `@dcloudio/uni-mp-*`（alipay/baidu/jd/kuaishou/lark/qq/toutiao/xhs），并移除 macOS 专用 `@esbuild/darwin-*` / `@rollup/rollup-darwin-x64`。
- **门禁验证**：
  - 主仓库 `pytest -q` → **4463 passed / 3 skipped / 2 deselected / 0 failed**。
  - `ruff check .` clean；`ruff format --check` clean；`pyright` 改动文件 0 errors；`check_code_size.py` PASS。
  - 小程序 `npx vue-tsc --noEmit` 0 errors + `npx uni build --platform mp-weixin` 通过；`pnpm test`（vitest）4 passed；`check-i18n-keys.mjs` OK（803 keys）。
  - 固件：`pio run -e release_esp32s3`（U1）与 `idf.py build`（U8）因本机 PlatformIO/ESP-IDF 环境缺失/损坏，未能在本地执行；改动为低风险配置（分区表文件、日志级别），后续在有完整固件工具链的环境补跑。
- **miniprogram-ci 上传修复**：P2.15 清理小程序依赖后，`miniprogram-ci` 上传报 `TypeError: _lruCache is not a constructor`——根因是 `@babel/helper-compilation-targets` 依赖被解析到 `lru-cache@11`（该版本改为具名导出，不再默认导出构造函数），而 Babel 期望 `lru-cache@5` 的默认构造函数。修复：在 `pnpm-workspace.yaml` 增加 `overrides` 强制 `@babel/helper-compilation-targets>lru-cache: ^5.1.1`（pnpm 10 已不再读取 `package.json` 的 `pnpm.overrides`，故同步删除该失效字段）。重装后 lockfile 锁定 `lru-cache@5.1.1`，Babel 编译链恢复正常。
- **小程序上传**：修复后版本号 `3.8.4` → `3.8.5`，已通过微信开发者工具 CLI 上传成功，AppID `wxbf3c1e0013b46343`。
- **Git 提交与推送**：子模块 `esp32S_XYZ` 提交 P2 剩余改动（固件/文档/小程序依赖 + lru-cache override 修复）；LiMa 主仓库更新子模块指针并提交后端/脚本/测试/文档改动，push origin main。
- **文档同步**：更新 `progress.md`（本条目）、`findings.md`（M3 发现）、`STATUS.md`（当前状态）。
- **下一步**：全项目改善计划 P0→P2 已闭环；P3（长期重构，如非微信端 SSE 完整实现、分包体积优化）作为后续可选里程碑，见 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`。

## 2026-07-03 M2 里程碑完成（P1 MEDIUM 全项目质量/文档/测试改进）

- **审计闭环**：承接 M1 安全修复，完成全项目 P1 MEDIUM 质量改进与文档同步，覆盖后端、Chat Web、小程序（uni-app）、固件（ESP32 U1/U8）四个端。
- **P1 改进项**（15 项全部完成并提交）：
  - P1.1 `session_memory` 幂等迁移：静默 `INSERT` 失败路径改 `logger.debug` 并说明原因。
  - P1.2 `observability/jsonl_store` 审计日志轮转：IO 异常路径改 `logger.warning`。
  - P1.3 文档同步：更新 `AGENTS.md` 与 `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` 的模块归属、流水线步骤与 Chat Web 入口。
  - P1.4 `code_context/chroma_vector_store` 降级：ChromaDB 不可用路径改 `logger.warning`。
  - P1.5 小程序类型债务收敛：`utils/index.ts` 减少 `any` 使用、增加 `SubPackage` 类型、清理 `deepClone` 类型；`utils/platform.ts` 增加 `__UNI_PLATFORM__` 运行时回退。
  - P1.6 删除死代码：`store/config.ts` 删除并清理 `store/index.ts` 导出；`store/user.ts` 移除冗余 `uni.removeStorageSync('userInfo')`。
  - P1.7 小程序 API 层统一：`chatCompletion` 迁移到 alova；非 mp-weixin 流式 `chatCompletionStream` 保持 fail-loud。
  - P1.8 修复路由悬空：`/pages/mine/mine` 相关残留引用清理。
  - P1.9 `manifest.config.ts` 与 `src/manifest.json` 的 `urlCheck` 生产环境改为 `true`。
  - P1.10 Chat Web 域名配置统一：`index.html` 与 `js/app-boot.js` 通过 `window.LiMaConfig` 单点配置。
  - P1.11 U8 固件死代码清理：`main/CMakeLists.txt` 移除非目标板（ml307/nt26/dual_network/rndis/esp_video）源码。
  - P1.12 协议版本管理：`docs/schemas/edge_*/*.schema.json` 增加 `schema_version: "1.0.0"`。
  - P1.13 U1 固件平台配置注释：`platformio.ini` 补充 `[env]` 默认配置被 `release_esp32s3` 覆盖的说明。
  - P1.14 边缘协议文档：`docs/schemas/edge_a/b/c/README.md` 增加迁移至 LiMa `device_gateway` 的提示横幅。
  - P1.15 前端测试基建：`vitest` 3.2.6 + `jsdom` + `tests/utils/deepClone.test.ts`，补充 `package.json` 测试脚本。
- **M1 遗留 Chat Web 部署修复**：`scripts/deploy_chat_web.py` 在 SFTP 上传前增加 `mkdir -p`（支持远程 `/var/www/chat` 及子目录 `js/`），修复新 VPS 首次部署缺失远程目录问题。
- **门禁验证**：
  - 主仓库 `pytest -q` → **4433 passed / 3 skipped / 2 deselected / 0 failed**。
  - `ruff check .` clean；`ruff format --check` clean；`pyright` 改动文件 0 errors。
  - 小程序 `npx vue-tsc --noEmit` 0 errors + `npx uni build --platform mp-weixin` 通过。
  - 新增 vitest 用例：`npx vitest run`（manager-mobile）GREEN。
- **VPS 部署**：
  - 主后端 `deploy_unified.py --target aliyun --slice core` → 893 文件上传成功，健康检查 OK。
  - Chat Web `deploy_chat_web.py` → 修复后成功，nginx reload OK。
- **小程序上传**：版本号 `3.8.2` → `3.8.3`，已通过微信开发者工具 CLI 上传成功，AppID `wxbf3c1e0013b46343`，提交大小 989.2 KB。
- **Git 提交与推送**：
  - 子模块 `esp32S_XYZ`：M2 批量修复提交（`f74da07..5c1408f`）+ 版本 bump 提交。
  - LiMa 主仓库：将更新 esp32S_XYZ 子模块指针到 `5c1408f`，并提交 `scripts/deploy_chat_web.py` 修复。
- **文档同步**：更新 `progress.md`（本条目）、`findings.md`（M2 补充发现）、`STATUS.md`（当前状态）。
- **下一步**：M3 里程碑（P2 LOW 技术债/体验打磨），具体计划见 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`。

## 2026-07-03 M1 里程碑完成（P0 全项目安全/正确性修复）

- **审计入口**：通读后端（Python/FastAPI）、Chat Web、小程序（uni-app）、固件（ESP32 U1/U8），识别 3 CRITICAL + 11 HIGH + ~20 MEDIUM + ~15 LOW 问题，制定并落盘 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`（P0→P3 四阶段）。
- **P0 修复项**（全部提交）：
  - CRI-F1：小程序上传私钥 `git log --all` 核实无历史提交，README 加「密钥保管」段落；`.gitignore` 已覆盖 `secrets/` 与 `*.key`。
  - CRI-F2：小程序 `env/.env.production` / `env/.env.test` 的 `NODE_ENV` 从 `development` 修正为 `production` / `test`。
  - CRI-F3：移除 `vite.config.ts` 三处 `console.log`（含打印全量 env），避免构建日志泄露 token 来源。
  - HIGH-F1：非微信端流式 `chatCompletionStream` 由「pollTimer=null 静默失败」改为 fail-loud，抛明确错误；完整 SSE 实现推迟至 P3.6。
  - HIGH-F6：Chat Web `chat-api.js` 图片生成路径增加 `isAllowedImageUrl` 域名白名单（`image.pollinations.ai` / `chat.donglicao.com` / `api.donglicao.com`），防止 XSS 通过恶意图片 URL 注入。
  - HIGH-B1：修复 `xiaozhi_drawing/pipeline.py` 的 `except ImportError: pass` 静默降级，改为 `logger.warning` 并说明 fallback。
  - HIGH-B2：扩展 `tests/test_ci_gates.py` 的 `_p13_scan_paths()` 为排除式扫描（排除 `tests/scripts/data/.worktrees/reference/esp32S_XYZ/...` 后扫全部生产 `.py`），覆盖 `xiaozhi_drawing/`、`context_pipeline/`、`session_memory/` 等原盲区；新增 `.worktrees` 到 `_P13_SKIP_DIRS`。
  - HIGH-W1：U1 默认禁用 WebUI OTA（`OTA_DISABLED_BY_DEFAULT`），`/updatefw` 与 `WebUpdateUpload` 直接返回 403，注释说明启用前置条件。
  - HIGH-W2：U8 OTA 服务器下发的 `mqtt`/`websocket` 端点加 `IsAllowedEndpointUrl` 白名单（`chat.donglicao.com` / `donglicao.com` / `localhost` / `127.0.0.1`），非白名单 host 拒绝写入 NVS 并 `ESP_LOGE`。
  - HIGH-W3：清理固件服务端残留基础设施（删除 `Dockerfile-server`、README/getting-started/Makefile 加「已迁移至 LiMa 主项目 device_gateway」标注、移除已删服务运行命令）。
- **提交与推送**：主仓库 2 提交（M1 安全 batch + 子模块指针）；子模块 `esp32S_XYZ` 4 提交；均已 push origin main。
- **门禁验证**：主仓库 `pytest -q` → **4433 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check` / `ruff format --check` clean；`check_code_size.py` PASS；`pyright` 改动文件 0 errors（仅既有 cv2/skimage warning）。小程序 `npx vue-tsc --noEmit` + `npx uni build --platform mp-weixin` 通过。
- **VPS 部署**：`deploy_unified.py --target aliyun --slice core` → 893 文件上传成功，健康检查 OK；`deploy_chat_web.py` 因远程 `/var/www/chat` 目录缺失失败，已记录为 M1 遗留项，需运维手动 `mkdir -p /var/www/chat` 后重试或后续加入脚本自动创建。
- **文档同步**：更新 `progress.md`（本条目）、`findings.md`（M1 审计发现）、`STATUS.md`（M1 状态）。
- **下一步**：M2 里程碑（P1 MEDIUM 质量门禁 + 文档同步），或继续处理 M1 遗留的 Chat Web 部署目录问题。


## 2026-07-03 深度瘦身 U 批完成（routes/device_gateway_ws_handlers.py hello 握手机制抽到 device_gateway_hello_helpers.py）

- **背景**：T 批闭环后继续扫描抽离候选。`check_code_size` PASS（无 >300 行文件、无 >50 行函数），转入细粒度接缝发现。对比两候选：`routes/device_gateway_ws_handlers.py`（269 行）与 `device_gateway/device_draw_handler.py`（273 行）。
  - ws_handlers：hello 握手机制子域（`_authenticate_hello`/`_negotiate_hello_protocol`/`_create_hello_session`/`_check_attestation`/`_reject_too_many_connections` 5 个私有 helper，约 94 行）内聚清晰，`handle_hello` 留作公共入口委托调用。
  - device_draw_handler：SVG 子域被 5 测试文件密集 `patch`（`SVGConverter`/`validate_svg_path`/`optimize_svg_path`/`precheck_draw_motion_path`），且 `precheck_draw_motion_path` 在搬迁与保留部分都用到——S 批式 patch 迁移 ×5 文件，风险高。
  - 选 ws_handlers hello 子域为最优目标。
- **迁移面精确核实**：`attestation_verifier` 是稳定单例（ripgrep 确认无 `set_*_for_tests`/`install_*_for_tests`/`monkeypatch` 替换接口——S 批稳定 vs 可替换单例判定法），顶层导入安全。但 8 处测试经 `monkeypatch.setattr(handlers, "attestation_verifier", ...)`/`patch.object(handlers, "attestation_verifier", ...)` **替换模块属性**（conftest 3 + test_device_attestation 4 + test_handle_hello_success 1），`_check_attestation` 抽走后从 `hello_helpers` 查 `attestation_verifier`，必须把这 8 处重指到 `hello_helpers`。`handle_hello`/`registry`/`shadow_store`/`drain_pending_tasks` 留在 ws_handlers，对应 patch 不动。`test_routes_device_gateway_ws.py` 的 `patch.object(dgws, "handle_hello", ...)` 绑定 WS 路由模块而非 handlers，不受影响。
- **抽离**：新建 `routes/device_gateway_hello_helpers.py`（133 行），搬入 5 helper + 各自所需导入（`validate_device_token`/`ProtocolNegotiator`/`attestation_verifier`/`attestation_failed_frame`/`attestation_warning_frame`/`extract_ws_token`/`send_ws_error`/`ticket_device_id`）。ws_handlers 删除 5 helper + 6 个死导入（`ProtocolError`/`attestation_failed_frame`/`attestation_warning_frame`/`ProtocolNegotiator`/`AttestationResult`/`attestation_verifier`/`validate_device_token`/`extract_ws_token`/`send_ws_error`/`ticket_device_id`），加 `from routes.device_gateway_hello_helpers import _authenticate_hello, ...`。269→175 行（-94）。
- **特征化测试**：新增 `test_hello_helpers_lives_in_dedicated_module` 锁定 5 helper 在 `hello_helpers` 模块可调用。
- **门禁**：`ruff check` + `ruff format --check` 5 改动文件 clean；`check_code_size.py` PASS；`pyright` 2 生产文件 0 errors；聚焦 53 测试 GREEN（ws_handlers/attestation/protocol_negotiation/ws_routes/ws_lifecycle/mqtt）；全量 `pytest -q` → **4433 passed / 3 skipped / 2 deselected**（较 T 批 4432 +1 = 新增特征化测试）。
- **下次**：git add/commit/push origin + CI Tests 实证 + 公网 4 测试冒烟。

## 2026-07-03 深度瘦身 T 批完成（device_gateway intent.py LLM planner 子域抽到 intent_llm_planner.py）

- **背景**：S 批闭环后 `routes/device_gateway.py` 已降至 146 行（远低于上限），继续拆 ws/ticket（~20 行）是过度碎片化（违反 Ponytail YAGNI）。转向其他逼近上限模块：对比 `routes/device_gateway_ws_handlers.py`（269 行，8 测试文件 + 既有导入排序违规，风险高）与 `device_gateway/intent.py`（262 行，纯函数解析器，4 测试文件，零 router/monkeypatch 风险）——选 intent.py 的 LLM planner 子域抽离为最优目标。
- **接缝核实**：LLM replanning 子域（`_build_llm_planner_prompt`/`_strip_code_fence`/`_interpret_llm_plan`/`_llm_replan` 4 函数 + `_ALLOWED_CAPABILITIES`/`DANGEROUS_CAPABILITIES` 2 常量，约 82 行）是内聚子域，仅被 `resolve_voice_task` 内部经 `_llm_replan` 调用。外部约束：`DANGEROUS_CAPABILITIES` 被 `prompt_engineering/layers.py`（生产）+ `test_prompt_registry.py` 从 `device_gateway.intent` 导入；`_llm_replan` 被 `test_device_intent_hardening.py` 用 `dgi._llm_replan(...)` 调用。两者必须经 intent.py re-export 保持可访问。
- **抽离**：新建 `device_gateway/intent_llm_planner.py`（110 行），搬入 4 函数 + 2 常量。intent.py 用 `from device_gateway.intent_llm_planner import DANGEROUS_CAPABILITIES, _llm_replan  # noqa: F401  re-export` 保持 backward compatibility（`is` 同一对象，非拷贝）。从 intent.py 删除 4 函数 + 2 常量，262→178（-84 行）。`resolve_voice_task` 的 `_llm_replan(text, result)` 调用通过 re-export 仍指向新模块函数，无需改动调用方。
- **特征化测试**：新增 `test_llm_planner_lives_in_dedicated_module_and_is_re_exported` 锁定 4 函数 + 2 常量在新模块 + `dgi.DANGEROUS_CAPABILITIES is planner.DANGEROUS_CAPABILITIES` / `dgi._llm_replan is planner._llm_replan` 同一对象身份（防 re-export 丢失）。
- **门禁**：`ruff check` + `ruff format --check` 3 改动文件 clean；`check_code_size.py` PASS；`pyright` 改动 2 生产文件 0 errors（re-export 无循环引用）；聚焦 67 测试 GREEN（intent 4 文件）；全量 `pytest -q` → **4432 passed / 3 skipped / 2 deselected**（较 S 批 4431 +1 = 新增特征化测试）。
- **下次**：git add/commit/push origin + CI Tests 实证 + 公网 4 测试冒烟。

## 2026-07-03 深度瘦身 S 批完成（routes/device_gateway.py events 端点抽离到 device_gateway_events_routes.py）

- **背景**：R 批把 3 个 GET 查询端点抽到 `device_gateway_query_routes.py` 后，`routes/device_gateway.py` 降至 186 行。继续按"写端点分组"思路评估 events 端点（POST /events，motion_event/device_info/self_check uplink 处理）——接缝干净，依赖中 `shadow_store`/`process_motion_event_core`/`validate_uplink`/`ack_frame` 仅 events 端点用，抽离后主文件这 4 个导入变死。
- **抽离**：新建 `routes/device_gateway_events_routes.py`（62 行），搬入 POST /events 端点 + 独立 `APIRouter(prefix="/device/v1")`。`shadow_store` 和 `process_motion_event_core` 是稳定模块级单例（无 `set_*_for_tests` swap 接口，ripgrep 确认），顶层导入安全——与 R 批 `task_store` 需延迟导入不同（R 批 lesson：`set_*_for_tests` 可替换单例必须延迟导入）。模块 docstring 记录此区别。从 `routes/device_gateway.py` 删除 events 端点 + 4 个变死导入，主文件 186→146（-40 行）。`route_registry.py` 注册新模块。
- **测试侧同步**：3 个局部 app 测试需加 `app.include_router(events_router)`：`test_events_http.py`、`test_ai_to_motion_gate.py`、`test_routes_device_gateway.py`。`test_routes_device_gateway.py` 的 5 个 events 测试用 `patch.object(dg, "validate_uplink", ...)` 等 patch `dg` 模块属性——events 端点移走后这些属性不在 `dg` 上，改指 `events_routes` 模块（`patch.object(events_routes, "validate_uplink", ...)` + `events_routes.ProtocolError` + `events_routes.shadow_store`）。用 `server.app` 完整注册的测试（`test_registration.py`、`test_json_body_contract.py`）自动获得新路由无需改。
- **特征化测试**：新增 `test_server_registers_device_gateway_events_routes_after_extraction` 锁定 POST /events 在 `server.app` 注册 + 新模块 router prefix 与路径完整。
- **门禁**：`ruff check` + `ruff format --check` 7 改动文件 clean（`test_routes_device_gateway.py` patch 行变长经 `ruff format` 自动折行）；`check_code_size.py` PASS；`pyright` 改动 3 生产文件 0 errors（2 warnings 是既有 `body.get` 问题，行号偏移非新引入）；聚焦 77 测试 GREEN；全量 `pytest -q` → **4431 passed / 3 skipped / 2 deselected**（较 R 批 4430 +1 = 新增特征化测试）。
- **下次**：git add/commit/push origin + CI Tests 实证 + 公网 4 测试冒烟。

## 2026-07-03 深度瘦身 R 批完成（routes/device_gateway.py 查询端点抽离到 device_gateway_query_routes.py）

- **背景**：Q 批闭环后继续扫描抽离候选。`store.py`（289 行）是状态封装类（17 方法 + `self._lock`/`self._tasks` 耦合），非纯函数抽离目标；`family_approval_store.py`（273 行）CRUD 方法体不可避免，可抽纯函数仅 ~40 行且切断同模块调用，收益有限。AST 全仓扫描确认主代码库函数已全部 ≤50 行（check_code_size 实证），长函数空间耗尽。转回 `routes/device_gateway.py`（286 行）——3 个 GET 查询端点（`device_task_status`、`device_task_list`、`device_drawing_history`）与写端点天然分组，HTTP 测试覆盖充分。
- **抽离**：新建 `routes/device_gateway_query_routes.py`（125 行），搬入 3 个 GET 查询端点 + 独立 `APIRouter(prefix="/device/v1")`（FastAPI 合并同 prefix router 无冲突）。从 `routes/device_gateway.py` 删除 3 端点 + 2 个随之变死的导入（`Query`、`artifact_store`），主文件 286→186（-100 行）。`route_registry.py` 用 `("routes.device_gateway_query_routes", "device_gateway_query_routes")` 元组注册新模块。
- **延迟导入修正测试隔离**：初版新模块用顶层 `from device_gateway.store import task_store` 等，触发测试隔离回归——`test_sessions.py::test_registry_remove_zombies_requeues_outstanding_tasks` 调 `install_task_store_for_tests()` 替换 `device_gateway.store.task_store` 模块属性指向新对象，但已顶层导入的 `device_gateway_query_routes` 仍持有旧对象引用（Python 模块级 `from import` 绑定陷阱）。修正：4 个运行时单例（`task_store`、`task_snapshot`、`artifact_store`、`artifacts_for_device`）改回函数内延迟导入，与原 `routes/device_gateway.py` 行为一致。模块 docstring 记录此 lesson。
- **测试侧同步**：5 个测试文件用局部 `FastAPI()` app + `app.include_router(dg.router)` 构造客户端，需加 `app.include_router(query_router)`：`tests/device_gateway/test_task_queries.py`、`test_drawing_history.py`、`test_ai_to_motion_gate.py`、`tests/test_routes_device_gateway.py`、`tests/fake_u1_helpers.py`（后者覆盖 4 个 `test_fake_u1_cloud_*`）。用 `server.app` 完整注册的测试（`test_registration.py`、`test_json_body_contract.py`）无需改。POST-only 测试（`test_tasks_http.py`、`test_p1_4_device_stability_gate*.py`）无需改。
- **特征化测试**：新增 `test_server_registers_device_gateway_query_routes_after_extraction` 锁定 3 个查询端点路径在 `server.app` 注册 + 新模块 router prefix 与路径完整（`APIRoute.path` 含 prefix 拼接，断言用完整路径 `/device/v1/tasks/{task_id}` 等）。
- **门禁**：`ruff check` + `ruff format --check` 7 改动文件 clean；`check_code_size.py` PASS；`pyright` 改动 3 生产文件 0 errors（2 warnings 在 `create_device_ws_ticket` 的 `body.get` 是既有问题，R 批前就存在，行号偏移非新引入）；聚焦 device_gateway 套件 47 passed；全量 `pytest -q` → **4430 passed / 3 skipped / 2 deselected**（较 Q 批 4429 +1 = 新增特征化测试）。
- **下次**：git add/commit/push origin + CI Tests 实证 + 公网 4 测试冒烟。

## 2026-07-03 深度瘦身 Q 批完成（device_gateway profiles.py 约束施加抽离到 profile_constraints.py）

- **背景**：P 批闭环后代码尺寸门禁全过（0 个 >300 行文件、0 个 >50 行函数），粗粒度尺寸目标耗尽。换用更细发现手段：CodeGraph 孤儿审计（`context_compressor.py` 标 ORPHAN 但磁盘已不存在，数据库陈旧非真目标）+ Ponytail 台账（待处理项空）+ 行数逼近上限扫描。定位 `device_gateway/profiles.py` 295 行（距 300 上限仅 5 行）为最值得抽离目标——职责清晰分两层："profile 解析"（registry + `resolve_profile` + routing hints）与"约束施加到 task"（`apply_profile_constraints` + `_apply_approval_gate` + `_cap_param`）。
- **接缝核实**：`_apply_approval_gate`/`_cap_param` 零外部引用（纯私有，仅被 `apply_profile_constraints` 内部调用）；`apply_profile_constraints` 生产调用方 `task_creation.py` + `tasks.py`（后者从 `.task_creation` 再导出作 monkeypatch 面，无需改动），测试 2 文件；无 `getattr` 动态引用；唯一外部运行时依赖 `record_simplification`。7+1 个现有约束测试构成 REFACTOR 安全网。
- **抽离**：新建 `device_gateway/profile_constraints.py`（90 行纯函数模块），搬入 `apply_profile_constraints` + `_apply_approval_gate` + `_cap_param`；`ResolvedProfile` 仅在 `TYPE_CHECKING` 下导入规避循环引用（`profile_constraints` → `profiles` → `device_profile`，运行时无环）。从 `profiles.py` 删除 3 函数 + 2 个随之变死的导入（`json`、`record_simplification`，F401 全局门禁会拦），profiles.py 295→222（-73 行）。
- **调用方同步**：`task_creation.py` 导入源 `.profiles import apply_profile_constraints, resolve_profile` 拆为 `.profile_constraints import apply_profile_constraints` + `.profiles import resolve_profile`；2 个测试文件（`test_device_gateway_profile_constraints.py`、`test_device_gateway_profile_tasks.py`）同步导入源。
- **特征化测试**：新增 `test_apply_profile_constraints_lives_in_profile_constraints_module` 锁定新模块公开 API（`via_new_module is profile_constraints.apply_profile_constraints`），防回退。
- **门禁**：`ruff check` + `ruff format --check` 改动 5 文件 clean；`check_code_size.py` PASS（0 个 >300 行文件、0 个 >50 行函数）；`pyright` 改动 3 生产文件 0 errors（TYPE_CHECKING 循环引用规避成功）；聚焦 51 测试 GREEN（device_gateway_profile/ + route_policy_validation + route_resolution）；全量 `pytest -q` → **4429 passed / 3 skipped / 2 deselected**（较 P 批 4428 +1 = 新增特征化测试）。
- **下次**：git add/commit/push origin + VPS 部署 + 公网 4 测试冒烟。

## 2026-07-03 深度瘦身 P 批完成（本地 pre-commit 加 ruff format --check 守护 + 副 `_run` cwd 透传真 bug 修复）

- **范围**：O-3 暴露本地守护与 CI 不对称（CI 跑 `ruff format --check` 而本地只 `ruff check`），本批把 `ruff format --check` 加进本地 pre-commit 入口，并顺手清理首个守护启用即抓出的 2 处历史 format 漂移。
- **P-1 守护加固**：`scripts/run_ruff_check.py::run_ruff` 改为聚合 `ruff check` + `ruff format --check` 两次 subprocess，任一非零即阻塞、stdout/stderr 透传组合；docstring 说明来历（O-3 lesson）。commit `c16a4f9d` 含三条改动：(1) 守护脚本；(2) `deploy/jdcloud/deploy_jd.py` 长 URL 单行折多行（O-3 一样的长行漂移）；(3) `tests/device_gateway/test_ws_lifecycle.py` 长函数签名折多行参数。
- **P-2 副带 `_run` cwd 透传真 bug 修复**：P-1 push 后 CI 在新 commit 跑 `Type check changed Python files` 步骤，因 `deploy_jd.py` 被 diff 命中触发 pyright，发现 `deploy_jd.py:34 _run("sha256sum -c prometheus.sha256", cwd=INSTALL_DIR)` 传 `cwd=` 但 `_run` 函数签名只有 `check`、**`cwd` 被静默忽略**——`sha256sum -c` 实际是在错误工作目录跑，校验可能误判。这是潜伏已久的真 bug，CI pyright 才能暴露。commit `addee045` 给 `_run` 加 `cwd: Path | None = None` 参数并透传 `subprocess.run(..., cwd=cwd)`，pyright 0 errors。
- **意外教训**：CI pyright 步骤在「全 repo authority 文件」+「changed-files」双管齐下——authority 验证稳定模块，changed-files 兜底无 anchor 的零散工具脚本。本地没有 changed-files pyright，每次只在大改时一次检查；CI 是新改动后所有 touched 文件 pyright 跑一遍——是隐藏的"宽覆盖"扫描。今后工具脚本改动应本地手动跑 pyright（不只是 commits 守护范围）。
- **CI 实证**：
  - `c16a4f9d`：Tests workflow 失败（pyright on changed deploy_jd.py 抓出 cwd bug）。
  - `addee045`：Tests workflow success ✓、CodeQL success ✓；Deploy 仅失败（与本机本地部署环境有关，与代码无关，历次一直失败）。
- **门禁结果**：
  | 门 | 结果 |
  |---|---|
  | ruff check + ruff format --check 全 repo | clean |
  | 全量本地 pytest | 4428 passed 恒定 |
  | check_code_size | PASS |
  | pyright deploy_jd.py | 0 errors |
  | CI Tests workflow (commit addee045) | **complete success** ✓ |
  | CI CodeQL workflow (commit addee045) | success ✓ |

## 2026-07-03 深度瘦身 P 批完成（本地 pre-commit 加 ruff format --check 守护）

- **背景**：O-3 修复 CI 失败时 push commit `3fb7b145` 后再次失败，根因是本地 pre-commit 入口 `scripts/run_ruff_check.py` 只跑 `ruff check`，没跑 `ruff format --check`，本地 commit 时切片 spacing 漂移不被守门，要等 CI 才暴露。本批直接补这个缺口——避免下次再有 `ruff check` 全绿但 `ruff format --check` 失败、需要补 fix commit 的 retry 浪费。
- **改动**：`scripts/run_ruff_check.py::run_ruff` 在 `ruff check` 之后追加 `ruff format --check`，聚合两次结果（第一非零 returncode 即阻塞），stdout/stderr 透传。
- **立即价值实证**：加守护后第一次本地空 staging 跑 pre-commit，立即抓出 2 处早已该 format 的过时长行折行漂移：
  - `deploy/jdcloud/deploy_jd.py`：单行长 URL 折成括号多行。
  - `tests/device_gateway/test_ws_lifecycle.py`：长函数签名折成多行参数。
  本批顺手 ruff format 这 2 文件清掉历史 format 债。
- **门禁结果**：
  | 门 | 结果 |
  |---|---|
  | `ruff format --check .` 全 repo | 1361 files already formatted |
  | `scripts/run_pre_commit_check.py` 空 staging 模拟 | 全过（All checks passed + 1361 already formatted + git diff --cached --check）|
  | check_code_size | PASS |
- **教训**：CI workflow 与本地守护应该对称——同一套 ruff 命令在两端都跑，否则「本地绿 CI 红」会反复发生。O-3 是这一原则的反射案例：CI 跑 `ruff format --check` 但本地只跑 `ruff check`，本地看不见 spacing 漂移，每次破绿都需补 fix commit。守护脚本与 CI 步骤的命令集合应对齐 grep 验证。

## 2026-07-03 CI 修复 O 批（pyright authority-files 过时路径 + 工具清单同步）

- **O-1 修正 CI pyright authority-files 步骤**：见下方 O 批主条目（`routing_engine.py` → `routing_engine/__init__.py`）。
- **O-2 修隐藏的 ws_handshake Linux recv 丢首帧 bug**：O-1 push commit `9bfabae9` 后 CI 仍失败，但根因已从 pyright 转为 `test_websocket_handshake_succeeds_without_sec_websocket_version` 在 CI 上 assert `'bridge_connected' in '{"type": "wakeword_config", ...}'` 失败。排查发现 `_wakeword_integration_support.py::ws_handshake` 的 HTTP 响应读取 `sock.recv(1024)` 在 Linux 上会把 101 响应 + 后续 WebSocket 首帧（ready frame）合并到一个 recv 返回，buf 截取 `\r\n\r\n` 之前的字节只留 HTTP 头，**\r\n\r\n 之后的 ready 帧字节被静默丢弃**——之后 `ws_recv_text(sock)` 读到的是第二帧（wakeword_config）。本地 Windows 上 recv 不合并 chunk 不暴露此 bug；CI Linux 暴露。修复：`ws_handshake` 找到 `\r\n\r\n` 分隔符后，把 buf 中之后的所有 trailing bytes 挂到 `sock._wakeword_leftover` 属性；`ws_read_exact` 在 recv 前先 drain `_wakeword_leftover`。本地 8 focused + full 4428 passed 恒定；之后 CI 应转绿。
- **教训**：跨平台 recv 边界差异 —— Linux `recv(N)` 可以一次返回 N 字节（含尾部 frame），Windows 上 chunk 化更碎。手写 WebSocket/HTTP-over-socket 测试客户端在 `\r\n\r\n` 之后必须 drain leftover 到 WS read 层，否则会丢首帧。RFC6455 库自带处理但手写支持模块要自觉处理。

## 2026-07-03 CI 修复 O 批（pyright authority-files 过时路径 + 工具清单同步）

- **背景**：N 批把 `pypinyin==0.55.0` 加进 CI test.yml 后，push commit `0b3aeec6` 触发的 GitHub Actions **Tests workflow 失败**。经查 CI 日志根因**不是** F401 门禁或 pypinyin——F401 安全门（`pytest --collect-only OK`）与 `4395 passed, 17 skipped` 全绿，pypinyin 也让集测正常跑（skip 数下降），说明 K2+L+M+N 主体在远端 CI 全部通过。失败根因是 test.yml「Type check authority files」步骤硬编码 `pyright server.py routing_engine.py routes/chat_endpoints.py`，而 `routing_engine.py` 早已被抽离重构为 `routing_engine/` 包（`__init__.py` 为权威路由入口），CI 报 `File or directory "routing_engine.py" does not exist` exit code 4。
- **修复**：
  - `.github/workflows/test.yml`：`routing_engine.py` → `routing_engine/__init__.py`（本地 `pyright server.py routing_engine/__init__.py routes/chat_endpoints.py` 验证 0 errors）。
  - `scripts/repo_stats.py` KEY_FILES：`routing_engine.py` → `routing_engine/__init__.py`（原有 `path.exists()` 守护使其静默跳过，仅统计缺一行，非致命，但更正以恢复统计准确）。
  - `scripts/deploy_unified_common.py`：CORE_FILES + SLICE_FILES["phase_a"] 两处 `routing_engine.py` → `routing_engine/__init__.py`（注：core slice 实际用 `_collect_runtime_files()` 动态收集，不读这两个静态清单，故此前部署 888 files 一直成功不受影响；phase_a slice 极少用，更正防止将来误用）。
- **教训**：重构抽离单文件为包目录（`routing_engine.py` → `routing_engine/`）时，除代码 import 外还需 grep 全仓「裸文件名字符串引用」——CI workflow step、部署清单、统计脚本等把文件名当字符串硬编码的位置不会被 import 分析或 ruff 覆盖，只有真到 CI 才暴露。CodeGraph/ruff 都只追踪 import 级依赖，字符串级引用需 ripgrep 兜底。
- **验证**：本地 pyright authority 三文件 0 errors；ruff check clean；check_code_size PASS；全仓已无 `routing_engine.py` 裸字符串引用。

## 2026-07-03 深度瘦身 K2+L+M+N 四批合一完成（F401 全局门禁启用 + 闭环 + CI 同步）

- **范围**：K2 完成测试侧 fixture-(d) 注入型态文件的真死清理与自豁免释明；L 用 ruff --fix 一次性删除 tests/ 残留 86 个真死 F401；M 启用 ruff.toml 全局 F401 gate 同步删生产侧 17 个真死并 exclude 参考仓库；N 给 GitHub Actions test.yml 加 pin `pypinyin==0.55.0` 让 CI 也能跑 H1/I/J 集测。这四批本属同一主线，合并做一次 commit/import/push 避免分批文档碎化。
- **K2 细项**：
  - `test_device_app_sharing.py`：删 `accept_share`（body 内 0 调用，真死），保留 `client`（fixture）/`seed_guest`（活跃函数）→ `client` 加 `# noqa: F401  pytest fixture injected via parameter name (d)`。
  - `test_device_app_sharing_permissions.py`：删 `seed_guest`（body 0 调用），保留 `accept_share`（活跃函数 `accept_share(client, "view")`）+ `client`（fixture）→ `client` 加同样 noqa。
  - `test_fake_u1_cloud_home.py`：先误删 `fake_u1`（pytest 错：`fixture 'fake_u1' not found`，证明 `fake_device_server` fixture 在 helper 中**依赖 `fake_u1` 作为 fixture 参数**——fixture 间接依赖链式发现，import 名即使不显式标注也必须存在）；回滚补回 `fake_u1`，3 个 fixture 名都加 noqa + 注释「transitively required (fake_device_server depends on fake_u1)」。
  - `test_fake_u1_cloud_draw_svg.py`/`rejection.py`/`write_text.py` 三文件 fixture 链路保持，3 个 fixture 名加 noqa 自豁免释明。
  - **新教训**：F401 fixture (d) 注入型态不止「直接 fixture 参数名注入」一种，还有「fixture 间接依赖 fixture 链」型态 —— 即 `import fake_u1` 即使测试函数签名没用到，只要 helper 模块下别的 fixture `def fake_device_server(fake_u1)` 依赖 `fake_u1`，import 名仍必须保留以让 pytest resolve fixture 依赖图。这是 G1b 四型态之外的第 (e) 型态。
- **L 细项**：写一次性审计脚本 `_tmp_f401_audit.py`（已删）逐 F401 名 grep body 是否真用，发现 86 个 ruff F401 中 80 安全 + 6「risky」实际都是误报假活——`pytest` 在 `"pytest"` 字符串字面量/`command[:6] == ["py", "-m", "pytest"]` 比较里命中，`json` 在 httpx keyword argument `json={...}` 命中，`asyncio` 在 `@pytest.mark.asyncio` 装饰器里命中（**不是 asyncio 模块本身用法**），`http.client` 在 docstring "WebSocket client" 里命中注释字符串，`sys` 在 `via sys.modules` 注释里命中。全部可 `ruff --fix` 安全清理。focused 7 文件（risky 集中所在的）跑 64 passed，全量 4428 passed 恒定不变。
- **M 细项**：
  - `ruff.toml` `select` 加入 `"F401"`；`exclude` 加入 `"reference/**"`（按 AGENTS.md「禁止暂存参考仓库」原则，reference/grbl_fix/ 5 个 F401 故意不动）。
  - 生产侧剩余 17 真死（lima_mcp_stdio 3 + packages/browser_lifecycle 1 + scripts 12 + reference 排除后 1）由 `ruff --fix` 安全删除。
  - `ruff --fix --select F401 .` 副作用：ruff format 顺手规范化了 23 个生产 / tests 文件（EOL 缺尾 newline / 二空行 / Optional[X]→X|None 等早已该过的格式化），与 G1b 后周期 format 应该早已做过，本批一并清掉。这是合理的 silent 升级，无运行时影响。
- **N 细项**：`.github/workflows/test.yml` install 步加 `pip install pypinyin==0.55.0`，与 `data/digital-human/wakeword_runtime/requirements.txt` 同 pin。让 CI executor 跑 H1/I/J 的 wakeword 集成测试时不再被 `pytest.importorskip("pypinyin")` 跳过。
- **门禁结果**：
  | 门 | 结果 |
  |---|---|
  | ruff check . | All checks passed |
  | ruff format --check | 1350 files already formatted |
  | --select F401 全 repo | All checks passed（gate 启用后立刻验证）|
  | check_code_size | PASS |
  | pyright（修改的 lima_mcp / packages / scripts 文件） | 0 errors（8 pre-existing warnings 与本批无关）|
  | focused pytest（risky 集中所在 7 文件）| 64 passed |
  | full pytest | 4428 passed, 3 skipped, 2 deselected, 1 warning（恒定）|
- **里程碑**：F401 全局门禁启用，从 G1b 提出的「四型态具名失效」原则到现在 K2+L+M+N 的全主线闭环（剩 ~6 个文件 fixture (d)/(e) 注入型态靠 `# noqa: F401` 自豁免释明），下一步 TDD 抽离批次会有 ruff 全 repo F401 0 报告做 baseline 守护，不再有 F401 静默死代码潜逃空间。

## 2026-07-03 深度瘦身 K 批次完成（测试侧 mixed 桶 10 文件 39 个真死 imported-name 逐文件清理）

- **范围**：继 G1b 测试侧 F401 STYPE_CLEAN 全过清理后，本批推进 mixed 桶 —— 即单文件内同时含 port-target 保留名 + domain 死名的混合型，需逐名判定。审计 agent 报告 mixed 桶 10 文件 / 39 imported-name，但 agent 归桶不可全信（fake_u1_cloud 4 文件的 `fake_device_server`/`fake_u1`/`lima_client` 被其归为「domain dead」实则是 G1b 已记录的 pytest fixture 字符串匹配注入 (d) 型态 —— 在测试函数签名作为参数名出现的 fixture，pytest 收集期注入、ruff 看不见，删了会 18 ERROR 复现）。**本批改用每文件 Read+grep 亲自验证每个 imported-name 的真实使用**，最终锁定 10 文件 / 39 个真死 + 2 个补漏（test_device_attestation.py 的 `os` 与 `verifier as attestation_verifier`）：  - 注：`attestation_verifier` 字符串出现在 `monkeypatch.setattr(handlers, "attestation_verifier", ...)` 但这是属性名字符串而非模块别名引用，handlers 自己有该 attr，本文件 import 不被引用，删安全。
- **逐文件结果**：
  - `test_chat_ide_golden_path.py`：删 `asyncio/json/ChatRequest/Message`（保留 `tempfile/Path/pytest` + `@pytest.fixture`）
  - `test_device_attestation.py`：删 `AttestationResult`、`attestation_failed_frame`、`attestation_warning_frame`、`os`、`verifier as attestation_verifier`（共 5 — 比 plan 多 2 个补漏）
  - `test_health_state_persistence2.py`：删 `os/tempfile/patch/_cooldown_states`（4）
  - `test_ops_metrics_backends.py` / `test_ops_metrics_eval.py` / `test_ops_metrics_payload.py` 三文件同模式删 `builtins/importlib/threading/pytest/server/reload_prometheus_metrics`（共 18）
  - `test_provider_automation_model_entry.py`：删 `pytest`，删 `from provider_automation_helpers import entry` —— 因文件内 `entry = ProviderModelEntry(...)` 局部变量 100% 遮蔽 import 模块，从未引用模块，属「局部变量遮蔽 import」新形态（2）
  - `test_provider_automation_snapshot_store.py`：删 `pytest` + `entry`（2）
  - `test_rate_limiter.py`：删 `time` + `_keyed_requests`（2）
  - `test_routes_admin_api.py`：删 `MagicMock` + `admin_auth`（2，保留 `patch`/`@pytest.fixture`/`json` 等活跃名）
  - 合计 39 个真死 imported-name 删除（37 plan + 2 补漏）
- **不动文件**：fake_u1_cloud 4 文件 + test_device_app_sharing 2 文件 = 共 6 文件的「domain dead」bucket — 它们实为 (d) pytest fixture 字符串匹配注入型态，删了会复现 18 ERROR，留待 K2 批（或永久保留 `# noqa: F401` 自豁免）。

### 门禁结果

| 门 | 结果 |
|---|---|
| focused pytest（10 修改文件） | 78 passed, 0 ERROR / 0 fail（明确证明 fixture 注入 + @pytest.mark 都未被误删）|
| full pytest | 4428 passed, 3 skipped, 2 deselected（不变，删死代码不动运行时）|
| ruff check --select F401（10 文件）| 0 报告 |
| ruff check + format | clean |
| check_code_size.py | PASS |
| pyright（10 文件） | 0 errors |

## 2026-07-03 深度瘦身 J 批次完成（唤醒词握手层抽离到 accept_websocket_upgrade 纯函数）

- **范围**：继 I 批次把 `TestRuntimeHandler` 闭包类抽到模块级 `build_handler_class` 工厂后，本批进一步把 `_handle_websocket` 内紧耦合到 `SimpleHTTPRequestHandler` 实例 API 的 RFC6455 握手协议（Upgrade 头校验 → send_error / Sec-WebSocket-Key 校验 → compute_accept → 101 + 3 响应头 → end_headers）抽到模块级 `accept_websocket_upgrade(handler) -> tuple[Any, Any] | None` 纯函数接缝。`_handle_websocket` 收缩到 ~9 行「调 accept → None 则 return → 委托 websocket_session」三行接缝。同时兑现 I 批次 plan 遗留：补一个 Sec-WebSocket-Version 不校验的契约特征化测试。

### J-1 RED — Sec-WebSocket-Version 不校验契约特征化测试

- **`tests/_wakeword_integration_support.py::ws_handshake` 加 `include_version: bool = True` 参数**：默认 True 行为不变（既有 5 个 happy-path 调用方不动）；False 时跳过 `Sec-WebSocket-Version: 13` 头的发送，模拟「无 Version 头」的客户端。
- **`tests/test_wakeword_session_integration.py` 234→249 行**：追加 `test_websocket_handshake_succeeds_without_sec_websocket_version`——用 `ws_handshake(port, include_version=False)` 触发握手，断言仍能 101 + drain greeting 等于 bridge_connected ready frame。把潜在改进点「未来引入 Version 13 严校验」显式化为契约——若将来收紧校验，此测试会变红，由改 PR 显式决策契约方向。全套 8 passed（7 原有 + 1 新增）。

### J-2 REFACTOR — 模块级 accept_websocket_upgrade 抽离

- **`data/digital-human/wakeword_runtime/runtime/http_server.py` 170→187 行**：新增模块级 `accept_websocket_upgrade(handler)`——duck-typed 用 handler 的 `.headers.get / .send_response / .send_header / .end_headers / .send_error / .connection / .wfile` 七个实例 API；`_handle_websocket` 原本 >20 行的握手协议就压缩到 ~9 行接缝（`upgraded = accept_websocket_upgrade(self)` → `None 则 return` → `reader, writer = upgraded` → `serve_websocket_session(...)`）。顶部 ponytail docstring 更新为「握手协议已抽到模块级 accept_websocket_upgrade 接缝函数；升级路径 = wsproto 上握手层一并下沉」。

### 门禁结果

| 门 | 结果 |
|---|---|
| focused pytest（3 文件） | 30 passed（I 批 29 + J 新增 1）|
| full pytest | 4428 passed, 3 skipped, 2 deselected, 1 warning（恰好 +1 = 4427→4428）|
| ruff check | All checks passed |
| ruff format | 3 files already formatted |
| check_code_size.py | PASS |
| pyright（修改文件） | 0 errors |

## 2026-07-03 深度瘦身 I 批次完成（唤醒词 http_server 类工厂抽离 + 握手错误路径特征化测试）

- **范围**：继 F2/G2/H1 唤醒词 runtime 渐进抽离后，本批做两件事 —— (1) RED 特征化：补 `_handle_websocket` 握手 BAD_REQUEST 两分支（无 Upgrade、无 Sec-WebSocket-Key）的端到端覆盖，前者此前完全未测；(2) REFACTOR：删除 F2/G2/H1 抽离后残留的 7 个死 wrapper 方法（`_build_wakeword_config_message`/`_handle_bridge_request`/`_save_wakeword_config`/`_receive_websocket_message`/`_read_exact`/`_send_websocket_text`/`_send_websocket_frame`，全仓零调用方，已 Explore `self._<method>` 审计确认），并把 `_build_server` 内嵌 `TestRuntimeHandler` 闭包类抽出到模块级工厂函数 `build_handler_class(test_root, event_bridge, schedule_restart) -> type[SimpleHTTPRequestHandler]`，与三个姐妹模块（`frame_codec` / `bridge_request_handler` / `websocket_session`）「模块级纯函数」风格对齐；`_build_server` 收缩为调用工厂构造 handler 类。顺带精简 `frame_codec` from-import 为只引入实际使用的 `compute_accept / receive_message / send_text`（删了 `read_exact / send_frame` 两个仅由已删 wrapper 引用的名字）。

### I-1 RED — 握手错误路径特征化测试

- **`tests/test_wakeword_session_integration.py` 196→234 行**：追加 2 个 http.client 直发测试 —— `test_websocket_handshake_rejected_without_upgrade_header`（裸 GET /wakeword-ws 无 Upgrade → 400 + `expected websocket upgrade`）、`test_websocket_handshake_rejected_without_sec_websocket_key`（有 Upgrade 无 Sec-WebSocket-Key → 400 + `missing Sec-WebSocket-Key`）。特征化测试（非新功能），立即全过锁定现有契约，为下一步类工厂抽离提供回归网。
- 全套 7 passed（5 原有 + 2 新增）。

### I-2 REFACTOR — 死代码清除 + 类工厂抽离

- **`data/digital-human/wakeword_runtime/runtime/http_server.py` 164→170 行**：结构维度看是「微增」（类工厂从闭包抽到模块级多了 `return TestRuntimeHandler` 与签名 6 行），但删除了 18 行死 wrapper（7 个 delegator 方法），净行为代码 ↓。模块顶部新增 ponytail docstring：上限 = 握手仍强依赖 SimpleHTTPRequestHandler 实例 API；升级路径 = 换 wsproto/starlette 后握手层一并下沉。
- **行为不变性证据**：focused 29 passed（7 集测 + 16 frame_codec + 6 bridge_request），full `4427 passed, 3 skipped, 2 deselected`（恰好 +2 = 4425→4427），check_code_size PASS（无 >300 文件、无 >50 函数），ruff check + format 全过，pyright 待跑。

### 门禁结果

| 门 | 结果 |
|---|---|
| focused pytest（3 文件） | 29 passed |
| full pytest | 4427 passed, 3 skipped, 2 deselected, 1 warning（仅 PytestCollectionWarning 不影响）|
| ruff check | All checks passed |
| ruff format | 2 files already formatted |
| check_code_size.py | PASS |
| 公网冒烟（待部署后跑） | 见下文 |

## 2026-07-03 深度瘦身 H1+H2 批次完成（F401 安全门工具化 + 唤醒词 WebSocket 会话抽离 + 端到端集成测试）

- **范围**：H2 把 G1b 四型态 lesson learned 永久固化为 pre-commit 安全门；H1 以 TDD 方式补 wakeword HTTP/WebSocket 端到端集成测试，再抽离 `_handle_websocket` 事件循环。

### H2 — 测试侧 F401 安全门工具化（pre-commit 集成）

- **新建 `scripts/testside_f401_safety_gate.py`**：当 staged 文件含 `tests/*.py` 时触发 `python -m pytest --collect-only -q`，收集失败按 ERROR 行解析失败文件、跳过 `--baseline-skip-from` 已知旧债后打印四型态提示 + 收集尾 30 行 triage + 返回非零阻止提交。设计要点：(1) tests/ 子树前缀判定；(2) `--baseline-skip-from` 渐进清理豁免旧债；(3) main() 经 `_build_argparser()` + `_print_blocked()` 拆分每函数 ≤50 行通过 check_code_size；(4) 集成入 `run_pre_commit_check.py` 的 `run_testside_f401_safety_gate()`，置于其他快速检查后、`--full` pytest 前。
- **10 个 gate 单测验证纯 helper 行为**（path 过滤 / ERROR 行解析 / baseline 过滤 / main 早早返回路径），不调用 pytest 本身避免依赖。

### H1 — wakeword WebSocket 会话抽离 + 端到端集成测试（TDD）

- **新建 `tests/test_wakeword_session_integration.py`**（193 行）+ 辅助 `tests/_wakeword_integration_support.py`（191 行，`_` 前缀导致 pytest 不收集）：用 importlib + sys.modules alias package（`wakeword_runtime_pkg.{runtime,bridge}` 合成包）让 hyphen 路径 `data/digital-human/...` 可导入；fixture 在 ephemeral port 0 起 TestRuntimeHttpServer + seed `wakeword_runtime/{config.json,models/keywords.txt}`；测试驱动 raw socket + http.client + 手写 RFC6455 client handshake 跑 `/health`、握手 Ready 帧、`set_wakeword_config` round-trip、restart、unknown type fallback 五例，全端到端验证 codec + bridge_request_handler + wakeword_config + websocket_session 真实运行时路径。`pytest.importorskip("pypinyin")` 保证外部依赖缺失环境跳过集测不挂 suite。
- **REFACTOR：新建 `data/digital-human/wakeword_runtime/runtime/websocket_session.py`**（99 行纯函数模块）`serve_websocket_session(reader, writer, bridge, test_root, schedule_restart, send_text_writer, receive_reader_writer)`——把 `_handle_websocket` 内嵌 46 行事件循环体（post-handshake 的 client_queue.add → greeting → 双向轮询 → finally remove）抽出。http_server 仅保留 HTTP/WebSocket 握手（强 self.send_response/headers 依赖），178→164 行。沿用 frame_codec/bridge_request_handler 模式：`handle_bridge_request` 与 `build_wakeword_config_message` 顶层属性链入由 http_server.py import 后 setattr 真实实现，测试可 setattr fake。**集成测试在抽离前后全过**，证明运行时行为不变；了结 G2「`_handle_websocket` 仍需先补端到端测试」遗留。
- **新增 ponytail 标记条目**：`wakeword_runtime/runtime/websocket_session.py:3`——不依赖 self/Handler instance，仅覆盖唤醒词 runtime 实际两段交互（greeting + 双向消息循环），未做 per-message 流控/重试扩展；升级路径为换用 wsproto 的 frame iterator + asyncio queue 实现更复杂流控。
- **环境寄存**：`pypinyin==0.55.0` 已 `pip install` 入 `.venv310`（与 `wakeword_runtime/requirements.txt` pin 一致）使 H1 集成测试可正常运行；后续 CI 环境（京东云 / 别处执行器）需同步 pin pypinyin 才能让 H1 集测可跑。

### 门禁（全绿）

- `ruff check .` clean；`ruff format --check` clean（仅格式化本批新增/修改的 H1/H2 6 文件）。
- `scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50；H2 脚本 main() 73 行经 `_build_argparser` + `_print_blocked` 拆分后通过；新集测首版 383 行超 300 经拆 `tests/_wakeword_integration_support.py` 191 行后双双 ≤300）。
- `pyright` 本批 4 个相关文件 0 errors 0 warnings。
- 全量 `pytest --tb=short -q` → **4425 passed / 3 skipped / 2 deselected / 0 failed**（较 G1+G2 的 4410 +15 = H2 +10 gate 单测 + H1 +5 集测）。

### 下次

VPS 部署 + 公网冒烟 + commit/push（本批已落 progress）→ 仅暂存里程碑文件 → conventional commit。后可选：测试侧剩余 ~143 mixed/keep-infa F401 逐文件人工核对（现可借助本批 H2 安全门验证）；wakeword `http_server._build_server` 整体嵌套类抽离（仍需更端到端 WebSocket 集测锚点 + swing 测试）；F401 全局门禁启用（待测试侧 mixed 清理完）。

## 2026-07-03 深度瘦身 G1+G2 批次完成（台账销账 + 测试侧 F401 精选 + 唤醒词桥接请求抽离）

- **范围**：G1 台账销账 + 测试侧 F401 精选（仅 domain dead imports，KEEP port-target infra，沿用 F1 双向别名安全审计教训但因属于 test/side 这边再加一层 sys.path 根基名前缀校验）；G2 TDD 抽离 wakeword `_handle_bridge_request` 到 `bridge_request_handler.py`。

### G1a — PONYTAIL-DEBT 销账陈旧条目

- `check_code_size.py 残留 12 个 51-54 行函数`条目经独立 AST 扫描（51-55 行范围全仓非排除目录 0 命中）确认陈旧，从「当前标记」区删除并补「已结清」记录。无代码改动。

### G1b — 测试侧 F401 精选清理

- **基线**：测试侧 ~202 处 F401（多为 `pytest`/`os`/`time`/`unittest.mock`/`patch` 等 patch-target / 隐式 fixture 用法，曾导致 85 收集错误）+ scripts/lima_mcp_stdio 数处。本批**只删 STYPE_CLEAN 文件中 AST 与 ruff 双确认的 domain dead imports**（`device_voice.exceptions.{AuthenticationError,ConfigurationError,VoiceProviderError}`、`device_gateway.attestation.*`、`client_keys.models.ClientKey`、`chat_models.{ChatRequest,Message}` 等业务符号），**保留** port-target infra（`pytest/os/patch/MagicMock/...`）。
- **STYPE 分类**：49 个 STYPE_CLEAN 文件（safe-only）经 F1 别名感知审计全过 0 danger，逐文件 `ruff check --fix` 移除共 84 处 domain dead imports，剩余 143 处为 KEEP-infra + mixed 文件，留待后续单独批逐文件人工核对。
- **二轮审计盲点 + 修复**：审计脚本默认 `module == file_dotted_path` 严格相等（`tests.fake_u1_helpers`），但 pytest 通过 `conftest.py` 把 `tests/` 加到 `sys.path`，消费者写 `from fake_u1_helpers import motion_task_to_u1_commands`（前缀基名）。`tests/fake_u1_helpers.py` 经 `--fix` 误删了 `motion_task_to_u1_commands` 后，下游 `test_fake_u1_protocol_translation.py` 收集失败。修复：恢复该 import 并附 `# noqa: E402,F401` 说明 re-export。教训：F2 提炼的「别名访问」具名失效风险 + 加上「pytest 测试间 sys.path 根基名引用」更隐蔽，下一轮测试侧 F401 批必须同时考虑这两类前缀。
- **附带收益**：scripts/、lima_mcp_stdio/、packages/ 内 4 处清理后整体整洁度小幅提升。

### G2 — wakeword 桥接请求 handler 抽离（TDD）

- **目标**：把 `http_server.py` 嵌套类 `_handle_bridge_request`（44 行内联、捕获 `test_root`/`schedule_restart` 闭包）抽出为纯函数模块，便于单测。
- **RED 先行**：新建 `tests/test_wakeword_bridge_request.py`（importlib.spec_from_file_location 加载），6 个测试覆盖：`invalid_json_returns_None`、`set_wakeword_config_success_publishes_and_returns_result`（含 fake save_wakeword_config 注入验证 publish + build_message 契约）、`set_wakeword_config_save_exception_returns_failure_result`（成功即降级路径 success=False + error 描述）、`restart_wakeword_service_invokes_schedule_restart`、`unknown_message_type_returns_failure_result`、`empty_message_type_uses_fallback_result_type`。RED：FileNotFoundError（bridge_request_handler.py 不存在）。
- **GREEN：新建 `data/digital-human/wakeword_runtime/runtime/bridge_request_handler.py`（121 行纯函数模块）**实现 `handle_bridge_request(bridge, raw_message, test_root, schedule_restart)` + 2 个 helper (`_handle_set_wakeword_config`、`_handle_restart`)。**关键解耦**：`save_wakeword_config` 不在模块顶层 from-import（否则 importlib 加载本模块因无父包相对导入失败），改为顶层 `save_wakeword_config: Any = None` + `_resolve_save()` 延迟相对导入兜底；http_server.py 在 import 后 `bridge_request_handler.save_wakeword_config = save_wakeword_config` 显式链入真实实现，测试用 `monkeypatch` / `setattr` 注入 fake。`WakewordEventBridge` 类型注解改 `Any`（duck-typed，契合 docstring），避开 F821。
- **REFACTOR：`http_server.py` 213 → 178 行**：`_handle_bridge_request` 改 1 行委托到 `bridge_request_handler.handle_bridge_request(bridge, raw_message, test_root, schedule_restart)`；`_handle_websocket` 事件循环与 `_build_wakeword_config_message`/`_save_wakeword_config` 简单委托不动。**闭包依赖 `test_root`/`event_bridge`/`schedule_restart` 与事件循环主逻辑仍保留在 `_build_server` 嵌套类中**（46 行 `_handle_websocket` 仍 tight coupling with `client_queue`，需先补端到端集成测试再考虑拆分）。
- **新增 ponytail 标记条目**：`bridge_request_handler.py:3` —— 顶层属性而非 from-import 避开 importlib 无父包相对导入失败；上限是测试必须改本属性才生效（生产代码也走同一通路）；升级路径待后续 bridge 内部状态机复杂化时改为依赖注入。连同 G1 已结清的 codec 上限，wakeword runtime 三个抽离粒度（codec / config / bridge_request）均与 Ponytail 阶梯一致。

### 门禁（全绿）

- `ruff check .` clean；`ruff format --check` clean（仅格式化本批新增/修改的 4 个 G2 文件 + 7 个 G1b 测试文件因 --fix 后 ruff format 建议合并括号）。
- `scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50）。
- `pyright` 对 `bridge_request_handler.py`、`http_server.py`、`tests/fake_u1_helpers.py` 0 errors 0 warnings。
- 全量 `pytest --tb=short -q` → **4410 passed / 3 skipped / 2 deselected / 0 failed**（较 F1+F2 的 4404 +6 = G2 新增 6 个 bridge_request 测试）。

### 下次

VPS 部署 + 公网冒烟 + 文档同步（progress/STATUS/findings/PONYTAIL-DEBT，本条已落 progress）→ 仅暂存里程碑文件 → conventional commit → push `origin/main`。可选后续：测试侧剩余 ~143 mixed/keep-infra F401 处逐文件人工核对；wakeword `_handle_websocket` 事件循环抽离（需先补端到端 WebSocket 集成测试）；F401 全局门禁。

## 2026-07-03 深度瘦身 F1+F2 批次完成（死导入清理 + 唤醒词 WebSocket 帧编解码抽离）

- **计划基线**：接续 E6-E9，本批经两轮实施修正后闭环。范围：F1 生产路径 F401 死导入清理（低风险）+ F2 wakeword WebSocket 帧编解码抽离（中风险，TDD: RED→GREEN→REFACTOR）。F3（test_jdcloud_push_probe.py 贴顶下移）经尝试后回退，跳过。

### F1 — 生产路径 F401 死导入清理（精选策略，非盲跑 `--fix`）

- **基线**：`ruff --select F401` 全库 341 处，其中测试侧 ~253 处多为 patch-target 导入（曾导致 85 个收集错误），本批**只动生产侧**，不动测试侧。
- **两轮安全审计**：
  - **第一轮（仅扫测试 `from <module> import <name>` 与点号 `<module>.<name>`）**：识别出 9 个 re-export 必须保留：`http_stream.StreamIdentitySanitizer`、`health_state.{save_health_state,load_health_state,save_on_change}`、`budget_manager.reset_token_usage`、`device_gateway.path_pipeline.MAX_PATH_POINTS`、`device_voice.providers.asr_composite.{AliyunASRProvider,DashScopeASRProvider,WhisperASRProvider}`。
  - 针对上述 9 项标注 `# noqa: F401` 后，对每个生产文件单独 `ruff check --fix <file>`，清除真正无用导入。
  - **首跑 pytest 出现 12 failed / 22 errors**：根因是 `server_bootstrap.MODEL_ID`（被 `server.py` 生产侧 `from server_bootstrap import MODEL_ID` 重新引用）与 `routes/device_gateway.{_reset_for_tests,start_device_gateway_runtime,stop_device_gateway_runtime}`、`routes/admin_api.{BACKENDS,add_backend,has_backend,remove_backend,_is_safe_backend_url,test_backend_sync}`、`health_state.flush_pending_save`、`xiaozhi_drawing.text_to_path.list_handwriting_fonts` 这些 re-export 是经**模块别名访问**（`from routes import device_gateway as dg` → `dg._reset_for_tests()`；`import routes.admin_api as _a` → `_a.BACKENDS`；`import health_state as hs` → `hs.flush_pending_save()`；`from xiaozhi_drawing import text_to_path` → `text_to_path.list_handwriting_fonts()`），第一轮纯文本扫描漏检。
  - **第二轮（别名感知 AST 审计，覆盖未改文件）**：补出 9 个 must-keep re-export，全部用 `# noqa: F401` 标注恢复后门禁转绿。
- **教训**：模块别名（`import M.sub as A` / `from pkg import sub` 类）会把 re-export 的使用方从源模块的全名变成短别名，纯文本 `<module>.<name>` 正则无法覆盖。安全审计必须包含「别名绑定 → 别名点号访问」双向解析，且要扫全仓未改文件，不只 `tests/`。单测「import 一次 = 可被 patch」不是高危机型态；「re-export 被下游模块别名访问」才是更高危型态且更隐蔽。
- **统计**：本批共清理生产路径 F401 ~97 处（91 真死导入删除 + 17 用 noqa 保留的 re-export）。剩余 F401 仅测试侧 ~253 处，留待后续单独批逐文件人工核对。
- **近顶文件收益**：`routes/device_gateway.py` 291 → 283 行（远离 300 上限）；`routes/admin_api.py` 167 → 175 行（恢复 re-export）；`health_state.py` 115 → 119 行；`http_stream.py` 行数微降；`server_bootstrap.py`、`budget_manager.py`、`xiaozhi_drawing/text_to_path.py` 行数稳定。

### F2 — wakeword WebSocket 帧编解码抽离（TDD）

- **目标**：把 `data/digital-human/wakeword_runtime/runtime/http_server.py` 中 210 行嵌套类 `_build_server.TestRuntimeHandler` 内嵌的手写 WebSocket 帧函数抽出为纯函数模块，便于单测。
- **RED 先行**：新建 `tests/test_wakeword_frame_codec.py`（importlib.spec_from_file_location 加载，避开 `digital-human` 连字符路径不可直接 import 的问题），16 个测试覆盖 `compute_accept`（RFC6455 范例向量）、`read_exact`（短 EOF 抛 ConnectionResetError / 0 长度）、`receive_message`（unmasked/masked 解掩码 / ping 自动 pong / close 抛 ConnectionAbortedError / pong 忽略 / 未知 opcode 忽略 / 126 扩展长度 / 空载荷）/ `send_frame` + `send_text`（<126 / 126 / 127 三种长度编码）/ round-trip。RED 阶段：FileNotFoundError（frame_codec.py 不存在）。
- **GREEN：新建 `data/digital-human/wakeword_runtime/runtime/frame_codec.py`（118 行，纯 stdlib，无 relative import，避免 hyphen 路径）**，实现 `compute_accept`/`read_exact`/`receive_message`/`send_frame`/`send_text` 五个纯函数，新增模块头 ponytail 注释说明上限（仅 RFC6455 最小帧子集，无分片/RSV）与升级路径（换用 wsproto）。16 个测试全过。
- **REFACTOR：`http_server.py` 274 → 212 行**：导入改为 `from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text`，移除 `base64`/`hashlib` 顶层导入；嵌套 `_handle_websocket` 内的 accept 计算改为 `compute_accept(websocket_key)`；嵌套类内 4 个方法 (`_receive_websocket_message`/`_read_exact`/`_send_websocket_text`/`_send_websocket_frame`) 委托 frame_codec。**闭包依赖 `test_root`/`event_bridge`/`schedule_restart` 与 `_handle_websocket` 事件循环主逻辑不动**，仅 codec 抽离；WebSocket 帧读写仍由 `self.connection`（reader）/`self.wfile`（writer）传递，运行时行为不变。
- **新增 ponytail 标记条目**：`wakeword_runtime/runtime/frame_codec.py:3` —— pypinyin 上限已于 E8 记录；本 codec 上限「仅实现 RFC6455 最小帧子集（无分片/无 RSV）」于模块头记录，升级路径为换用 wsproto。

### F3 — test_jdcloud_push_probe.py 贴顶下移（跳过）

- 300 行贴顶的测试文件，尝试提取 `monkeypatch_post` shared-fixture 把 3 处 `monkeypatch.setattr(push_probe_results, "_post_payload", ...)` 合并：实测反而增至 305 行（fixture 定义净增 11 行，仅每个 test 删 3 行），未达瘦身目标。**回退**保持 300 行现状（贴顶但未破门禁，符合 ≤300 限额）。下次若需进一步降行，可用更紧凑的 fixture + 函数尾部断言合并，或重排测试以合并相似前缀，但收益微小，优先级低。

### 门禁

- `ruff check .` clean；`ruff format --check` clean（仅格式化本批改动的 4 个 routes 文件，不触碰既有 10 个 pre-existing format-dirty 文件如 `device_gateway/device_draw_config.py`、`provider_inventory/mcp_registries.py`、`xiaozhi_drawing` 三件套等，避免污染 diff）。
- `scripts/check_code_size.py` PASS（0 个 >300 行文件、0 个 >50 行函数）。
- `pyright` 对本批改动的 8 个生产文件 0 errors（仅 `routes/device_gateway.py` 2 个与 F1 无关的既有 JSONResponse.get 误警，与 HEAD 相同）。
- 全量 `python -m pytest --tb=short -q` → **4404 passed / 3 skipped / 2 deselected / 0 failed**（较 E6-E9 的 4388 +16，与 F2 新增 16 个 frame codec 测试一致）。

### 下次

VPS 部署 + 公网冒烟 + 文档同步（progress/STATUS/findings/PONYTAIL-DEBT，本条已落 progress）→ 仅暂存里程碑文件 → conventional commit → push `origin/main`（Gitee 已退役，不双推）。后可选提案：测试侧 F401 ~253 处单独批逐文件人工核对、PONYTAIL-DEBT `check_code_size.py` 残留 12 个 51-54 行函数 consolidate、wakeword http_server 内 `_build_server` 嵌套类整体抽离（需先补端到端集成测试）。

## 2026-07-02 深度清理：未跟踪源文件入库 + .gitignore 补全 + 临时文件清理

### 执行内容

1. **恢复未跟踪但被引用的源文件**：
   - `xiaozhi_drawing/pipeline.py` — 从 `__pycache__/*.pyc` bytecode 重建；绘图管道架构（PipelineConfig / PipelineContext / 5 阶段）
   - `xiaozhi_drawing/hershey_font.py` — Hershey 单笔画字体渲染器，从 bytecode 签名 + 测试契约重建
   - `xiaozhi_drawing/hershey_font_data.py` — 85 字符的 GLYPHS 字典，从 .pyc 导出为 JSON 并改为运行时加载（.py 仅 22 行）
   - `xiaozhi_drawing/hershey_font_data.json` — 字体数据 JSON 文件

2. **.gitignore 补全**：
   - 新增 `.omk/`、`.hypothesis/`（Agent 工具产物，2685 文件 / 1MB）
   - 新增 `.tmp_ci_*.log`（临时 CI 日志模式）
   - 清理已存在的 `.tmp_ci_after_fix.log`、`.tmp_ci_repro.log`、`.coverage`

3. **归档文件入库**：
   - `docs/archive/progress-2026-06.md` — progress.md 截断迁移的历史归档
   - `docs/archive/status-log-2026-06.md` — STATUS.md 截断迁移的历史归档

4. **F401 评估结论**：
   - ruff F401（未使用导入）全局扫描发现 330 个；自动修复导致 85 个测试收集错误
   - 原因：代码库大量使用 re-export 模式（facade 模块导入后供其他模块引用）
   - 结论：F401 需逐文件手动审查，不适合自动批量修复；保持当前 ruff select 不含 F401

### 验证

- `pytest --tb=short -q` → **4391 passed, 3 skipped, 0 failed**
- `ruff check .` → All checks passed
- `scripts/check_code_size.py` → PASS

## 2026-07-02 瘦身计划 P0-1/P0-5/P1-11 批量清理

### 背景

瘦身设计文档中 P0/P1/P2 项大部分已完成。本轮清理剩余 3 项。

### 改动

1. **P0-1: 删除 U1 固件 85MB node_modules**：`esp32S_XYZ/firmware/u1-grbl/embedded/node_modules/` 未被 git 跟踪（0 tracked files），物理删除 85MB 并在子模块 `.gitignore` 中添加排除规则。
2. **P0-5: 标记 Telegram bot DEPRECATED**：`integrations/telegram_bot/client.py` 和 `__init__.py` 顶部添加 DEPRECATED 标记，明确通知通道已退役、仅 gallery 存储仍依赖。不删除代码（gallery 活跃依赖）。
3. **P1-11: 添加 docs/archive/ README**：新建 `docs/archive/README.md`，说明归档规则（仅文档、不修改内容、定期审查）和目录索引。archive 中已无 .py 文件（BACKLOG-P1-3 已清理）。

### 验证

- gallery/telegram 相关 30 tests passed
- `ruff check` clean；pre-commit 全绿
- `check_code_size.py` PASS

### Git

- 子模块 `esp32S_XYZ`：`3381e19..891869e`（.gitignore +3 行）
- 根仓库：`18f52e93..90e50a08`（4 files, +49/-2）

### 瘦身计划完成状态总览

| 项 | 状态 |
|----|------|
| P0-1 U1 node_modules | ✅ 已删除 + gitignore |
| P0-2 U1 WiFi/BT 编译开关 | ✅ 已完成 |
| P0-3 U8 音频协议矛盾 | ✅ 已修复（PCM） |
| P0-4 DEPRECATED 标记修正 | ✅ 已完成 |
| P0-5 Telegram DEPRECATED | ✅ 已标记 |
| P0-6 AGENTS.md 断链 | ✅ 已修复 |
| P0-7 STATUS.md 矛盾 | ✅ 已修复 |
| P0-8 gitnexus skills | ✅ 已删除 |
| P1-9 战略文档归档 | ✅ 已归档 |
| P1-10 progress.md 截断 | ✅ 343 行 |
| P1-11 docs/archive 清理 | ✅ README + 无 .py |
| P1-12 agent 配置树 | ✅ 已纠偏 |
| P1-13 routing_engine 归包 | ✅ 已完成 |
| P1-14 routing_executor 归包 | ✅ 已完成 |
| P1-15 模块数修正 | ✅ 17 模块 |
| P2-16 死鉴权端点 | ✅ 已删除 |
| P2-17 create.vue 合并 | ✅ 决定保留 |
| P2-18 tabbar 5→3 | ✅ 已完成 |
| P2-19 settings 瘦身 | ✅ 已完成 |
| P2-20 except:pass 审查 | ✅ 已完成 |

**全部 20 项已完成。**

## 2026-07-02 代码尺寸门禁清零 + 小程序死页面清理

### 背景

`check_code_size.py` 报告 2 个文件超过 300 行（`test_drawing_pipeline.py` 366 行、`test_deploy_unified.py` 304 行），且小程序中残留已退役的 mine.vue 页面和 4 个未引用的语言文件。

### 改动

1. **拆分 `test_drawing_pipeline.py`（366→293 行）**：将 `TestRunPipeline` 端到端测试拆到 `test_drawing_pipeline_e2e.py`（105 行），原文件保留 stage 独立测试。
2. **拆分 `test_deploy_unified.py`（304→183 行）**：将 6 个 mock 类提取到 `tests/_deploy_mocks.py`（126 行），消除重复 setup 代码。
3. **删除 4 个残留语言文件**：`de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts`（已在上一轮从 import 移除但物理文件残留，共 ~117K）。
4. **删除 mine.vue 死页面**：功能已完全被 settings 吸收（退出登录、声纹、关于），tabbar 已无 mine 入口；从 `pages.json` 移除注册，清理 `tabBar.mine` i18n 键。
5. **小程序 P2 瘦身变更入库**：4 个 composables（useServerUrl/useCacheManager/useNotifications/useAccountDeletion）、tabbar 5→3、alova.ts langMap 裁剪等。

### 验证

- `check_code_size.py`：**0 个 >300 行文件、0 个 >50 行函数**（首次全绿）
- 全量 pytest：**4391 passed / 3 skipped / 2 deselected / 0 failed**
- `ruff check` clean；pre-commit 全绿
- `vue-tsc --noEmit` 0 errors

### Git

- 子模块 `esp32S_XYZ`：`db1a118..3381e19`（19 files, +423/-2796）
- 根仓库：`55d135ca..7ca69fe4`（测试拆分 + 子模块指针）

## 2026-07-02 系统瘦身 P2-17/18：小程序 UI 合并完成

### P2-18: 合并 3 个首页 → tabbar 5→3（已完成）

**痛点**：tabbar 5 个 tab 中有 3 个首页重叠（device-list / WorkshopHome / mine），且「配网」是一次性 onboarding 却占永久位。

**改动**：
1. **mine → settings 合并**：将 mine 页的声纹入口、退出登录功能合并到 settings 页（新增两个 SectionCard），mine 页 layout 从 tabbar → default
2. **index(WorkshopHome) 移出 tabbar**：与 device-list 功能重叠（都是设备仪表盘），layout 从 tabbar → default；device-detail 中 goToAgents 改为 navigateTo
3. **tabbar 5→3**：首页(device-list) + 配网(device-config) + 设置(settings)；tabBarI18nKeys 同步裁剪
4. **settings 页 layout**：从 default → tabbar（因为现在是 tabbar 页面）

**P2-17 决策**：write-draw-panel 已是简化版 2 步流（写字+画图），create/ 页面是高级模式（含图片选择、参数面板）。合并会丢失高级功能，决定保留现状。满足「≤3 步」要求。

**验证**：vue-tsc 0 errors；mp-weixin 编译成功；settings 379 行（< 400）；无 switchTab 到已移除页面的残留引用

## 2026-07-02 系统瘦身 P2-19：小程序 settings 瘦身完成

### P2-19: settings 瘦身（已完成）

**痛点**：settings/index.vue 是 656 行的杂物袋，混合了 7 个功能段（服务端地址、缓存管理、隐私权限、通知订阅、账号注销、关于、语言），且语言列表包含 4 个臆测语言（de/vi/pt_BR/zh_TW）。

**改动**：
1. **语言裁剪**：`Language` 类型从 6 种裁到 2 种（zh_CN + en）；删除 `de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts` 导入；更新 `alova.ts` 的 `langMap`
2. **逻辑拆分到 composables**：
   - `hooks/useServerUrl.ts` — 服务端地址管理（加载/验证/测试/保存/重置）
   - `hooks/useNotifications.ts` — 微信通知订阅管理
   - `hooks/useCacheManager.ts` — 缓存信息获取与清除
   - `hooks/useAccountDeletion.ts` — 账号注销双确认流程
3. **settings/index.vue 重写**：从 656 行 → 322 行（< 400 行目标达成），脚本段从 ~400 行 → ~75 行

**验证**：vue-tsc --noEmit 0 errors；无残留 zh_TW/de/vi/pt_BR 引用

## 2026-07-02 系统瘦身 P2-20：except:pass/continue 违规审查完成

### P2-20: 审查 except Exception: pass/continue 违反硬规则（已完成）

**痛点**：AGENTS.md 硬规则 #1 禁止 `except Exception: pass`（静默降级），但此前统计有 21 个文件疑似违规。

**审查过程**：
- 编写精确检测脚本，区分宽泛异常捕获（`except Exception:`）与特定异常类型捕获（`except json.JSONDecodeError:` 等）
- 全面扫描后确认：83 个 `except: pass/continue` 中，仅 3 个是真正的宽泛异常静默吞掉（违反硬规则），其余 80 个是特定异常类型的合法控制流

**修复的 3 个违规**：
1. `packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64` — `except Exception: continue` → 添加 `logging.debug` 记录探测失败原因
2. `packages/provider-probe-offline/provider_probe/reverse/pricing_probe.py:74` — `except Exception: continue` → 添加 `logging.debug` 记录定价探测失败原因
3. `tests/test_memory_promote.py:39` — `except Exception: pass` → 添加 `logging.debug` 记录 DB 状态依赖异常

**验证**：全量 4391 passed, 0 failed；ruff check clean；违规数归零

## 2026-07-02 系统瘦身 P1-13/14：routing_engine/executor 归包完成

### P1-13: routing_engine 9 个根文件 → 包（已完成）

**痛点**：`routing_engine*.py` 共 9 个文件散落在仓库根目录，阅读一个路由决策需要打开 14+ 文件，概念碎片化严重。

**实现**：
- 创建 `routing_engine/` 包目录，9 个文件移入并缩短名称：
  - `routing_engine.py` → `routing_engine/__init__.py`（facade，保持公共 API 不变）
  - `routing_engine_types.py` → `routing_engine/types.py`
  - `routing_engine_trace.py` → `routing_engine/trace.py`
  - `routing_engine_cache.py` → `routing_engine/cache.py`
  - `routing_engine_context.py` → `routing_engine/context.py`
  - `routing_engine_execute_strategy.py` → `routing_engine/execute_strategy.py`
  - `routing_engine_helpers.py` → `routing_engine/helpers.py`
  - `routing_engine_intent.py` → `routing_engine/intent.py`
  - `routing_engine_post.py` → `routing_engine/post.py`
- 包内导入改为相对导入（`from .trace import trace_span` 等）
- 外部引用更新：`routing_engine` 主模块 API 完全不变（`from routing_engine import route, pick_backend, ...`）
- 测试文件更新：7 个测试文件中的子模块导入路径和 patch 路径更新
- `pyrightconfig.json` 更新：`routing_engine.py` → `routing_engine/`

### P1-14: routing_executor 5 个根文件 → 包（已完成）

**痛点**：`routing_executor*.py` 共 5 个文件散落在仓库根目录，与 routing_engine 同属概念碎片化。

**实现**：
- 创建 `routing_executor/` 包目录，5 个文件移入：
  - `routing_executor.py` → `routing_executor/__init__.py`
  - `routing_executor_telemetry.py` → `routing_executor/telemetry.py`
  - `routing_executor_serial.py` → `routing_executor/serial.py`
  - `routing_executor_parallel.py` → `routing_executor/parallel.py`
  - `routing_executor_fallback.py` → `routing_executor/fallback.py`
- 包内导入改为相对导入
- 外部引用不变（`from routing_executor import execute`）
- 4 个测试文件更新子模块导入路径
- `test_routing_pipeline_authority.py` 更新：源码路径检查从 `routing_executor_serial` → `routing_executor.serial`

### 验证

- 全量测试：**4391 passed, 3 skipped, 0 failed**
- ruff check：Python 文件全部 clean（pyrightconfig.json 的 JSON false 误报忽略）
- code size：0 个 >300 行文件，0 个 >50 行函数
- 公共 API 完全向后兼容：`from routing_engine import route` 和 `from routing_executor import execute` 不变

## 2026-07-02 Tier 2 改善计划推进

### T2-2 后端健康检查探针标准化（已完成）

**痛点**：`backend_probe_loop.py` 有重复的 `_classify_error` 函数，与 `health_recorder.classify_failure` 逻辑重复且分类结果不一致。

**实现**：
- 新增 `health_probe.py`：定义 `ProbeResult` dataclass、`HealthProbe` Protocol、`classify_probe_error()` 委托函数、`make_result()` 便捷构造器
- 重构 `backend_probe_loop.py`：删除重复的 `_classify_error`（-13 行），改用 `classify_probe_error` 委托至 `health_recorder.classify_failure`
- 新增 `tests/test_health_probe.py`：16 个测试覆盖 ProbeResult、classify_probe_error、make_result
- 全量测试：4391 passed, 0 regressions

**关键文件**：`health_probe.py`、`backend_probe_loop.py`、`tests/test_health_probe.py`

### T2-3 设备任务历史时间线查询（已完成）

**痛点**：`GET /tasks/{task_id}` 只返回原始事件列表，无法直观看到状态流转和阶段耗时；`GET /tasks` 只返回当前状态，无历史时间线。

**实现**：
- 新增 `device_gateway/task_timeline.py`：将 ledger 事件流转换为结构化时间线，含中文状态描述、阶段间耗时、终态判断
  - `build_task_timeline(task_id)`：单任务时间线（事件→阶段流转+耗时）
  - `build_device_timeline(device_id, limit)`：设备级时间线（多任务聚合，按最后更新倒序）
- 新增 `routes/device_timeline_routes.py`：两个新端点（独立路由文件，控制 device_gateway.py 行数 ≤300）
  - `GET /device/v1/tasks/{task_id}/timeline`：单任务状态流转时间线
  - `GET /device/v1/devices/{device_id}/timeline`：设备任务历史时间线
- 路由注册：`routes/route_registry.py` 添加 `device_timeline_routes` 到 `_DEVICE_APP_ROUTERS`
- 新增 `tests/test_task_timeline.py`：9 个测试覆盖单任务/设备级时间线、排序、limit、终态判断
- 全量测试：4391 passed, 0 regressions

**关键文件**：`device_gateway/task_timeline.py`、`routes/device_timeline_routes.py`、`tests/test_task_timeline.py`

### T2-1 U1 固件迁移到 FluidNC（软件层完成，硬件验证待人工执行）

**痛点**：Grbl_Esp32 已停更，无安全更新；配置需编译时 C 头文件硬编码。

**软件层实现**：
- 翻译 `dlc_motor_control_p1.h` → `firmware/fluidnc/config/dlc_motor_control_p1.yaml`
  - 完整映射 GPIO（X/Y/Y2/Z STEP/DIR、MOTOR_EN、4 路限位、激光 PWM）
  - 运动参数（steps/mm、max_rate、acceleration、pulse_us、idle_ms）
  - 回零策略（Z→X→Y 顺序、Y/Y2 龙门校正 square:true）
  - 激光模式（PWM 输出 GPIO45）
- 编写 `esp32S_XYZ/docs/U1-FluidNC迁移计划.md`：含配置映射对照表、8 步硬件验证清单（D1-D8）、回退方案、已知风险

**待人工执行**：D1-D8 硬件验证步骤（需物理设备在环测试，Agent 无法替代）

## 2026-07-02 Tier 1 改善计划全部完成

三项 Tier 1 改善计划已按顺序实施完成，全部测试通过（193 passed, 0 regressions）。

### T1-2 路径优化重构为管道架构（对标 vpype）

- **新增** `xiaozhi_drawing/pipeline.py`：管道架构（`PipelineContext` + `run_pipeline` + 5 个独立 stage 函数）
- **重构** `xiaozhi_drawing/svg_converter.py`：委托至管道阶段，保持所有公共 API 向后兼容
- **测试**：`tests/test_drawing_pipeline.py`（26 tests）+ 现有 39 tests 全部通过
- **关键设计**：`preprocess → skeleton → trace → order → simplify` 五阶段可独立测试和替换

### T1-3 Hershey 单笔画字体支持（对标 GRBL-Plotter）

- **新增** `xiaozhi_drawing/hershey_font_data.py`：96 字符的 Hershey 字体数据（A-Z, a-z, 0-9, 标点）
- **新增** `xiaozhi_drawing/hershey_font.py`：渲染器（`hershey_text_to_svg_path`）
- **修改** `xiaozhi_drawing/text_to_path.py`：新增 `font_type="hershey"` 参数，默认 `"ttf"` 不破坏现有行为
- **测试**：`tests/test_hershey_font.py`（23 tests）全部通过
- **关键优势**：单笔画开放路径（无 Z），绘图机不会画出双线

### T1-1 意图分类引入语义向量预筛（对标 Semantic Router）

- **新增** `routing_semantic.py`：n-gram TF-IDF 余弦相似度分类器（纯 Python，零外部依赖）
- **修改** `routing_intent.py`：在 `_enhanced_classify` 中插入语义层（规则 → 信号 → 语义 → 上下文 → 默认）
- **测试**：`tests/test_routing_semantic.py`（26 tests）+ 现有 88 tests 全部通过
- **关键设计**：不引入 sentence-transformers 或网络 API，用 n-gram TF-IDF 实现毫秒级语义匹配
- **行为改进**：`"explain quantum mechanics"` 从默认 `"chat"` 改进为正确识别 `"explanation"`

### 文件清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `xiaozhi_drawing/pipeline.py` | 新增 | 226 |
| `xiaozhi_drawing/svg_converter.py` | 重构 | 248 |
| `xiaozhi_drawing/hershey_font.py` | 新增 | 188 |
| `xiaozhi_drawing/hershey_font_data.py` | 新增 | 138 |
| `xiaozhi_drawing/text_to_path.py` | 修改 | 243 |
| `routing_semantic.py` | 新增 | 166 |
| `routing_intent.py` | 修改 | 296 |
| `tests/test_drawing_pipeline.py` | 新增 | 367 |
| `tests/test_hershey_font.py` | 新增 | 148 |
| `tests/test_routing_semantic.py` | 新增 | 159 |

全部文件通过 `ruff check`、`ruff format --check`、`check_code_size.py`（≤300 行/≤50 行函数）。

## 2026-07-02 基于参考项目的改善计划制定

- **背景**：系统瘦身完成后，基于已核实的 GitHub 参考项目，分析 LiMa 与参考项目的差距，按 Ponytail YAGNI 原则过滤后制定精准改善计划。
- **差距分析**：逐一对比 LiMa 现状与 5 个核心参考项目（Semantic Router、vpype、LiteLLM、eventsourcing、FluidNC），评估差距大小和改进价值。
- **Ponytail 过滤结果**：
  - **Tier 1 值得做（3 项）**：T1-1 语义向量预筛意图分类、T1-2 路径优化管道重构、T1-3 Hershey 单笔画字体支持
  - **Tier 2 可以做（3 项）**：T2-1 U1 固件迁移 FluidNC、T2-2 健康探针标准化、T2-3 设备任务时间线查询
  - **Tier 3 暂不做（4 项）**：后端 adapter 模式、语义缓存、完整事件溯源、远程证明 —— 均 YAGNI
- **设计文档**：`docs/superpowers/specs/2026-07-02-reference-driven-improvement-plan.md`（中文）
- **关键设计决策**：
  - 语义分类器不直接引入 Semantic Router 依赖，用已有 embedding 后端自实现
  - 路径管道重构参考 vpype 架构但保持现有函数签名，纯重构不改行为
  - Hershey 字体是增量新增，不破坏现有 TTF 路径
- **待用户审批**：计划已就绪，等待用户确认优先级和执行顺序后开始实施。

## 2026-07-02 GitHub 参考项目实测核实 + 文档更新

- **背景**：项目文档 `docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 附录中收录了 30+ 个 GitHub 参考项目，星数和活跃度数据写于 2026-06-24，用户要求重新到 GitHub 核实。
- **核实方式**：逐个用浏览器访问 GitHub 仓库页面，提取实时星数、最后提交时间、是否归档。
- **核实结果**：
  - **核心参考全部真实活跃**：LiteLLM 52.3k（原标 20k+，今日仍在更新）、Ponytail 70.8k（昨日更新）、FluidNC 2.5k（上月更新）、Semantic Router 3.7k（原标 2k+）、vpype 917（原标 500+）、bCNC 1.7k（原标 1.5k+）、eventsourcing 1.7k（原标 1.5k+）。
  - **5 个项目已死或低价值**，已附替代推荐：
    - `IoTThinks/esp32FOTA`（1 星，2021 停更）→ 替代 [espressif/esp_https_ota](https://github.com/espressif/esp-idf/tree/master/components/esp_https_ota)
    - `barfittc/gcode-optimizer`（0 星，2023 停更）→ 替代 vpype 的 `optimize` 命令
    - `DrivenIdeaLab/openstatus`（0 星，URL 可能有误）→ 替代 [upstash/openstatus](https://github.com/upstash/openstatus)
    - `PufferFinance/rave`（35 星，SGX 场景不匹配）→ 替代 ESP-IDF Secure Boot v2 官方实现
    - `SebKuzminsky/svg2gcode`（25 星，功能简单）→ 替代 vpype 的 SVG→GCode 管道
  - 其余项目（esp_ghota 446 星、GRBL-Plotter 865 星、BrachioGraph 745 星、ModelCache 941 星、GPTCache 8.1k 星、THiNX 24 星但活跃）均真实存在，已更新精确星数和活跃度标记。
- **文档更新**：`docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 附录 A.1–A.9 共 19 处编辑——更新星数、添加活跃度标记（🟢/🟡/🔴）、为 5 个死掉/低价值项目添加替代推荐、末尾添加核实说明。
- **教训**：文档中的第三方项目数据会随时间漂移，星数只增不减但活跃度会变化。建议每季度核实一次参考项目清单，及时标记死链和替代推荐。

## 2026-07-02 全量门禁 + 京东云生产部署 + 公网冒烟验证

- **本地全量门禁**：`scripts/run_pre_commit_check.py --full` → **4278 passed, 3 skipped, 2 deselected**；ruff check clean。（测试数较上次 4285 少 7 个，因小程序 UI 重构删除了死鉴权端点相关测试。）
- **VPS 部署**：`deploy_unified.py --target jdcloud --slice core` → 883 文件上传，0 失败。tar/scp 因 SSH key 认证失败自动回退 SFTP（密码认证）成功。备份 `/opt/lima-router/backups/unified-core-20260702_141038/runtime-before.tgz`。服务重启健康检查 OK。
- **公网冒烟验证**：
  - `GET /health` → `{"status":"ok","version":"2.0","model":"lima-1.3","startup":{"status":"ready"}}` ✅
  - `GET /health/ready` → `{"status":"ready","startup_status":"ready","pending_warm":[],"error_count":0}` ✅
  - `POST /v1/chat/completions`（匿名）→ 200，后端 `cfai_qwen_coder`，记忆召回 `memory_ids:[33,7]` ✅
  - `/device/v1/app/voice/ticket` → 405（GET 不支持，端点可达）✅
- **结论**：最新代码（含小程序 UI 重构、静默降级修复、retired 代码清理、deploy_unified 京东云支持）已部署到京东云生产节点并验证通过。

## 2026-07-02 小程序 UI 深度重构（BACKLOG-P2-1）

- **背景**：瘦身审查报告三项 UI 指控，逐项核实后真伪分明，按「真问题改、伪指控纠偏」执行。
- **核实纠偏**：
  - `create.vue` 937 行嵌套两层 tab（`mode`+`aiSubMode`，两路不同 API）— **属实**。
  - 3 首页重叠（mine 统计与 index Hero 重复；mine 跳底栏已有 tab）— **部分属实**。
  - `settings` 744 行「杂物」— **不属实**（全是设置页职责，仅样式重复+2 死代码）。
  - `chat` 与 `create` 重叠 — **不属实**（零交叉导入）。
- **M1 抽公共组件 + settings 死代码**（子模块 `a6e1e60`）：新增 `section-card.vue`（≤30行）、`stat-pill.vue`（≤80行）；settings 7 个重复 section 壳 → `<SectionCard>` 组件调用，744→655 行；删 `useConfigStore`/`systemInfo` 2 处死代码。视觉零变化。
- **M2 create.vue 拆两页**（子模块 `9110792`）：新增 `useCreateShared.ts` composable 抽共享逻辑；`ai-draw.vue`(322行) 承载云生图、`image-draw.vue`(264行) 承载设备绘图；抽 `create-shared.scss` 共享样式；删 create.vue 937 行；index.goDraw/goImageDraw 改跳新页去 `?mode=`；pages.json 路由更新。
- **M3 mine 转纯账号页 + index 去重**（子模块 `c78edc1`）：mine 418→305 行，删 3 统计卡 + 设备数据获取、删「设备管理/配网」冗余菜单（底栏已直达）、新增「声纹」入口；index Hero sub-item「设备 X 台」改为「在线 X/总 Y 台」吸收在线统计；i18n zh/en 加 `mine.voiceprint/voiceprintDesc`。
- **M4 验收 + 文档**：`npx vue-tsc --noEmit` 0 errors（每里程碑均验证）；`npx uni build --platform mp-weixin` 编译通过（exit 0，dist/build/mp-weixin 生成）；设计文档见 `docs/superpowers/specs/2026-07-02-miniprogram-ui-refactor-design.md`（中文）。
- **未做**：微信上传/审核（BACKLOG-P0-4 单独触发）；真机端到端（BACKLOG-P0-3，需硬件）。
- **教训**：审查「行数/嵌套层数」可信，但「杂物/重叠」严重度判定不可信。改 UI 前必须逐区块核实职责归属，不能按行数盲改。

## 2026-07-02 retired 文件删除 + 冗余 Cursor rules 清理（BACKLOG-P1-3/P1-4）

- **BACKLOG-P1-3 删除退役代码**：`docs/archive/retired/` 下 7 个 Gitee 镜像/双推退役文件（`gitee_mirror*.py`、`gitee_mirror_urls.py`、`push_dual_remotes.{ps1,py,sh}`、`test_gitee_mirror.py`）。全仓 grep 确认**零引用**，Gitee 镜像已彻底退役，git 历史可恢复。代码文件不应残留在 `docs/` 树，直接 `git rm` 删除（含 `__pycache__` 物理清理）。
- **BACKLOG-P1-4 agent 配置树纠偏**：审查报告称「8 棵树 / ~9300 行 / Ponytail 重复 6 处」。逐树核实后**纠偏**：
  - 8 棵树中 **5 棵被 `.gitignore` 忽略不入库**（`.agent`、`.claude`、`.kimi-code`、`.continue`、`andrej-karpathy-skills`）——本地 IDE 私有副本，重复无害，无需处理。
  - 入库的 agent 树仅 `.cursor`（2 rules）、`.joycode`（2 memory）、`skills`（14）、`AGENTS.md`、`CLAUDE.md`。
  - 真正可统一项仅 `.cursor/rules/` 两份：`ponytail.mdc`（与 `docs/AGENTS_PONYTAIL.md`，被 `AGENTS.md` 引用为权威源）重复、`ecc-workflow.mdc`（与 `docs/ECC_WORKFLOW_CN.md`，被 `AGENTS.md` 引用）重复。两份均 `alwaysApply: true`，删后 Cursor 失去自动注入但 `AGENTS.md` 仍是权威源。
  - 删除 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`，保留 `.cursor/rules/lima-*.mdc`（未入库的本地 Cursor 私有 rules）不动。
- **验证**：`ruff check .` + `scripts/check_code_size.py` 全通过；删除项不影响测试（`docs/`、`.cursor/rules` 不在 import 路径）。
- **教训**：审查「8 棵树 / 9300 行 / 重复 6 处」口径来自把「被 gitignore 的本地私有配置」也计入重复——合并前必须区分「入库」与「本地工具私有」，否则会去清理一堆本就不该入库的副本。

## 2026-07-02 code-review 修复 + 静默降级修复（BACKLOG-P1-2/P1-1）

- **code-review 死导入清理**：`DeployTarget` 重构（P0-1）留下 9 处死导入/重定义（`shlex`、`time`×2、重复 `from config import deploy_config`×2、`CORE_FILES`、`DEFAULT_MIN_FREE_MB`、`DEFAULT_MIN_MEM_MB`、未用 `deploy_config`×2）。这些因 `ruff.toml` 只 select `E9/F821/...` 不含 `F401`/`F811` 而漏过 pre-commit。已全部移除，提交 `refactor(deploy): remove dead imports left by DeployTarget refactor`（`7b2b7140`）。
- **BACKLOG-P1-2 静默降级修复（纠偏后精准执行）**：审查报告称「16 处 / voice_pipeline_ws·mqtt_client·store_voiceprint 各 2 处」。用 Explore 子代理实地核查后**证伪**——那 6 处全是 `asyncio.TimeoutError` / `CancelledError` / `sqlite3.OperationalError` 幂等迁移，属正常控制流，**0 违规**。真正违反 AGENTS.md「禁止静默降级」的是 **4 处**一等生产路径的 `except Exception:` 裸吞：
  - `routing_executor_parallel.py`：并行降级执行器逐 future 吞 worker 异常 → 补 `_log.warning`（`_try_one_parallel` 已记录 per-backend 失败，此处仅 worker 本身异常）。
  - `speculative_execution.py`：推测竞速内层 `future.result()` 吞异常 → 补 `logger.debug`（`_spec_worker` 已 warning+exc_info 记录真实后端失败并返回 ""，到此仅 future 本身取消/executor 错误，debug 避免每次推测落败刷屏）。
  - `observability/jsonl_store.py`：读遥测文件吞异常 → 窄化为 `(OSError, UnicodeDecodeError)` + `_log.warning`；顺手删预存死导入 `os`。
  - `provider_automation/adapters/cloudflare.py`：编码评分循环吞调用失败 → 补 `_log.warning`（新增 `logging` import + `_log`）。
- **边界项（不改，仅记录）**：`packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`、`pricing_probe.py:74` 各 1 处 `except Exception: continue`——属冷离线探测工具，不在生产请求路径，本轮不改，记入 findings 供后续排期。
- **BACKLOG-P1-1**：语音设计文档 `2026-07-02-mini-program-voice-draw-design.md` 状态标记经查已在前序会话更新为「已完成（M0+M1+M2）」，无残留「待审批」标记，无需再改。
- **验证**：受影响模块聚焦测试 176 passed；全量 `pytest` **4288 passed, 3 skipped**；`ruff check .`（项目配置）+ 全量 `F401/F811` 复查 + `scripts/check_code_size.py` 全通过。
- **教训**：审查报告的「计数」可信，但「严重度判定」不可信——同一批 6 个 `except: pass` 计数准确却 0 违规。修静默降级前必须逐点区分「裸 `except Exception` 无日志」（违规）与「窄化异常做控制流」（合规），不能按 pattern 计数盲改。

## 2026-07-02 U8 固件改 PCM 解决音频协议矛盾（BACKLOG-P0-2）

- **背景**：U8 固件 `audio_service.cc` 的麦克风输入走 OPUS 编码后发送，但 `websocket_protocol.cc` 的 hello 帧已声明 `"format":"pcm"`，后端 `device_voice_ws_helpers.py` / `voice_pipeline_ws.py` 均假设 PCM 输入，导致设备实时语音/TTS 无法互通。
- **方向**：用户选择方案 A——固件改 PCM，后端零改动。
- **实现**（U8 固件侧，路径 `esp32S_XYZ/firmware/u8-xiaozhi/main/`）：
  - `protocols/protocol.h`：
    - `AudioStreamPacket` 新增 `std::string format = "opus"` 字段；
    - `Protocol` 基类新增 `virtual bool UsesPcm() const { return false; }`。
  - `protocols/websocket_protocol.h`：覆写 `UsesPcm()` 返回 `true`。
  - `protocols/websocket_protocol.cc`：对下行音频包（v1/v2/v3）统一设置 `format = "pcm"`。
  - `protocols/mqtt_protocol.cc`：对下行音频包显式设置 `format = "opus"`（保持 MQTT 默认行为）。
  - `audio/audio_service.h`：新增 `bool send_pcm_` 成员与 `SetSendPcm(bool)` 方法。
  - `audio/audio_service.cc`：
    - `OpusCodecTask` 上行分支：按 `send_pcm_` 选择 PCM 透传或 OPUS 编码；
    - `OpusCodecTask` 下行分支：按 `packet->format` 选择 PCM 透传或 OPUS 解码；
    - `PlaySound` 保持 `format = "opus"`，本地 Ogg 提示音继续走 OPUS 解码路径；
  - `application.cc`：协议初始化后调用 `audio_service_.SetSendPcm(protocol_->UsesPcm())`，使 Websocket/LiMa 路径启用 PCM 上行。
- **验证**：
  - 代码审查确认下行/上行/提示音三条路径格式区分清晰；MQTT 路径未破坏；PlaySound 路径未破坏。
  - 未执行 ESP32 编译/烧录（当前环境无工具链），需你本地 `idf.py build` + 烧录 U8 后验证实时语音与 TTS 回放。
- **风险**：固件中 OPUS 编码器/解码器仍初始化但 Websocket 路径不再使用，会占用少量 RAM/CPU；后续如需彻底清理，可再拆一轮移除 OPUS 依赖。
- **文档**：更新 `findings.md` 关闭 P0-2。

## 2026-07-02 deploy_unified.py 支持京东云主生产节点（BACKLOG-P0-1）

- **背景**：2026-07-02 部署小程序语音端点时，`deploy_unified.py` 默认连接阿里云（`LIMA_SERVER=47.112.162.80`），而公网入口 `chat.donglicao.com` 实际走 Cloudflare Tunnel → 京东云（`117.72.118.95`）。误部署导致公网端点返回 404。
- **实现**：
  - `config/deploy_config.py`：新增 `deploy_target()`（默认 `jdcloud`）、`aliyun_password()`（回退到 `LIMA_DEPLOY_PASS`）、保留 `jdcloud_password()`。
  - `scripts/deploy_unified_common.py`：新增 `DeployTarget` 值对象、`get_deploy_target()`、`TARGET_ALIYUN` / `TARGET_JDCLOUD`；`_connect_ssh()` 改为按目标连接。
  - `scripts/deploy_unified.py`：新增 `--target {aliyun,jdcloud}`，默认 **jdcloud**；打印目标名与 IP；部署标签包含目标名。
  - `scripts/deploy_unified_preflight.py`/`deploy_unified_deploy.py`/`deploy_unified_restart.py`/`deploy_unified_nginx.py`：全部改为接收 `DeployTarget`，使用目标专属 `host`/`remote_path`/`user`/`password`/`key_path`。
  - `.env.example`：新增 `LIMA_DEPLOY_TARGET`、`LIMA_ALIYUN_PASSWORD`、`LIMA_JDCLOUD_ROOT_PASSWORD` 说明；保留 `LIMA_DEPLOY_PASS` 作为 Aliyun 历史别名。
- **验证**：
  - `python scripts/deploy_unified.py --dry-run --target jdcloud --slice core` → 目标显示 `jdcloud (117.72.118.95)`。
  - `python scripts/deploy_unified.py --dry-run --target aliyun --slice core` → 目标显示 `aliyun (47.112.162.80)`。
  - `ruff check scripts/deploy_unified.py scripts/deploy_unified_*.py config/deploy_config.py tests/test_deploy_unified.py` → PASS。
  - `python -m py_compile` 上述文件 → PASS。
  - `.venv310` 下全量 pytest：`4286 passed, 3 skipped, 2 deselected`（含更新后的 `tests/test_deploy_unified.py` 10 passed）。
  - 实际部署 JDCloud：`python scripts/deploy_unified.py --slice core` → 883 uploaded / 0 failed / health OK / `Deploy OK: unified/core/jdcloud`。
  - 公网冒烟：`https://chat.donglicao.com/health/ready` → `{"status":"ready"}`；`POST /device/v1/app/voice/ticket` → 401（鉴权生效）。
- **风险**：默认目标从隐式 Aliyun 改为显式 JDCloud，可能改变只依赖 `LIMA_SERVER` 而不看 `--target` 的用户/脚本习惯。已通过 `--target aliyun` 保留回退路径。
- **文档**：更新 `STATUS.md` 将「待修」改为「已修复」；`findings.md` 关闭 BACKLOG-P0-1；`.env.example` 同步说明。

## 2026-07-02 移除设备网关 WebSocket query 参数 token 注入（AUDIT-11-W2）

- **背景**：`routes/device_gateway_dispatch.py:extract_ws_token`  historically 支持 ticket / Authorization header / `?token=` / `?authorization=` 四种注入方式，后两者会让 Bearer token 进入 nginx access log 与 Referer。此前生产已默认拒绝 query token，但代码仍保留 legacy 分支和临时环境变量 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN`。
- **实现**：
  - `routes/device_gateway_dispatch.py`：删除 `import os`、移除 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 判断与 legacy query token 分支，`extract_ws_token` 仅保留 `?ticket=` 与 `Authorization` header 路径。
  - `.env.example`：删除 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 相关说明。
  - `tests/conftest.py`：删除 `_allow_legacy_device_ws_query_token_in_tests` autouse fixture。
  - `tests/test_device_gateway_dispatch.py`、`tests/test_device_ws_ticket.py`、`tests/test_routes_device_gateway_dispatch.py`：更新断言，确认 query token/authorization 被永久拒绝。
  - 设备 WS 集成测试迁移：把 `client.websocket_connect("/device/v1/ws?token=test-device-token")` 改为 `headers={"Authorization": "Bearer test-device-token"}`，涉及 `tests/device_gateway/test_ai_to_motion_gate.py`、`test_tasks_http.py`、`test_ws_lifecycle.py`、`test_device_gateway_ws_errors.py`、`test_fake_u1_cloud_*.py`、`test_p1_4_device_stability_gate*.py`。
  - `docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md`：更新为 Phase 2 已完成，query token 注入已移除。
- **验证**：
  - 聚焦设备 WS 相关测试：71 passed，1 skipped。
  - 全量 pytest：`4285 passed, 3 skipped, 2 deselected`。
  - `ruff check .`、`ruff format --check`、`pyright` 目标文件、`scripts/check_code_size.py` 均通过。
  - `grep` 确认仓库中不再有 `/device/v1/ws?token=` 与 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 代码/测试引用。
- **风险**：若前端或固件仍有未切换的 `?token=` 调用，生产会认证失败；但生产此前已默认拒绝 query token，因此本次仅清理 legacy 代码与测试，不影响线上行为。
- **文档**：更新 `findings.md`、`STATUS.md` 将 AUDIT-11-W2 标记为已关闭。

## 2026-07-02 为 AUDIT-6-A1 补充 OpenAPI 文档开关显式测试

- **背景**：`server.py` 已按 AUDIT-6-A1 默认禁用 Swagger/OpenAPI 文档（`LIMA_DOCS_ENABLED=1` 可开启），但测试目录此前无针对 `/docs`、`/redoc`、`/openapi.json` 返回行为的断言。
- **实现**：新增 `tests/test_server_docs_disabled.py`：
  - 默认环境下通过独立子进程导入 `server`，断言三个文档端点均返回 404。
  - 设置 `LIMA_DOCS_ENABLED=1` 后，断言 `/docs`、`/redoc` 返回 HTML 200，`/openapi.json` 返回 200。
  - 使用子进程隔离，避免切换 `LIMA_DOCS_ENABLED` 时污染同进程的全局 `app` 对象。
- **验证**：
  - `tests/test_server_docs_disabled.py`：2 passed。
  - 全量 pytest：`4285 passed, 3 skipped, 2 deselected`。
  - `ruff check .`、`ruff format --check`、`pyright tests/test_server_docs_disabled.py server.py`、`scripts/check_code_size.py` 均通过。
- **文档**：更新 `findings.md` AUDIT-6-A1 验证列为新增测试 + 全量门禁。

## 2026-07-01 关闭过时的代码尺寸 findings（VOICE-SIZE-3 / ECC-2）

- **背景**：`findings.md` 中 `VOICE-SIZE-3` 与 `ECC-2` 仍标记为 Open，记录的是历史上存在 23~35 个 >300 行文件 / 99~100 个 >50 行函数的状态。
- **当前状态**：`scripts/check_code_size.py` 当前扫描结果为 **0 个 >300 行文件、0 个 >50 行函数**，`run_pre_commit_check.py` 已将其作为阻塞门禁运行。
- **操作**：将 `findings.md` 中两项状态更新为 Closed，并补充 2026-07-01 基线达标的说明。
- **验证**：`scripts/check_code_size.py` PASS；`scripts/run_pre_commit_check.py --ci --full` 4273 passed。

## 2026-07-01 CI 新增 `pip-audit` 依赖漏洞门禁

- **背景**：`findings.md` 2026-07-01 依赖漏洞修复项建议将 `pip-audit` 加入 CI，防止已修复的 manifest 漏洞回退。
- **实现**：
  - `.github/workflows/test.yml` 的 `Install dependencies` 步骤安装 `pip-audit`。
  - `Security scan` 步骤合并 `bandit` 与 `pip-audit -r requirements_server.txt`；设置 `PYTHONUTF8=1` 避免 Windows 编码下 requirements 中文注释被误识别为 GBK。
- **验证**：
  - 本地 `PYTHONUTF8=1 pip-audit -r requirements_server.txt` → `No known vulnerabilities found`。
  - `bandit` 通过（仅 Low 问题）。

## 2026-07-01 修复 CI `Tests` workflow 与本地全量测试失败

- **背景**：合并 dependabot PR 后 GitHub `Tests` workflow 仍失败（18 failed），本地 `scripts/run_pre_commit_check.py --ci --full` 同样复现。
- **根因 1 — FastAPI 0.138.2 路由内省破坏**：
  - `fastapi>=0.138.2` 将 `app.include_router()` 的结果包装为 `_IncludedRouter`，`server.app.routes` 不再直接包含 `APIRoute` 叶子对象，导致所有路由注册/内省类测试断言失败。
  - 修复：将 `requirements_server.txt` 与 `deploy/jdcloud/jdcloud-worker-requirements.txt` 的 FastAPI 范围收紧为 `>=0.136.1,<0.136.3`（排除恶意 0.136.3 同时避开 0.138.x），并保留显式 `starlette>=1.3.1` 以继续覆盖 CVE-2026-54282/54283。
- **根因 2 — path_validator 丢弃已生成 motion path**：
  - `device_gateway/path_validator.py` 对 `write_text`/`draw_generated`/`handwriting` 等 `_PATH_GENERATING_CAPABILITIES` 会跳过 `path` 字段，即使 `build_run_params_async` 已经生成了有效 path，也会被丢弃，导致 5 个设备任务测试 KeyError/AssertionError。
  - 修复：新增 `_maybe_preserve_path()` 辅助函数；当 path 已存在且有效时校验并保留，无 path 时仍保持原有“稍后生成”的兼容性。
- **验证**：
  - `scripts/run_pre_commit_check.py --ci --full`：`4273 passed, 3 skipped, 2 deselected`
  - `pip-audit`：installed packages 无已知漏洞
  - `ruff check .`、`ruff format --check`、`pyright device_gateway/path_validator.py`、`scripts/check_code_size.py` 均通过

## 2026-07-01 Cloudflare Worker 透明兜底/灰度（已完成）

- **目标**：在 `chat.donglicao.com` 边缘部署 Worker，对匿名 `/v1/chat/completions` 请求透明代理到阿里云 pilot，并在 pilot 异常时自动回源到京东云主节点。
- **实现**：
  - 新增 `cloudflare/workers/chat-router.js`：按 `Authorization` 头存在性粗分流；无 key 的 POST `/v1/chat/completions*` 走 pilot；其余请求回源 `origin-chat.donglicao.com`；pilot 返回 429/5xx/408 时自动回源兜底。
  - 新增 `cloudflare/wrangler.toml`：路由 `chat.donglicao.com/v1/chat/completions*`。
  - 新增 `.github/workflows/deploy-chat-router-worker.yml`：自动确保 `origin-chat.donglicao.com` DNS 记录并部署 Worker。
- **基础设施**：
  - 京东云 `/etc/cloudflared/config.yml` 增加 `origin-chat.donglicao.com` ingress，指向本地 nginx（跳过 TLS 校验）。
  - GitHub Actions 已创建 `origin-chat.donglicao.com` CNAME 到 tunnel。
- **部署状态**：workflow run `28525746050` 成功，Worker `lima-chat-router` 已部署。
- **验证**：
  - `curl -X OPTIONS https://chat.donglicao.com/v1/chat/completions` → 204，CORS 头来自 Worker。
  - 匿名 POST（无 Authorization）→ `X-Lima-Backend: aliyun`，后端 `pollinations_openai`，响应 200。
  - 带 Authorization POST → `X-Lima-Backend: jdcloud`，响应 401（dummy key 被主节点拒绝，证明回源路径正常）。

## 2026-07-01 前端匿名简单聊天请求分流到阿里云 pilot

- **目标**：让 chat-web、官网 playground、manager-mobile H5 的匿名简单聊天请求走阿里云 `lima-router-pilot`（仅免费后端），降低京东云主节点负载。
- **实现**：
  - **chat-web**：新增 `chat-web/js/app-config.js` 提供 `shouldUsePilot(path, body)` 判定规则；`chat-api.js` 通过 `LiMaConfig.getApiUrl()` 选择 endpoint；`sendMessage()` 已增加一次失败回退（pilot 返回 429/503/5xx 或网络错误时重试 `chat.donglicao.com` 主节点）。
  - **官网 playground**：`donglicao-site-v2/app/developer/playground/page.tsx` 在 API Key 为空且 endpoint/model 为默认 chat 时自动切换 baseUrl 到 `aliyun.donglicao.com`。
  - **manager-mobile**：新增 `utils/index.ts` 的 `getChatBaseUrl()`，未登录且默认模型时返回 `aliyun.donglicao.com`；`api/chat/chat.ts` 的流式/非流式 chat 均使用该 baseUrl。
  - **CSP / 部署**：chat-web CSP 增加 `aliyun.donglicao.com`；`.gitignore` 增加 `chat-web/dist/`；manager-mobile H5 构建 base 设为 `/mobile/`。
- **部署**：
  - chat-web 源文件同步到京东云 `/opt/lima-router/chat-web`，并经 GitHub Actions 部署到 Cloudflare Pages（`app.donglicao.com`）。
  - 京东云 tunnel 入口由 `http://127.0.0.1:8080` 改为 `https://127.0.0.1:443`（跳过 TLS 校验），恢复 nginx 作为流量入口，从而支持 `/mobile/` H5 静态目录。
  - manager-mobile H5 构建后通过 `scp -r` 部署到 `/var/www/chat/mobile/`。
  - 官网 playground 经 GitHub Actions 部署到 Cloudflare Pages（`www.donglicao.com`）。
- **验证**：
  - `https://app.donglicao.com/` 与 `https://www.donglicao.com/developer/playground/` 均包含 `aliyun.donglicao.com` 相关引用。
  - `https://chat.donglicao.com/mobile/index.html` 返回 H5 入口，资源路径以 `/mobile/assets/` 开头。
  - `/health`、`/v1/chat/completions` 仍正常。

## 2026-07-02 深度瘦身 E1-E5 批次完成（低风险高收益）

- **计划基线**：`docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。采用「低风险高收益」范围 + 恢复 30-50 行缓冲，逐批 TDD 执行并在每批后跑 focused → full 门禁。
- **E1 归档**：
  - `findings.md` 3204 行 → 拆分为主体指针 + 两个归档档（`docs/archive/findings-2026-06-CN.md` ~2300 行、`docs/archive/findings-2026-06-audit-CN.md` ~750 行），主文 171 行仅留指针。
  - 7 个已落地 specs `git mv` 至 `docs/archive/superpowers-specs-2026-06/`。
  - `scripts/archive/openclaw_retired/` 7 个文件 `git rm`。
- **E2 测试合并**：`test_route_result_dataclass.py` 并入 `test_route_result.py`（~124 行，统一 base_result fixture）；`test_routing_engine_trace_spans.py` 并入 `test_routing_engine_trace.py`（~94 行）。
- **E3 死函数删除**：CodeGraph fan-in + ripgrep 复审 13 候选 → 12 个 0-fan-in / 0-grep / 无装饰器 / 无同文件引用 → AST 删除（保留有测试的 `record_backend_error`）。删除项：`alert_expired_tokens`、`get_active`、`backends_registry/__init__.get_backend`、`is_mqtt_enabled`、`mqtt_send_to_device`、`build_cached_prompt`、`task_fit_score`、`apply_lesson`、`estimate_context_usage`、`llm_summarizer_factory`、`is_retired_route_path`、`provider_snapshot`。
- **E4 贴顶文件拆分（6 个）**：所有新子模块统一用「父模块懒属性」模式（`import parent_module as _m; _m.SYM` 于函数体内调用而非导入期绑定），保证 `patch.object(parent_module, …)` / `monkeypatch.setattr(parent_module, attr, …)` 仍生效。
  - `routing_engine/__init__.py` 295 → 234：抽出 `route_pipeline.py`（`_classify_and_recall` + `_select_backends`）。（commit 66aa2ea7）
  - `routes/admin_api.py` 297 → 167：抽出 `routes/admin_backends_routes.py`（6 个后端 routes + `_backend_status_info` + `_admin_actor`，`import routes.admin_api as _a` 懒访问 `BACKENDS` 等）。（commit 42b1f86c）
  - `device_gateway/task_recorder.py` 300 → 161：抽出 `device_gateway/route_evidence_builder.py`（5 个 evidence 函数；`_persist_route_evidence` 用 `import device_gateway.task_recorder as _t` 破环）。（commit 0d02d53f）
  - `device_gateway/device_draw_handler.py` 299 → 276：抽出 `device_gateway/device_draw_config.py`（仅 `_resolve_draw_request` 24 行；未抽 `_generate_image` 因测试直接 `from … import _generate_image`）。（commit 2d4eb4f0）
  - `device_gateway/redis_store.py` 298 → 252：抽出 `device_gateway/redis_store_recover.py`（`RedisStoreRecoverMixin.recover_stale_processing`，`# type: ignore[attr-defined]` 处理 mixin 的 `self._redis`/`self._task_*`）。（commit dacbe563）
  - `provider_inventory/mcp_registries.py` 297 → 255：抽出 `provider_inventory/safemcp_scraper.py`（`SAFEMCP_URLS` + `_safemcp_entry` + `fetch_safemcp_index(fetch_text)`，`fetch_text` 注入为参数兼容 monkeypatch）。（commit 4a1a1860）
- **E5 贴顶函数抽 helper（6 个）**：所有原 50 行贴顶函数降为 < 50 行，恢复 30-50 缓冲，保持单一职责。
  - `routes/device_app_sharing.py::accept_share` → `_accept_share_lookup` + `_apply_share_accept_binding`。
  - `routes/device_app_task_templates.py::execute_task_template` → `_resolve_template_target` + `_bump_template_use_count`。
  - `routes/device_gateway_ws.py::handle_device_ws` → `_process_one_inbound_frame` + `_teardown_ws_session`。
  - `device_gateway/intent.py::_llm_replan` → `_build_llm_planner_prompt` + `_strip_code_fence` + `_interpret_llm_plan`。
  - `provider_automation/runner.py::_probe_one` → `_run_completion_smoke`/`_run_stream_smoke`/`_run_coding_fixture`/`_run_quality_gate`。
  - `provider_automation/admission.py::format_patch_plan` → `_format_additions_section` 等 4 个 section 渲染 helper。（commit d728f29d）
- **门禁**：`ruff check .` clean；`scripts/check_code_size.py` PASS（0 个 >300 行文件、0 个 >50 行函数）；全量 `pytest -q` → **4390 passed / 3 skipped / 2 deselected**（较瘦身前 +112，因 E3/E2 增删后测试结构调整）。
- **下次**：VPS 部署 + 公网冒烟 + 提交推送至 `origin/main`。

## 2026-07-02 深度瘦身 E6-E9 批次完成（长函数/退役端点/唤醒词抽离/台账同步）

- **背景**：E1-E5 已闭环（commit d728f29d + 51962676）。本轮继续按 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md` 推进剩余长函数提取、DEPRECATED 退役端点删除、唤醒词运行时抽离与 Ponytail 台账同步。
- **E6-1 长函数子辅助提取**：`lima_mcp_stdio/lima_codegraph_tools.py` 3 个 50 行贴顶函数（`tool_dependency_analysis` / `tool_search_symbols` / `tool_module_structure`）抽出 `_fetch_symbol_dependencies` / `_build_fts_query` / `_format_symbol_rows` / `_compute_module_dependencies`，文件降至 298 行。（commit 030f285e）
- **E6-2 provision 端点抽离**：`routes/device_app_misc.py` 296 → 199 行，两个 provision 端点（`/device/v1/app/devices/provision` + `/confirm`）连同 `_build_provision_response` / `_validate_provision_token` / `_complete_provision_binding` 抽到新模块 `routes/device_app_provision.py`（138 行，相同前缀）；`route_registry.py` 注册新模块；测试 `test_device_app_self_check.py` 同步 include provision_router 并将 `routes.device_app_misc.now` monkeypatch 改指 `routes.device_app_provision.now`。（commit f28ac745）
- **E6-3/E6-4/E6-5 经核验跳过**：`device_gateway/profiles.py` 295 行 / `routing_intent.py` 294 行（fn ≤41）/ `scripts/lima_feature_planner.py` 293 行 —— 三者本就在行/函数限额内，无需提取；E6-3 一次误拆导致 `profiles.py` 反增到 304 行（超标）已 `git checkout` 回退。
- **E7 退役端点删除**：移除 DEPRECATED v3.0 `routes/eval_internal.py`（`/internal/v1/eval/call` 410 Gone 桩）、`route_registry.py` 中 `_try_include` 注册行，以及 `test_routing_pipeline_authority.py::TestRoutingEngineAuthority::test_eval_internal_is_retired` 测试。全仓库（排除独立 worktree）已无 `eval_internal` 引用。
- **E8 唤醒词运行时抽离**：`data/digital-human/wakeword_runtime/runtime/http_server.py` 347 → 274 行；配置读/写/拼音转换（`build_wakeword_config_message` / `save_wakeword_config` / `build_keyword_line`，纯逻辑无 socket/self 依赖）抽到新模块 `wakeword_config.py`（96 行，带 `ponytail:` 标记说明 pypinyin 上限与升级路径）。`http_server.py` 内嵌 `TestRuntimeHandler` 保留闭包语义，仅改为委托新模块。WebSocket 帧逻辑因强依赖 `self.connection` 未抽（避免破坏未经测试的闭包）。
- **E9 PONYTAIL-DEBT.md 台账同步**：
  - 删除 6 个已在源码中移除的失效标记条目：`capability_matrix.py:132` / `device_gateway/task_creation.py:32` / `device_gateway/task_events.py:182` / `device_gateway/mqtt_client.py:81` / `client_keys/quota.py:33` / `chat-web/js/config.js:9`（文件已不存在）。
  - 修正 3 个偏移行号：`device_logic/activation.py` 25→26、54→55；`device_gateway/tasks.py` 31→33。
  - 补录 1 个新标记：`wakeword_runtime/runtime/wakeword_config.py:3`（pypinyin 依赖上限）。
- **门禁**：`ruff check` 改动文件 clean；`ruff format --check` 全过；`pyright` 改动文件 0 errors（1 warning：wakeword_config 的 `pypinyin` 可选依赖未解析，与 E8 前行为一致）；`scripts/check_code_size.py` PASS（0 个 >300 行文件、0 个 >50 行函数）；全量 `pytest -q` → **4388 passed / 3 skipped / 2 deselected**（较 E1-E5 收尾的 4390 −2：E7 删除退役端点测试 −1，E2 测试合并计数口径微调 −1；无新增失败）。
- **下次**：文档同步 + git commit/push origin + VPS 部署 + 公网冒烟。


## 2026-07-05 生产清理：SCNet sidecar 退役 + nginx .bak 清理 + JWT secret 轮换（已完成）

- **目标**：阶段 D（双节点标准化到 `/opt/dlc-drawing`）收尾后的遗留项清理——退役不再使用的 SCNet sidecar、清理 nginx 历史备份、轮换固定的 JWT secret。
- **SCNet sidecar 退役（Aliyun）**：
  - `lima-scnet-reverse.service`（:4505）`stop` + `disable`；unit 文件改名 `/etc/systemd/system/lima-scnet-reverse.service.retired-20260705`（可逆，非删除）。
  - 工作目录 `/opt/lima-router` **保留不动**——被 7+ 个 sidecar 引用（`lima-router-pilot`/`hermes-api`/`tts-proxy`/`mimo-proxy`/`litestream`/`longcat-web-proxy`/`kimi-proxy`），整体删除会破坏这些仍在运行的 AI 后端代理。`lima-voice.service` 工作目录是 `/opt/lima-voice`（独立），不受影响。
  - 两节点 `dlc-drawing/.env` 与 `lima-router/.env` 的 key 集合完全一致（dlc-drawing 为完整超集），无配置丢失风险。
- **nginx `.bak` 清理（两节点）**：
  - Aliyun `/etc/nginx/conf.d/*.bak*` **30 → 0**；JDCloud **3 → 0**（含 `sites-available/new-api.bak`）。
  - 清理前后 `nginx -t` 均通过，`systemctl reload nginx` 成功；活跃 `.conf` 全部保留。
  - 已知既存 warning（非本次引入）：JDCloud `api.donglicao.com` server name 在 :443/:80/:8443 重复，nginx 仅 warn 不影响运行。
- **JWT secret 轮换（两节点）**：
  - 旧 secret `xiaozhi-prod-secret-key-2026`（28 字节固定串，低于 RFC 7518 推荐的 32 字节）→ 新 secret（`secrets.token_urlsafe(32)`，43 字符 / 32 字节熵随机串）。
  - 两节点 `/opt/dlc-drawing/.env` 先 `cp -a` 备份为 `.env.bak-20260705-jwt`，再 `sed` 原地替换单值（符合「.env 合并而非覆盖」硬规则——备份 + 原地改值，非整文件覆盖）。
  - 两节点新 secret sha256 一致（`6352a64a22b8fd7f58340fa060a2ced377e3cad4d95326ed59e5009757dd460f`）；`dlc-drawing` 重启后 health 正常。
  - 诊断验证（每节点，`device_logic.auth.make_token`/`authorize`）：新 secret 签的 token `authorize()` 通过（返回 dict）；旧 secret 签的 token 返回 401（预期失效）。
  - **影响**：所有此前签发的设备/小程序 JWT 立即失效，客户端需重新登录——这是轮换的预期效果。
- **验证**：
  - 两节点 `:8081/health` → `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`。
  - 公网 `https://chat.donglicao.com/health` → HTTP 200。
  - systemd 最终状态：`dlc-drawing` active（两节点）；`lima-scnet-reverse` inactive（Aliyun，已退役）；`lima-router` disabled（两节点，退役）；`lima-router-pilot`/`lima-voice` active（Aliyun，保留）。
  - 诊断脚本 `/tmp/diag_jwt.py` 已清理；secret 值全程未打印。
- **未做/后续**：
  - `/opt/lima-router` 目录保留——彻底清理需先逐一审计 `hermes-api`/`tts-proxy`/`mimo-proxy`/`litestream`/`kimi-proxy`/`longcat-web-proxy` 等 sidecar 是否仍在使用，属独立任务。
  - JDCloud `api.donglicao.com` server name 冲突 warning 待单独排查。

## 2026-07-05 生产清理（续）：/opt/lima-router 部署备份裁剪（已完成）

- **背景**：阶段 D + SCNet/nginx/JWT 清理后，审计两节点 `/opt/lima-router`（Aliyun 1.1G / JDCloud 1.4G）的可回收空间。该目录不能整体删除——Aliyun 的 `lima-router-pilot`(:8080，免费后端 chat 路由) 仍通过 `mimo-proxy`/`longcat-web-proxy`/`kimi-proxy`/`hermes-api`/`tts-proxy` 等 sidecar 服务匿名 chat（chat-web / playground / manager-mobile H5），JDCloud 的 `litestream` 仍在复制 `health_state.db`。
- **安全裁剪**：只动 `unified-*`/`manual-*`/`dotenv-before-*` 部署快照，保留最近 5 份；**绝不碰 `backups/litestream/`**（JDCloud 占 553M，litestream 活跃副本存储）。
- **回收量**：
  - Aliyun：backups 473M → 261M（146 份部署快照裁掉 141 份），`tmp_sonic.tar.gz` 7.7M 删除；`/opt/lima-router` 1.1G → 871M。
  - JDCloud：backups 599M → 560M（24 份裁掉 19 份，litestream 553M 完整保留）；`/opt/lima-router` 1.4G → 1.3G。
  - 合计回收约 **260MB**。
- **未动（有引用或风险）**：`logs/`（全部 <7 天，rotation 已生效）、`router_model.pkl`（`local_router.py` 等引用）、`opencode-source/`（`opencode_*.py` 引用）、`data/`（多个 .db 含 litestream 源）、活跃 sidecar 进程。
- **验证**：裁剪后两节点 `dlc-drawing` + 全部活跃 sidecar（pilot/hermes/tts/mimo/longcat/kimi/voice + litestream）均 active；`:8081/health` 正常。
- **后续更大决策（需用户拍板）**：彻底退役 `lima-router-pilot`(:8080) 可连带下线 mimo/longcat/kimi/hermes/tts sidecar 并再回收数百 MB，但会影响 chat-web/playground/manager-mobile H5 的匿名免费 chat——属产品级决策。

## 2026-07-05 Aliyun pilot 免费 chat 链路退役

- **背景**：审计确认 pilot(:8080) 入站真实流量为 0（详见 findings.md 同日条目），24h 空转探测失效后端，连带 6 个 sidecar。用户批准退役。
- **阶段1（切前端引用）**：改 4 文件——`cloudflare/workers/chat-router.js`（移除 pilot 分支，恒回源 JDCloud）、`cloudflare/wrangler.toml`（删 PILOT_ORIGIN）、`chat-web/js/app-config.js`（shouldUsePilot 恒 false，保留 window.LiMaConfig 接口）、`donglicao-site-v2/app/developer/playground/page.tsx`（selectBaseUrl 恒主节点 + placeholder 文案）。commit + push origin main。
- **既存 CI 修复**：`deploy-chat-web.yml` 补 `npm install`（修 7-03 起连续失败的 esbuild ERR_MODULE_NOT_FOUND）；`test.yml` pyright 路径 `server.py routing_engine/__init__.py routes/chat_endpoints.py` → `server_dlc.py`（P4/P5 已删旧文件）。
- **部署验证**：GitHub Actions `Deploy Chat Router Worker` / `Deploy Next.js Site` / `Deploy Chat Web` 均 success；`curl chat.donglicao.com/v1/chat/completions` 响应头 `X-Lima-Backend: jdcloud`（不再 aliyun），确认前端已不走 pilot。
- **阶段3（停后端）**：停服前只读复核——nginx proxy_pass 不直接指向任何 sidecar 端口；pilot :8080 established 连接空、journal 无新入站。逐个 stop+disable，unit 改名 `.retired-20260705`：`lima-router-pilot`/`mimo-proxy`/`longcat-web-proxy`/`kimi-proxy`/`hermes-api`/`tts-proxy`。daemon-reload + reset-failed。:8080 端口释放。
- **终态验证**：两节点 `dlc-drawing` :8081/health ok；`lima-voice`(Aliyun)/`litestream`(JDCloud)/nginx 未受影响；`:8080` FREE。`/opt/lima-router-pilot`(1.1G) 仅停服未删。
- **回滚**：前端 `git revert` → Actions 自动回滚；后端 unit `.retired-20260705` 改回原名 → daemon-reload → enable --now。

## 2026-07-05 Deploy workflow SSH 根因修复 + pilot 目录回收

- **背景**：pilot 退役后 `Deploy` workflow 仍 failure；调查确认与 pilot 退役无关，是 P4/P5 瘦身遗留的部署自动化配置 bug。
- **根因（两缺陷叠加）**：
  1. `.github/workflows/deploy.yml` 主部署步骤名 "Deploy Aliyun primary"，`ssh-keyscan` 扫的是 `VPS_HOST`(Aliyun)，但 `deploy_unified.py` 未传 `--target` → 默认 `jdcloud`（连 117.72.118.95）。known_hosts 无 JDCloud key → `configure_ssh_host_keys` 的 `RejectPolicy` 抛 `SSHException`。
  2. `scripts/deploy_unified_common.py::_connect_ssh` 的密码回退路径复用同一个 `RejectPolicy` 的 ssh 对象，host key 仍未知 → 第二次 connect 在 `missing_host_key` 再抛 `SSHException`，无 except 包裹 → 崩溃（CI traceback 落点）。
- **修复（最小改动，只改 workflow）**：主部署步骤对齐到 JDCloud（生产入口 `chat.donglicao.com` 经 CF Tunnel 指向 JDCloud，`verify` 步骤与脚本默认 target 均为 jdcloud）——`ssh-keyscan` 改扫 `JDCLOUD_HOST`、加 `if: JDCLOUD_HOST_SET` 守卫、env 补 `LIMA_JDCLOUD_SERVER`、调用显式 `--target jdcloud`，与下方已工作的 probe 步骤一致。未改 `_connect_ssh` 生产 SSH 逻辑（host key 命中后回退路径不再触发）。
- **行为变更（需知悉）**：主步骤原意图部署 Aliyun（实际因崩溃从未成功），现纠正为部署 JDCloud。**Aliyun 节点不再由本 workflow 自动部署**；如需部署 Aliyun 应手动 `LIMA_DEPLOY_TARGET=aliyun` 或 `--target aliyun`。
- **验证**：commit `a49ebe17` 后 `Deploy` workflow 三条全绿（Deploy / Tests / CodeQL）；deploy job 各步骤真跑通（非跳过）：`Deploy JDCloud primary` + `Verify production deployment`（`chat.donglicao.com/health` + L2 限流）+ `Deploy JDCloud provider probe` 均 success。
- **顺带修复的既存 CI 债**（pilot 退役期间暴露）：
  - `deploy-chat-web.yml`：build 前缺 `npm install` → `esbuild` ERR_MODULE_NOT_FOUND（自 7-03 连续失败）。加 `npm install` 步骤。
  - `test.yml`：`Type check authority files` 仍 pyright 已删的 `server.py`/`routing_engine/__init__.py`/`routes/chat_endpoints.py`（exit 4）。改指现存入口 `server_dlc.py`。**`Tests` workflow 恢复绿灯**（7-01 以来首次）。
  - `scripts/verify_production_deploy.py`：断言已退役的 `/device/v1/health`(404) + `metrics`(410 Gone)。精简为只检 `/health` + L2 限流；删死函数 `_check_metrics`/`_load_key` 及孤立 `Path`/`ROOT`。
- **pilot 目录回收**：`/opt/lima-router-pilot`（1.1G，仅停服的孤儿）复核无引用（仅 `.retired` unit）后删除；env 文件（`.env`+`.env.merged`，含密钥）先备份到 VPS `/root/lima-router-pilot-env-backup-20260705.tar.gz`（chmod 600）。磁盘 used 22G→21G。`dlc-drawing` 仍健康。`/opt/lima-router` 保留（`litestream` 仍依赖其复制 `health_state.db`）。

## 2026-07-05 生产目录彻底回收：/opt/lima-router* 三处清理

- **背景**：pilot 链路退役后，`/opt/lima-router-pilot` 与两节点 `/opt/lima-router` 成为仅停服的孤儿目录，占用大量磁盘。
- **`/opt/lima-router-pilot`（Aliyun，1.1G）**：唯一引用是已退役 `.retired` unit，nginx/进程/cron 无引用，自包含无独有数据库。备份 `.env`+`.env.merged`（含密钥）→ `/root/lima-router-pilot-env-backup-20260705.tar.gz`（600）后删除。磁盘 22G→21G used。
- **`/opt/lima-router`（Aliyun，871M）**：所有引用服务（lima-router / litestream / sidecar）全部 inactive，无 active 引用（`systemctl` 逐服务 grep 确认 0 ACTIVE-REF）。备份 `.env`+data 小型 db+litestream 配置（不含 120M chroma 死向量库）→ `/root/lima-router-aliyun-backup-20260705.tar.gz`（600）后删除。磁盘 21G→20G used。lima-voice 仍 active 不受影响。
- **`/opt/lima-router`（JDCloud，1.3G）**：`litestream.service` 仍 active，但其复制的 `health_state.db` 写入者（旧 lima-router）已退役，mtime 停在 18:21（回收时 23:16，陈旧 5h），dlc-drawing 用独立 `/opt/dlc-drawing/data/health_state.db`——litestream 在持续备份死库。停 litestream（stop+disable+unit 改名 `.retired-20260705`，可逆）→ 确认 `fuser` 无持有者 → 备份 `.env`+小 db+litestream 配置 → 删除。磁盘 26G→25G used。dlc-drawing 健康。
- **保留恢复凭据**：三处 unit 均改名 `.retired-20260705` 而非删除；三份备份 tar 保留在各节点 `/root`。
- **回收合计**：Aliyun ~2G（pilot 1.1G + lima-router 871M）+ JDCloud 1.3G ≈ 3.3G。
- **Deploy workflow 修复**：`deploy.yml` 主部署步骤从误标的 "Aliyun primary"（keyscan 扫 VPS_HOST 却因脚本默认 target=jdcloud 实连 JDCloud、host key 不匹配→RejectPolicy→密码回退撞同一策略再抛→崩溃）对齐到 JDCloud（keyscan JDCLOUD_HOST + 显式 `--target jdcloud` + JDCLOUD_HOST_SET 守卫）。`Deploy`/`Tests`/`CodeQL` 三条 workflow 恢复全绿，deploy job 各步骤真跑通（部署+verify+probe 均 success）。⚠️ 行为变更：Aliyun 不再由该 workflow 自动部署（生产入口本就是 JDCloud）。

## 2026-07-06 设备网关自托管 WS/MQTT 下发链退役（死代码物理删除）

- **前提**：用户确认「研发阶段，无线上存量设备依赖 `chat.donglicao.com` 的 `/device/v1/ws`」，解除 findings.md 记录的唯一阻塞点。
- **已核实**：生产入口 `server_dlc.py` 不注册 WS 端点、不启动任何 gateway runtime；`start_device_gateway_runtime`/`start_mqtt_client`/`start_task_notifier` 全仓无生产调用者；`dispatch_or_enqueue` 的 `registry.get()` 因无 WS 会话恒返回 None → WS 分支为死代码。
- **删除**（Plan mode 批准，coder subagent 执行 + 主 agent 核验）：
  - `device_gateway/`：`mqtt_client.py`、`mqtt_handlers.py`、`mqtt_topics.py`、`health.py`（孤儿）、`notifier.py`、`attestation.py`、`protocol.py`、`protocol_frames.py`、`protocol_validators.py`、`protocol_negotiator.py`
  - `routes/`：`device_gateway_dispatch.py`、`device_gateway_helpers.py`
  - 根：`device_ws_ticket.py`（删 dispatch 后成孤儿，`/device/v1/ws` 一次性票据）
  - 测试：`test_device_mqtt_transport.py`、`test_device_gateway_dispatch.py`、`test_routes_device_gateway_dispatch.py` 删除；`test_device_task_metrics.py`、`test_device_gateway_motion_contract.py`、`test_device_gateway_protocol.py`、`test_run_path_intent.py`、`device_gateway/{conftest,test_sessions}.py` 调整
- **简化**（行为等价，生产本就恒 queued）：`device_logic/gateway.py::dispatch_or_enqueue` 与 `device_gateway/tasks.py::create_and_route_task` 去掉恒不执行的 WS 会话分支，只保留 `enqueue_pending_task` + metrics，返回契约不变。
- **保留**：`protocol_families.py`（绘图核心校验）、`sessions.py`（registry 被 `device_app_api._build_device_status` 生产引用）、全部绘图/任务/gallery 核心模块。
- **未动**（最小改动，避免误伤）：`.env.example` 的 `LIMA_DEVICE_REDIS_URL` 仍被 `device_gateway/store.py` 使用不可删；`LIMA_DEVICE_WS_URL`/`session_bus` 字段成未用配置但无害，暂留。
- **门禁**：基线 1407 passed → 退役后 **1349 passed / 3 skipped**（−58 为删掉的 WS/mqtt/dispatch/protocol 用例）；`ruff check` clean；`check_code_size` PASS；`codegraph_orphans` 清理 `device_ws_ticket` 后无新孤儿（`test_repo_hygiene` 因未跟踪 `.cocoindex_code/`/`.serena/` 失败，与本次无关，基线即存在）。

## 2026-07-06 打通语音 → MCP → 绘图核心链路（dlc-mcp 接入小智云）

- **前提**：用户提供小智云智能体 MCP endpoint token（`wss://api.xiaozhi.me/mcp/?token=<JWT>`，有效期至 2027-06），解除 STATUS.md:57 长期挂着的「待操作」。
- **调查发现两个 P0 缺口**（读 `dlc_mcp/{mcp_pipe,server}.py` + `dlc_api` 路由 + deps）：
  1. **鉴权缺口**：`dlc_api` 的 `/dlc/tasks/dispatch`、`/dlc/devices/{id}/status` 都 `Depends(verify_dlc_api_token)`（需 `Authorization: Bearer` + `device_id==token所属设备`），但 `server.py::_submit/_get_json` 是裸请求 → 必 401。
  2. **MCP ping 缺口**：`handle_request` 不处理 MCP `ping` keepalive，回 `-32601` → 小智云判协议违规每 ~24s 断连，`mcp_pipe` 无重连 → systemd crash-loop。
- **修复**（TDD，`.venv310`）：
  - `server.py`：新增 `DLC_API_TOKEN` env → `_auth_headers()` 注入 `Authorization: Bearer`；补 `ping`→空 result、`notifications/*`→不回复；默认 `DLC_API_URL` `18080`→`8081`（对齐生产）。
  - `mcp_pipe.py`：抽 `_run_session`，`run_bridge` 包指数退避重连循环（1→30s），`CancelledError` 放行以便 systemd 干净停止。
  - `deploy/aliyun/dlc-mcp.service`：路径 `/opt/lima-router`→`/opt/dlc-drawing`、venv python、`ExecStart` 修正 server_cmd 带解释器前缀（原裸 `server.py` → PermissionError）。
  - `deploy/aliyun/install_dlc_mcp.sh`：`.env` 路径 + 端口提示对齐。
- **部署**：token 合并进 VPS `/opt/dlc-drawing/.env`（备份 `.env.bak-20260705-mcp` + chmod 600，token 全程不回显不入 git）；代码经 sftp 同步（md5 校验落地）；`install_dlc_mcp.sh` 装服务 enable。
- **验证**：MCP 握手全通（initialize / notifications/initialized / tools/list 返回 4 个 dlc.* 工具 / ping）；`dev-test-1` 带 token dispatch → HTTP 200 `{"status":"queued","task_id":...}`（无 token 422）；服务连续存活 >3.5min、`ConnectionClosedError`=0、`NRestarts`=0。
- **门禁**：`tests/test_dlc_mcp_server.py` 17 passed；ruff + format + check_code_size PASS。提交 `360a413b`（auth+路径）+ 后续 commit（ping+重连）已 push origin main。
- **诚实边界**：VPS 仅占位设备 `dev-test-1`、无真实绘图机硬件，故链路验证止于「任务入队」；固件端 `HandleMotionTaskJson` 执行 + 语音端到端待有设备接入后验证。

## 2026-07-12 优化计划 C/D 京东云 VPS 部署 + 模块级验证（全 PASS）

- **部署**：`deploy_unified.py --target jdcloud --files rate_limiter.py device_gateway/redis_store.py device_gateway/redis_store_helpers.py device_gateway/redis_store_index.py`；自动依赖 10 个文件经 md5 比对与 VPS 完全一致（无害上传）。备份 `/opt/dlc-drawing/backups/unified-files-20260712_013319/`；重启后 health OK（version 0.4.0-p3）；4 文件 VPS md5 == 本地 md5。
- **验证方式**：开关均为调用时读 env，故在 VPS 用生产 venv 直接 import 模块验证（脚本 `/tmp/verify_cd_remote.py`，跑后即删），隔离命名空间 `lima:verify:*` + 测试 IP `203.0.113.99`，**未改 .env、未开总限流、零生产数据/流量影响**，全部写入已清理并验证为空。
- **D（`LIMA_REDIS_TASK_INDEX`，生产 Redis 100.85.114.65）**：flag=1 → `task_idx:{device_id}` set 含 task_id ✅、索引读路径 `list_tasks_for_device` 返回该任务 ✅、索引 key 带 TTL ✅；flag=0 → 不写索引 ✅。
- **C（`LIMA_IP_RATE_REDIS`）**：flag=0 → 无 `lima:ip_rate:*` key（纯内存）✅；flag=1 → key 创建、5 次调用计数累加为 5（INCR 跨调用一致）✅、TTL ∈ (0,61] ✅。
- **结论**：两开关在生产环境（真实 Redis、生产 venv）行为正确。但 C 当前无生产调用方（详见 findings.md 同日条目），「双 worker 计数一致性」待其接入路由后才有验证意义；Redis INCR 原子性 + `tests/test_rate_limiter_redis.py` 已覆盖该性质。

## 2026-07-12 删除优化计划 C（无生产调用方的 IP Redis 限流，ponytail）

- **背景**：VPS 验证发现 `check_rate_limit` 生产零调用方（详见 findings.md 同日条目），用户决策删除而非接线。
- **删除**：`rate_limiter.py` 的 `_check_ip_redis`/`_ip_rate_redis_flag`/`_IP_RATE_REDIS_KEY` + `import os`（`check_rate_limit` 回归纯内存滑动窗口）；`tests/test_rate_limiter_redis.py` 整文件（11 用例只覆盖该特性）；`.env.example` 的 `LIMA_IP_RATE_REDIS` 注释块。
- **保留**：keyed Redis 限流（`check_keyed_rate_limit`，device auth L2，生产在用）与 D（task 二级索引，已验证）。
- **门禁**：聚焦测试 22 passed；ruff clean。
- **后续**：VPS 重新部署删除后的 `rate_limiter.py` 保持版本一致（无行为变化：该路径本就无调用方）。

## 2026-07-12 修复 3 个预存在红测试（test_dlc_api draw-from-image）

- **根因**：SEC-04 校验从 `dlc_api/routes.py` 移到 `device_gateway/image_url_validation.py` 后，测试里的 DNS stub 仍 patch 旧位置 `dlc_api.routes._resolve_hostname`（该属性已不存在，赋值成死属性），导致 `validate_image_url` 走真实 DNS——本机 api.telegram.org 被 DNS 污染解析到保留地址，SSRF 守卫正确拦截，用例随之失败。实现无跑偏。
- **修复**：改为 autouse fixture + monkeypatch 补 `device_gateway.image_url_validation._resolve_hostname`（返回公网 Telegram IP），与 `tests/test_sec04_ssrf_hardening.py` 的补法一致；自动还原不污染其他测试文件。
- **门禁**：全量 **1536 passed / 3 skipped / 0 failed**（此前 3 failed）；ruff clean。

## 2026-07-12 安全审查闭环（P0→HIGH→MEDIUM→LOW）+ 京东云部署

- **范围**：深度 code review 后按严重度分批修复并推送，最后同步京东云生产。
- **提交**：
  - P0 `cd1780d4`：gallery IDOR、Host 头 WS URL、假 queued → `queued_no_delivery`、lifespan 配置 fail-fast
  - HIGH `ba6544f2` + 固件 `91cb4ea`：i2i SSRF、bind 限流、list tasks `deviceId` alias、U1 `ENABLE_AUTHENTICATION`（`allow_dashscope` 按 Q-02 不改）
  - MEDIUM `9974bec4`：health 期望 redis 但 backend≠redis → 503；`token_epoch`+`tv` 改密吊销；voice `consume_if`；幂等日志措辞（fail-open+L1 保留）
  - LOW `1592c882`：gallery 异常不回传 bot token、env token 常量时间比较、share 过期校验/上限、MAX_PATH_POINTS 单一定义、prompt max_length、store 公开 ping/close、SVG escape、mcp 版本对齐、usage 测试
  - 固件 LOW `4de9ae9`：control WS token 常量时间比较；activation 失败日志去掉完整 body
- **门禁**：全量 **1574 passed / 3 skipped**；ruff clean。
- **部署（jdcloud `/opt/dlc-drawing`）**：
  - `deploy_unified.py --files` 因 auto-deps 膨胀 + SFTP 中途 `Socket is closed` 两次失败；改为直传 12 个仍 DIFF 文件 + 既有已对齐文件 md5 复核。
  - 20 个安全相关生产文件 **md5 全匹配**；`systemctl restart dlc-drawing` → active。
  - `/health` → `ok` / `task_store=redis`；`v2_account.token_epoch` 列已存在（migrations 在 connect 时生效）。
  - 公网 `chat.donglicao.com/health` 从本机 403（Cloudflare 1010，非服务故障）；VPS 本机探针 200。
- **未做**：`device_app_tasks.py` 306 行拆分（债）；IDF floor 5.5.2→5.5.3（升构建风险/收益低）；固件 `control_ws_token` 写入者（已是 fail-closed 拒绝无 token 握手）。
- **部署教训**：`expand_with_dependencies` 把 12 文件扩到 160+，SFTP 长连接易断；精确 diff 列表 + 直传 SFTP 更稳。

## 2026-07-12 拆分 device_app_tasks（≤300 行）+ 京东云部署

- **背景**：`routes/device_app_tasks.py` 306 行触碰单文件硬限；LOW 债项。
- **A2A**：MiMo `2d05007e` 失败（`Request blocked by risk control`）；改派 Atom `04595ba1` 成功（~246s）。
- **改动**（`f122c3a7`）：新建 `routes/device_app_task_create.py`（创建路径 helpers + 常量）；`device_app_tasks.py` 196 行仅路由；extras/templates import 同步；测试 patch 同步。
- **门禁**：聚焦 41 passed；ruff + `check_code_size` PASS。API 语义未改（deviceId alias、`_account_id` re-inject）。
- **部署**：直传 4 文件到 jdcloud `/opt/dlc-drawing`，md5 全匹配；`systemctl restart dlc-drawing` → active；`/health` ok + `task_store=redis`；生产 venv import `device_app_task_create` OK。
- **附带**：`scripts/a2a_mimo_dispatch.js`；教训：MCP send_message 轮询易 Unknown task，实现派活用 `a2a_dispatch.py`；MiMo 风控时改 Atom/Grok。

## 2026-07-12 Aliyun 对齐安全修复 + tasks 拆分（0.2.0-p1 → 0.4.0-p3）

- **背景**：jdcloud 已是 `0.4.0-p3` + 安全审查 + tasks 拆分；aliyun 仍 `0.2.0-p1`，关键安全文件 23/23 DIFF，且缺 voice/gallery 栈。
- **部署策略**：直传安全核心 + `server_dlc` 启动必需（voice/chat/gallery 依赖）+ redis_store 全家桶；**import 探针通过后再 restart**，避免半升级 crash-loop。
- **过程**：
  1. 首批 38 文件 md5 全匹配，但 import 缺 `device_logic.audio_clips` → **未重启**。
  2. 迭代补：`audio_clips`/`audio_store`/`chat_store`/`gallery_service`/`gallery_storage`/`middleware`。
  3. 重启后 lifespan 缺 `redis_store_index` → 再传 redis_store 相关 7 文件。
  4. 最终：startup complete，`/health` 200。
- **终态（两节点）**：
  - aliyun/jdcloud：`dlc-drawing` active；`version=0.4.0-p3`；`task_store=redis`。
  - 抽样 9 关键文件（含 `server_dlc`/`task_create`/`auth`/`gallery`/`images`/`voice_ticket`）**md5 双端 == 本地**。
- **备份**：aliyun `/opt/dlc-drawing/backups/aliyun-security-20260712_100707/pre.tgz`。
- **未做**：aliyun 全量 `slice core`（依赖膨胀/SSH 易断）；仅保证安全路径与启动闭包对齐。

## 2026-07-12 代码尺寸债清理（文件 ≤300 + voice 函数 ≤50）

- **测试拆分**（`f550253d`）：`test_device_app_tasks` / `test_dlc_api` / `test_device_app_notifications` 拆为 6 文件，均 ≤227 行；36 passed。
- **gallery apply 脚本**（`4c26a5ad`）：内嵌 TS/Vue 模板抽到 `scripts/miniprogram_gallery_templates/`；`apply_miniprogram_gallery_v2.py` 760→91、`improvements` 578→113。
- **主仓扫描**：第一方包（routes/dlc_*/device_*/scripts/tests 等）**0 个文件 >300 行**。
- **voice 函数拆分**（本提交）：
  - `routes/device_app_voice_ws.py`：`_run_voice_stream_ws` 69 行 → open/frame/control/loop/finalize 小函数（最大 19 行）。
  - `routes/device_app_voice.py`：`transcribe_voice` 66 行 → read/transcribe/persist helpers（endpoint 41 行）。
- **门禁**：voice 相关 29 passed；ruff clean。语义未改。

## 2026-07-12 生产函数 ≤50 行拆分（draw/path/images/notifications）

- **task_draw_params**：`build_draw_generated_params` 拆 resolve/finalize helpers；handwriting 抽到 `device_gateway/task_handwriting_params.py`（文件 304→201）。
- **path_validator**：`validate_capability_params` 拆 required/scalar helpers。
- **device_app_images / images**：endpoint 与 `_generate_image_urls` 抽 parse/options/i2i/backends helpers。
- **notifications**：subscribe 抽 parse/insert helpers。
- **门禁**：相关 93 passed；`check_code_size` 目标文件 PASS；语义未改。

## 2026-07-12 生产函数 ≤50 行扫尾 + Aliyun 内存说明

- **model_routing.try_backends**：抽 `_should_continue_fallback`，主函数 ≤50。
- **device_voice.providers.dashscope._transcribe_sync**：抽 collector/stream helpers，主函数 ≤50。
- **扫描**：`routes/dlc_*/device_gateway/device_logic/device_voice` 等第一方生产路径 **0 个函数 >50 行**。
- **门禁**：fallback/voice 相关 38 passed；ruff clean。
- **Aliyun 运维**：1.8G 节点 flaresolverr 多 Chromium 时 available 可跌至 ~140MB，uvicorn 卡在 swap、unit 显示 active 但不 listen。处理：`podman restart flaresolverr` 释放内存后 `systemctl start dlc-drawing`。

## 2026-07-12 运维脚本函数 ≤50 行扫尾（无功能变更）

- `gallery_e2e_probe.run_gallery_e2e_probes`：拆 upload/list/thumbs/download/delete 子探针。
- `check_newapi_cache_health`：`check_server_env` / `main` 拆 parse/score/status/sidecar/kimi/claude helpers。
- `migrate_newapi_sqlite_to_mysql` / `deploy_newapi_healthcheck`：`main` 拆 connect/upload/redact 与 remote cmd 组装。
- **扫描**：`scripts/*.py` 与生产包 **0 个函数 >50 行**；行为未改（纯结构拆分）。

## 2026-07-12 修复 P0 append_event_atomic Lua ARGV 错位

- **根因**：`_APPEND_EVENT_LUA` 约定 ARGV[1]=task_id，Python `script(args=)` 漏传 task_id，真 Redis 下 HGET 用 event JSON 当 field → 恒 miss。
- **修复**：`args=[task_id, encode_redis_json(event), new_status, ttl_seconds]`。
- **测试**：`_FakeRedisWithScript` 走 `register_script` 路径，断言 ARGV[0]==task_id；缺任务返回 None。旧 Fake 无 script 仍覆盖 fallback。
- **门禁**：`tests/test_redis_task_cas.py` 等 24 passed。
