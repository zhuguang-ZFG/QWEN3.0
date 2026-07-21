# 阿里云 DLC 公网入口 Runbook

> 状态：设计阶段（待实施）
> 目标：小智云 + DLC 瘦身后，阿里云 `47.112.162.80` 作为 `dlc_api` / `dlc_mcp` 的公网入口。
> 关联：`docs/xiaozhi-cloud/lima-slimdown-design.md` §1.5、`docs/ops/JDCLOUD_RUNTIME_STATUS.md`

---

## 架构定位

| 维度 | 瘦身前 | 瘦身后 |
|------|--------|--------|
| 阿里云角色 | `lima-router-pilot` 辅助节点（匿名 chat 免费后端） | **DLC 公网入口 / edge** |
| 入口域名 | `chat.donglicao.com` / `aliyun.donglicao.com` | `chat.donglicao.com`（保留） |
| 核心服务 | `lima-router-pilot` | `dlc_api` + `dlc_mcp` |
| 数据/观测 | 无 | 复用 JDCloud `117.72.118.95` 的 MySQL/Redis/Prometheus |

## 网络拓扑

```text
Internet
   │
   ▼
chat.donglicao.com → 阿里云 47.112.162.80 (nginx :443)
   │
   ├─ /dlc/*            → dlc_api (本地 :8080)
   ├─ /device/v1/*      → dlc_api / 设备网关（按最终瘦身范围保留）
   └─ /health / metrics → dlc_api
   │
   Tailscale / 内网
   │
   ▼
JDCloud 117.72.118.95
   ├─ MySQL / Redis
   ├─ Prometheus + Grafana
   └─ probe / worker / optional dlc_api hot-standby
```

## 运行服务

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 443 / 80 | TLS termination，反向代理到 `dlc_api` |
| dlc_api | 127.0.0.1:8080 | FastAPI：/dlc/tasks/*、/device/v1/*、/health、/metrics |
| dlc_mcp | 127.0.0.1:8081（或复用 8080） | MCP Server，通过 WebSocket 接入小智官方云 MCP endpoint |

## 部署资产（待创建）

| 文件 | 用途 |
|------|------|
| `deploy/aliyun/dlc-api.service` | systemd 单元 |
| `deploy/aliyun/install_dlc_entry.sh` | 阿里云 VPS 安装脚本 |
| `deploy/aliyun/dlc-entry.nginx.conf` | nginx 模板 |
| `scripts/deploy_aliyun_dlc.py` | 本地一键部署脚本 |

## 快速部署（待实现）

```bash
# 本地执行（依赖 SSH key ~/.ssh/lima_deploy_ed25519 或 LIMA_ALIYUN_PASSWORD）
python scripts/deploy_aliyun_dlc.py
```

脚本将：

1. 把当前仓库打包为 tar.gz，scp 到阿里云 `/opt/dlc-api/repo.tar.gz`。
2. 远程解压到 `/opt/dlc-api/repo/`。
3. 创建/复用 `dlc-api` 用户、venv、`.env`（合并旧 `/opt/lima-router/.env` + 追加 DLC 专用变量）。
4. 停止 `lima-router-pilot.service` 和 `lima-router.service`（若存在）。
5. 安装并启动 `dlc-api.service`。
6. 更新 nginx 配置，将 `/dlc/*` 和 `/device/v1/*` 路由到 `dlc_api`。
7. 检查 `/health` 返回 200。

## nginx 配置要点

```nginx
server {
    listen 443 ssl http2;
    server_name chat.donglicao.com;

    ssl_certificate /etc/letsencrypt/live/chat.donglicao.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.donglicao.com/privkey.pem;

    location /dlc/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /device/v1/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8080;
    }

    location /metrics {
        proxy_pass http://127.0.0.1:8080;
        # 建议限制内网/Tailscale 访问
        allow 100.64.0.0/10;
        deny all;
    }
}
```

## 环境变量

`/opt/dlc-api/.env` 示例：

```env
LIMA_RUNTIME_ENV=production
DLC_API_TOKEN=change-me-in-production
DLC_API_BASE_URL=https://chat.donglicao.com

# 数据库/缓存复用 JDCloud
MYSQL_HOST=100.85.114.65
MYSQL_PORT=3306
REDIS_HOST=100.85.114.65
REDIS_PORT=6379

# MCP 接入小智官方云
XIAOZHI_MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...

# 禁用旧 LiMa 能力
LIMA_CHAT_ENABLED=0
LIMA_ADMIN_ENABLED=0
LIMA_VOICE_ENABLED=0
LIMA_PROVIDER_PROBE_ENABLED=0
```

## 验证

```bash
# 本地 loopback
ssh root@47.112.162.80 'curl -sf http://127.0.0.1:8080/health'

# 公网 HTTPS
curl -sf https://chat.donglicao.com/health

# dlc_api 预览接口
ssh root@47.112.162.80 \
  'curl -sf -X POST http://127.0.0.1:8080/dlc/tasks/preview \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $DLC_API_TOKEN" \
     -d '\''{"type":"write_text","text":"你好"}'\'''
```

## 与旧 Pilot 的关系

- 旧 `lima-router-pilot.service` 停止并禁用。
- 旧 `aliyun.donglicao.com` 域名可保留重定向到 `chat.donglicao.com`，或逐步退役。
- 历史 pilot runbook 已删除（见 git history）。
