# 审查发现矩阵（修复前冻结）

冻结日期：2026-07-16。以下 `confirmed` 均由主线程再次回溯真实入口、数据源和设计文档；
`risk/debt` 不冒充线上缺陷，也不因建议性加固阻断产品修复。

## High / confirmed

| ID | 位置 | 触发与影响 | 最小修复方向 |
| --- | --- | --- | --- |
| DEP-01 | `scripts/deploy_unified.py:43-55`、`deploy_unified_common.py:64-92,163-178` | 默认 core 遍历工作树，当前 596 文件，含 ignored 日志/tmp/音频/`nginx.exe`；本地数据泄漏并污染 VPS | core 只取 git-tracked CORE allowlist；all 也禁止 ignored/untracked；补 manifest 回归 |
| DEP-02 | `deploy/nginx/chat.donglicao.com.conf:84-113`、`deploy_unified_nginx.py:85-90` | 公网 health/readiness 与 nginx sync 检查退役 :8080；真实服务为 :8081 | 8081 同时提供 health/ready；两个 nginx 权威副本和 sync probe 对齐 |
| DEP-03 | `deploy_unified_preflight.py:38-57,83-100`、`deploy_unified.py:58-89,147-180`、`deploy_unified_restart.py:49-89` | 部分上传、新文件、`--remove`、unit 变更无法完整回滚；files+remove 删除后不再 health | 备份上传+删除+unit 的 pre-state；失败统一恢复/删除新增项；一次 restart 后验证 |
| DEP-04 | `.github/workflows/deploy.yml:39-42`、`deploy_unified_restart.py:49-89` | CI runner 安装依赖，但 VPS 不安装；requirements 变化上线后远端 venv 漂移/ImportError | requirements 变化时构建新 venv、import smoke、原子切换并可回滚 |
| DEP-05 | `.github/workflows/deploy.yml:69-74` | 只比较 `HEAD~1..HEAD` 且排除删除；多提交 push 漏文件，远端孤儿不删除 | 使用 push `before..sha`，D 映射 `--remove`，服务端再次校验 runtime allowlist |
| AUT-01 | `routes/device_app_provision.py:173-229`、`device_logic/crud.py:89-114` | 任意登录账户可为任意未绑定 SN 生成 token，并自行调用公开 confirm 完成 owner 绑定 | 未有设备证明前停用该未落地 provision 流；保留已有 activation/bind 主路径 |
| MCP-01 | `dlc_mcp/server.py:89-118,132-140,182-193` | HTTP 401/403/422/500/非 JSON 可被输出为“任务已提交”或空状态 | 非 2xx fail-loud，稳定提取 detail/error，覆盖 POST/GET 失败矩阵 |

## Medium / confirmed

