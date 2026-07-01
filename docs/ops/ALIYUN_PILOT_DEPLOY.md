# 阿里云 LiMa Router Pilot 部署 Runbook

> 状态：已上线（2026-07-01）
> 目标：京东云 `117.72.118.95` 为主力节点；阿里云 `47.112.162.80` 作为只处理免费/低价后端流量的辅助节点。
> 关联：`docs/ops/JDCLOUD_RUNTIME_STATUS.md`、`STATUS.md`

---

## 架构

```
chat.donglicao.com  →  Cloudflare Tunnel → 京东云 lima-router（主节点，全功能）
aliyun.donglicao.com →  阿里云 nginx → 阿里云 lima-router-pilot（辅助节点，仅免费后端）
```

阿里云 pilot 特性：

- `LIMA_NODE_ROLE=free_backend_only`
- 禁用 `session_memory`、`device_gateway`、`mqtt_client`、`context_pipeline` 检索注入、`alert_evaluator`
- 保留 Prometheus 导出器，确保京东云监控可继续抓取阿里云指标
- 后端选择限制为云上免费/低价后端（Pollinations、DDG、OVH、Google Flash 等）
- 不依赖本地 Windows 后端

## 部署资产

| 文件 | 用途 |
|---|---|
| `config/node_role.py` | 节点角色与能力开关 |
| `router_v3/select.py` | 辅助节点后端池过滤 |
| `deploy/aliyun/lima-router-pilot.service` | systemd 单元 |
| `deploy/aliyun/install_aliyun_pilot.sh` | 阿里云 VPS 安装脚本 |
| `deploy/aliyun/aliyun-pilot.nginx.conf` | nginx 模板 |
| `scripts/deploy_aliyun_pilot.py` | 本地一键部署脚本 |

## 快速部署 / 更新

```bash
# 本地执行（依赖 SSH key ~/.ssh/lima_deploy_ed25519 或 LIMA_ALIYUN_PASSWORD）
python scripts/deploy_aliyun_pilot.py
```

脚本会：

1. 把当前仓库打包为 tar.gz，scp 到阿里云 `/opt/lima-router-pilot/repo.tar.gz`。
2. 远程解压到 `/opt/lima-router-pilot/repo/`。
3. 停止旧 `lima-router.service`（释放 `:8080`）。
4. 创建/复用 `lima-pilot` 用户、venv、`.env`（合并旧 `/opt/lima-router/.env` + 追加辅助节点覆盖）。
5. 安装并启动 `lima-router-pilot.service`。
6. 检查 `/health` 返回 200。

## 手动部署（首次或排查）

```bash
# 在阿里云以 root 执行
bash /opt/lima-router-pilot/repo/deploy/aliyun/install_aliyun_pilot.sh
```

## nginx + HTTPS 配置

```bash
# 1. 确保 DNS 已添加 aliyun.donglicao.com → 47.112.162.80（DNS-only/灰云）
# 2. 复制 nginx 模板
cp /opt/lima-router-pilot/repo/deploy/aliyun/aliyun-pilot.nginx.conf \
   /etc/nginx/conf.d/aliyun-pilot.donglicao.com.conf

# 3. 申请 Let's Encrypt 证书（使用 webroot，不中断其他站点）
mkdir -p /var/www/certbot
certbot certonly --webroot -w /var/www/certbot -d aliyun.donglicao.com \
  --non-interactive --agree-tos --email admin@donglicao.com

# 4. 在 nginx 配置中取消 ssl_certificate 注释并指向真实证书路径
sed -i 's|# ssl_certificate /etc/letsencrypt/live/donglicao.com/fullchain.pem;|ssl_certificate /etc/letsencrypt/live/aliyun.donglicao.com/fullchain.pem;|' \
  /etc/nginx/conf.d/aliyun-pilot.donglicao.com.conf
sed -i 's|# ssl_certificate_key /etc/letsencrypt/live/donglicao.com/privkey.pem;|ssl_certificate_key /etc/letsencrypt/live/aliyun.donglicao.com/privkey.pem;|' \
  /etc/nginx/conf.d/aliyun-pilot.donglicao.com.conf

# 5. 验证并重载
nginx -t && systemctl reload nginx
```

## 验证

```bash
# 本地 loopback
ssh root@47.112.162.80 'curl -sf http://127.0.0.1:8080/health'

# 公网 HTTPS
curl -sf https://aliyun.donglicao.com/health

# 匿名免费后端聊天
curl -s -X POST https://aliyun.donglicao.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}]}'

# 预期：x_lima_meta.backend 为 google_flash / google_flash_lite / ddg_* / ovh_* 等云上免费后端
```

## 环境变量覆盖

`/opt/lima-router-pilot/.env` 末尾追加：

```env
LIMA_NODE_ROLE=free_backend_only
LIMA_SESSION_MEMORY_ENABLED=0
LIMA_DEVICE_GATEWAY_ENABLED=0
LIMA_MQTT_CLIENT_ENABLED=0
LIMA_CONTEXT_RETRIEVAL_ENABLED=0
LIMA_PROMETHEUS_ENABLED=1
LIMA_ALERT_EVALUATOR_ENABLED=0
LIMA_STRUCTURED_LOGGING_ENABLED=1
LIMA_DEVICE_MEMORY_STORE=memory
LIMA_DEVICE_LEDGER_STORE=memory
LIMA_DEVICE_TASK_STORE=memory
LIMA_RUNTIME_ENV=production
LIMA_ALLOW_ANONYMOUS=1
```

## 监控

- systemd 状态：`systemctl status lima-router-pilot`
- 日志：`journalctl -u lima-router-pilot -f`
- Prometheus 指标：`curl http://127.0.0.1:8080/v1/ops/metrics/prometheus`

## 回滚

```bash
# 停止 pilot，恢复旧 lima-router
systemctl stop lima-router-pilot
systemctl disable lima-router-pilot
systemctl enable lima-router
systemctl start lima-router
systemctl reload nginx
```

## 后续：接入 chat.donglicao.com 流量分流

当前 `aliyun.donglicao.com` 已作为独立辅助入口可用。若要让 `chat.donglicao.com` 自动把部分流量导向阿里云，可选：

1. **Cloudflare Load Balancer**：创建 pool（origin = 阿里云 IP + 京东云 Tunnel），按权重/地理分配。
2. **按子路径分流**：nginx 或 Cloudflare Worker 把 `/v1/chat/completions` 中匿名/无 session 请求转发到阿里云。
3. **客户端选择**：前端/小程序根据请求类型选择 `chat.donglicao.com` 或 `aliyun.donglicao.com`。
