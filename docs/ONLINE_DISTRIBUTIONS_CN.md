# LiMa 在线分布

> 更新时间: 2026-06-09
> 范围: 属于 LiMa 项目且必须由此仓库控制的 VPS 托管公共服务面。

## 规则

官方网站、开放平台、聊天界面、FRP 端点、nginx 边缘及支撑公共服务均属于 LiMa 分布。对这些面的任何变更必须在 VPS 变更之前或同一提交中更新此仓库。

必需的仓库更新：

- `docs/ONLINE_DISTRIBUTIONS.md`（清单和策略变更）
- `infra/vps/nginx/*.conf`（脱敏后的 nginx 配置快照）
- `infra/vps/systemd/*.service`（脱敏后的 systemd 服务快照）
- `scripts/smoke_online_distributions.py`（烟雾测试预期变更时）
- `STATUS.md`、`docs/LIMA_MEMORY.md`、`progress.md`（运维证据）

禁止提交密钥、证书私钥、提供商令牌、数据库转储、生成的 `.next/`、`node_modules/` 或本地二进制/软件下载。

## 清单

| 服务面 | 公开 URL | VPS 运行时 | 仓库中的源/控制 | 用途 | 当前策略 |
|---|---|---|---|---|---|
| 官方网站 | `https://www.donglicao.com`、`https://donglicao.com` | nginx root `/www/wwwroot/donglicao-site`；demo 代理 `/api/demo`→LiMa 路由器 | `infra/vps/nginx/www.donglicao.com.conf`；本地站点源码目前在嵌套 `net/` 工作树中，在源码变更被视为已追踪之前，必须导入（不含 `.git`、构建输出或大型二进制文件） | 公共产品/品牌入口和 LiMa 演示 | 托管分布；营销/商业方向保持暂停，除非用户另行更改 |
| 聊天界面 | `https://chat.donglicao.com` | nginx root `/var/www/chat`；`/v1`、`/health`、`/agent`、`/mcp`、`/device` 代理至 `127.0.0.1:8080`；`/ws/voice` 代理至 `127.0.0.1:8091`；已退役的 `/telegram/*` 路径必须保持不可用 | `infra/vps/nginx/chat.donglicao.com.conf`；已追踪 Python 模块中的 LiMa 运行时 | 私有聊天 UI 加 OpenAI/Anthropic 兼容 API 和设备边缘 | 主要私有编码助手端点 |
| 开放平台 / API 兼容 | `https://api.donglicao.com` | nginx 代理至 `/opt/ai-router/ai_router_mcp.py`（`127.0.0.1:8769`）；已退役的 `/telegram/*` 路径返回边缘 404 | `infra/vps/nginx/api.donglicao.com.conf`；New API/One API 运行时保留在 VPS 上，但不是此主机的当前 nginx 目标 | 现有兼容网关状态，非主要 LiMa IDE 端点 | 保留但不进行活跃商业推广。`chat.donglicao.com/v1` 仍是主要私有编码 API |
| FRP 端点 | `http://47.112.162.80:8088` | VPS `frps` 映射至 Windows LiMa API `127.0.0.1:8080` | `docs/LOCAL_PROXY_RUNTIME_STATUS.md`、`frp/frpc.toml`（追踪时） | Windows 本地路由器和本地代理提供商的公开验证路径 | 运维烟雾路径，非首选的 HTTPS IDE 端点 |
| 京东云运维节点 | `117.72.118.95` | 辅助提供商探测/监控节点；追踪模板安装 `/opt/lima-probe` 服务和定时器 | `docs/ops/JDCLOUD_RUNTIME_STATUS.md`、`deploy/jdcloud/README.md`、`deploy/jdcloud/*.service`、`deploy/jdcloud/*.sh` 模板 | 跨云探测和监控实验 | 真实运维节点，但不是主要 LiMa 公开 API 面；凭证和一次性密码助手保留在 Git 之外 |
| LiMa 路由器 | 本地服务，通过 nginx/FRP 公开 | `lima-router.service`，工作目录 `/opt/lima-router`，端口 `8080` | `infra/vps/systemd/lima-router.service`；运行时源码在仓库中 | 核心 FastAPI 路由器 | 密钥必须存放在 `/opt/lima-router/.env`，而非 service unit 文件 |
| 语音网关 | 仅通过聊天 nginx websocket 路径公开 | `lima-voice.service`，工作目录 `/opt/lima-voice`，端口 `8091` | `infra/vps/systemd/lima-voice.service`；`voice_gateway_deploy.sh`/使用时涉及的相关文件 | 语音 websocket 网关 | 密钥必须存放在 `/opt/lima-voice/.env`，而非 service unit 文件 |
| LiMa 设备网关 | `https://chat.donglicao.com/device/v1/*` | nginx 将 `/device/v1/health`、`/device/v1/tasks`、`/device/v1/events` 和 WebSocket `/device/v1/ws` 代理至 `127.0.0.1:8080`；VPS 生产环境跨路由器进程使用 Redis 任务队列和 Redis 发布/订阅任务通知 | `routes/device_gateway.py`、`device_gateway/*`、`infra/vps/nginx/chat.donglicao.com.conf`、`docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md`、`docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md` | 直连 U8/ESP32 设备后端 | 经设备令牌认证后公开。Redis HA 模式已部署以支持实时多进程任务投递；Postgres 仍为后续审计/历史存储方案 |