| ID | 位置 | 触发与影响 | 最小修复方向 |
| --- | --- | --- | --- |
| AUT-02 | `dlc_api/deps.py:35-60,92-129` | DB 任意异常时生产接受 env emergency token；已撤销 token 可恢复访问 | production 默认 fail-closed；仅显式 break-glass flag 允许 env fallback |
| AUT-03 | `device_logic/access.py:13-20`、`notifications.py:183-206`、`device_app_sharing.py:116-129` | 分享撤销/过期后旧 active notification subscription 仍发送设备事件 | 派发时复核 owner/有效 share；revoke/unbind 同步失活订阅 |
| AUT-04 | `device_app_chat.py:51-95`、`chat_store.py:248-284` | 客户端复用其他设备 `audioId`，UPDATE 按全局 id 覆盖 victim 元数据 | 写前按 device_id 校验冲突；跨设备 409；文件写失败/拒绝时清理 |
| VOI-01 | `device_voice/asr.py:32-34`、provider `to_thread`、voice REST/WS finalize | SDK/模型卡住时请求、线程和 WS slot 无总 deadline | 配置统一 deadline；云 SDK 原生超时；本地推理并发上限 |
| VOI-02 | `routes/device_app_voice_ws.py:69-86,139-193` | `websocket.receive()` 无限等待，默认每账号 3 槽可永久占用 | idle + absolute session timeout，超时后关闭 session 并释放 slot |
| WS-01 | `routes/device_app_status_ws.py:120-180` | 可无限签 ticket/建长连接，每 5s 访问 store，无账户/设备连接上限 | ticket keyed rate limit、并发 cap、session age、finally 释放 |
| ASY-01 | `redis_store_helpers.py:34-44`、`dlc_core/dispatch.py:25-60`、`tasks.py:89-128` | 同步 redis-py 直接运行在 async dispatch 热路径，故障可冻结单 worker 数秒 | 在 async 边界整体 `to_thread` 同步工作单元；避免拆散事务 |
| IDE-01 | `dlc_api/idempotency.py:86-105,130-159` | L1 claim 后 Redis 恢复时 L1 被绕过；release 也可能只清一层 | claim/release 始终协调 L1+L2，保留 compare-and-delete |
| QA-01 | `scripts/check_code_size.py:25-99`、`run_pre_commit_check.py:127-138` | 默认错扫 `.venv`，tracked 错扫 `.trellis`，full 还把失败降 warning | 产品树 allowlist/排除工具树；full/CI size failure 必须非零 |
| QA-02 | `device_gateway/redis_store.py`、多处活跃函数 | 排除工具树后仍有 2 个 >300 行文件、9 个 >50 行函数，硬门禁红 | 仅按职责做最小拆分，测试辅助超限同步拆分 |
| CI-01 | `.github/workflows/test.yml:66-71`、`tests/test_secret_hygiene.py:7-12` | Bandit 漏掉多数生产包且含不存在目录；secret test 扫描已删除文件，空跑绿 | 用活跃 runtime 包常量；目标不存在即失败；secret 扫 git/deploy manifest |
| CNT-01 | `Dockerfile:17-20`、`.dockerignore`、`docker-compose.yml` | `COPY . .` 可把 ignored 日志/nginx 二进制烘入镜像；compose 两服务争用 host 8081 | 显式 runtime COPY/补 ignore；searxng 改独立 host port |
| ENV-01 | `deploy_unified_restart.py:49-71` | “.env 备份后合并”规范未实现；已有 env 永不补新必需键 | 仅合并显式模板键，保留现值，先 0600 备份并纳入 rollback |
| FW-01 | `esp32S_XYZ/firmware/u1-grbl/platformio.ini:42-100` | native env 继承 `board=esp32dev`，0 tests executed | 需固件/PlatformIO skill 后调整 env 继承并复跑 |
| FZ-01 | `fz/hardware_sim/run_hw_sim.py:87-129,559-588`、`case_runner.py:159-230` | 运行中读取仅在进程退出后保证 flush 的 step log，五个 step_window 假红 | 在 fz 改为可同步观测/分例进程或退出后窗口；复跑 standard |

## Low / risk / design debt

- `TYP-01 confirmed Low`：`DeviceTaskStore` 缺 `ping/close` Protocol，造成 2 个 Pyright warnings。
- `TST-01 risk`：U8 native test 在测试文件重实现生产纯函数，不能证明真实固件逻辑。
- `RED-01 Low`：Redis enqueue 的 RPUSH/TTL/CAS 非原子；当前队列明确 `queued_no_delivery`、无生产消费者，故不定为运动 Medium。
- `SQL-01 debt`：大量 async 路由内同步 SQLite 可能在锁竞争时阻塞；缺少线上/压力证据，作为架构风险而非本轮全量改写理由。
- `SUP-01 risk`：`npx ...@latest`、Actions major tag、CI 工具浮动降低供应链可复现性；先移除 `@latest` 执行，完整 SHA/哈希锁由依赖更新机制承接。
- `OPS-01 debt`：systemd 以 root 且隔离较少；需结合 VPS 写目录/HIL 做独立 rollout，不在无部署验证下盲改。
- `DOC-01 confirmed drift`：公开 SDK/docs/worker 仍发布退役 chat/self-hosted WS；修复是标废/拆分归属，不恢复 `/device/v1/ws`。
- `LOG-01 Low`：prompt/text 与带 gallery token 的异常 URL 可能进入日志，需统一脱敏。

## 已排除

- `/device/v1/ws` 未注册不是 8081 bug：用户已确认无存量设备，服务端链路于 2026-07-06 退役。
- gallery token purpose/account/image/expiry 绑定正确；图片 URL 有 host allowlist、IP pinning且禁重定向，未确认 SSRF。
- JWT exp/account active/token_epoch、任务/设备/gallery 直接 IDOR、路径/SQL/命令注入候选未成立。
- Redis event/CAS/recovery 已使用 Lua/CAS；不能泛化为普通读改写丢更新。
- fz MPos 正确，当前红灯不能证明产品运动错误；Host SIL 也不能证明纸路/BT/OTA/HIL。