## 边缘策略

- 公开 HTTPS 经 nginx 在 `80` 和 `443` 端口提供服务。
- FRP 公开验证使用 `8088` 端口。
- 内部服务端口（如 `8080`、`3003`、`8769`、`8091`、`6379`）的直接公开访问必须通过防火墙/云安全组保持阻断，即使服务绑定 `0.0.0.0`。
- `api.donglicao.com` 是兼容面，不是恢复公开商业平台工作的许可。
- `chat.donglicao.com/v1` 是主要 IDE/Agent 基础 URL。
- 已退役的 `/telegram/*` 路径必须在 `chat.donglicao.com` 和 `api.donglicao.com` 的 nginx 边缘返回 404。
- 京东云未经单独设计、认证审查、防火墙审查、回滚计划和烟雾证据，不得暴露新的公开 LiMa API 面。
- `/device/v1/*` 仅通过 `chat.donglicao.com` 公开，要求设备令牌认证。VPS 生产环境使用 Redis 共享队列加发布/订阅任务通知，使持有本地 WebSocket 会话的进程可以消费其他进程创建的任务。

## 密钥策略

- nginx 快照可包含证书路径，但绝不包含私钥材料。
- systemd unit 文件不得包含提供商密钥、Bot Token、API Token 或密码。
- 服务密钥应存放于 VPS 上仅 root 可读的环境文件中：
  - `/opt/lima-router/.env`
  - `/opt/lima-voice/.env`
- 如在 unit 文件或文档中发现密钥，将其迁移至 env 文件，重启服务，并在 `progress.md` 中记录迁移。
- 如果密钥曾暴露在非 root 仅读文件之外，需要进行提供商侧密钥轮换。

## 当前 VPS 证据

- `lima-router.service` 和 `lima-voice.service` 在密钥迁移后处于活跃状态。
- `systemctl cat` 快照不再包含提供商密钥行。
- Service-unit 密钥备份已移至 `/root/secure-service-backups`，权限为 `600`。
- 最新公开健康检查：`https://chat.donglicao.com/health` 返回 `status=ok`。
- 最新 Telegram 退役边缘检查：在 nginx 备份 `/etc/nginx/conf.d/donglicao.conf.bak-20260609-040449` 和 `/etc/nginx/conf.d/chat.donglicao.com.conf.bak-20260609-040449` 之后，公开 `POST /telegram/webhook` 在 `https://api.donglicao.com` 和 `https://chat.donglicao.com` 均返回 HTTP `404`。
- 最新设备网关健康检查：`https://chat.donglicao.com/device/v1/health` 返回 `status=ok`，使用 Redis 任务存储和 Redis 会话总线。
- 最新迁移后烟雾测试使用 `scripts/smoke_online_distributions.py --api-key lima-local --chat-exact ha_redis_guarded_ok`，通过 `12/12`，含公开 `6379` 防护。
- Redis HA 代码路径由 `LIMA_DEVICE_TASK_STORE`、`LIMA_DEVICE_SESSION_BUS` 和 `LIMA_DEVICE_REDIS_URL` 控制；VPS 生产环境当前启用，Redis 仅绑定 loopback。

## 变更检查清单

1. 首先更新已追踪的源/配置/文档。
2. 运行 `python -m py_compile scripts/smoke_online_distributions.py`。
3. 部署后运行 `python scripts/smoke_online_distributions.py --chat-exact <short-token>`。
4. 如 nginx 变更，在 VPS 上 reload 前运行 `nginx -t`。
5. 如 systemd 变更，运行 `systemctl daemon-reload`，重启受影响服务，验证 `systemctl is-active`。
6. 更新 `STATUS.md`、`docs/LIMA_MEMORY.md`、`progress.md`。
7. 仅提交和推送精选文件。
