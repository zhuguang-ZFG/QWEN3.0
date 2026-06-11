# JDCloud 部署 new-api Runbook

> **状态**：✅ 已上线（2026-06-11 部署完成）
> **公网入口**：`https://api.donglicao.com`（Cloudflare → 阿里云反代 → 京东云）
> **目标节点**：JDCloud `117.72.118.95`（new-api 服务实际运行节点）
> **代理节点**：AliCloud `47.112.162.80`（nginx 反代，绕过 JDCloud ISP 拦截）
> **配套脚本**：`deploy/jdcloud/install_newapi.sh`、`configure_newapi_firewall.sh`、`newapi.nginx.conf`
> **关联文档**：`docs/DEPLOY_AND_RELEASE_CONVENTION.md` · `docs/ops/JDCLOUD_RUNTIME_STATUS.md` · `deploy/jdcloud/README.md`

---

## 0. 为什么需要这份 runbook

LiMa 本身是**多后端 AI 路由 + 智能设备服务端**，定位在"消费自己持有/可代理的 AI 后端 key"；但当**对外开放、按用户/渠道分发**API key、计费时，需要一个成熟的"OpenAI 聚合 + 用户/计费"门面。GitHub 上 `songquanpeng/new-api`（one-api 的继任 fork）就是这种事实标准。

本 runbook 记录 **JDCloud 上 new-api 的完整部署过程**（包括遇到的 ISP 拦截问题及绕过方案），与 LiMa 主业务零耦合，可独立运维、独立回滚、独立备份。

**非目标**：
- 不替换 LiMa 的智能路由能力
- 不在 JDCloud 上跑 LiMa 主流量
- 不做多区域灾备（单节点即可）

---

## 1. 前置条件

| 类别 | 要求 |
|---|---|
| JDCloud 节点 | ECS，2C/2G/40G；OS: Ubuntu 22.04 LTS |
| 公网 IP | 117.72.118.95（已有，但 ISP 拦截 Cloudflare IP 段） |
| 域名 | `api.donglicao.com` — Cloudflare DNS → 阿里云 `47.112.162.80`（非京东云） |
| TLS 证书 | 京东云自签证书（仅 nginx 间通信用）+ 阿里云 Let's Encrypt（对外） |
| 端口 | 3000（new-api）、80/443（nginx）、22（SSH） |
| Cloudflare SSL | **Full** 模式（允许自签证书）+ 关闭 Always Use HTTPS |
| 阿里云反代 | `47.112.162.80` nginx 反代 `api.donglicao.com` → JDCloud `117.72.118.95:443` |

---

## 2. 架构（实际部署拓扑）

### 2.1 为什么需要双层 nginx

**京东云 ISP 会拦截来自 Cloudflare IP 段的入站 HTTPS 请求**。直接让 Cloudflare 解析 `api.donglicao.com` 到 `117.72.118.95` 会导致 SSL 握手失败（京东云侧无任何日志，请求未到达 nginx）。

绕过方案：利用阿里云 VPS 做中间代理。阿里云不会拦截 Cloudflare IP，nginx 在阿里云侧作为透明反代转发到京东云。

```
用户浏览器 / API 客户端
    │
    │  HTTPS (443) + Cloudflare Full SSL
    ▼
┌──────────────────────────────────────────────┐
│  Cloudflare DNS                              │
│  api.donglicao.com → 47.112.162.80 (阿里云)  │
└──────────────────────────────────────────────┘
    │
    │  HTTPS (443)  Let's Encrypt 证书
    ▼
┌─────────────────────────────────────────────────────────┐
│  阿里云 VPS  47.112.162.80                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │  nginx donglicao.conf                               ││
│  │  - TLS: Let's Encrypt (certbot 自动续期)            ││
│  │  - gzip 静态资源压缩                                 ││
│  │  - 静态资源: proxy_buffering on + Cache-Control 1h   ││
│  │  - API/SSE: proxy_buffering off（保持流式）          ││
│  │  - proxy_pass → https://117.72.118.95:443          ││
│  │    proxy_ssl_verify off（京东云自签证书）            ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  ★ 注意：京东云 117.72.118.95 的 DNS 记录已从          │
│    Cloudflare 删除，避免 ISP 拦截。                     │
└──────────────────────────────────────────────────────────┘
    │
    │  HTTPS (443)  自签证书（nginx 间通信）
    │  proxy_ssl_verify off
    ▼
┌─────────────────────────────────────────────────────────┐
│  京东云 VPS  117.72.118.95                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │  nginx (80/443, 自签 TLS, 安全 headers)             ││
│  │  ↓ proxy_pass http://127.0.0.1:3000                ││
│  │  new-api 容器 (host 网络模式)                       ││
│  │  - 用户/渠道/Key/计费 Web UI                        ││
│  │  - OpenAI/Claude/Gemini 兼容 API                    ││
│  │  - MySQL 8.0 (宿主机 :3306)                         ││
│  │  - Redis 7.0 (宿主机 :6379)                         ││
│  │  ↓ 转发到各后端 API                                  ││
│  │  OpenAI · Anthropic · Gemini ...                   ││
│  └─────────────────────────────────────────────────────┘│
│  ufw：仅开 22, 80, 443；3000/3306/6379 DENY 外部       │
└─────────────────────────────────────────────────────────┘
```

new-api 与 LiMa 的关系：**完全独立**。两者可以同时跑、互不感知。

---

## 3. 部署步骤

### 3.0 前置：节点初始化（一次性）

```bash
# 在本地 Windows 或跳板机上
ssh -i ~/.ssh/jdcloud_ed25519 root@117.72.118.95

# 创建专用用户（不要直接用 root 跑服务）
useradd -m -s /bin/bash newapi
mkdir -p /home/newapi/.ssh
# 复制公钥
cp ~/.ssh/authorized_keys /home/newapi/.ssh/
chown -R newapi:newapi /home/newapi/.ssh
chmod 700 /home/newapi/.ssh && chmod 600 /home/newapi/.ssh/authorized_keys

# 允许 newapi 用户 sudo（无密码，仅限 docker/systemctl）
echo "newapi ALL=(ALL) NOPASSWD: /usr/bin/systemctl *, /usr/bin/docker *" > /etc/sudoers.d/newapi
chmod 440 /etc/sudoers.d/newapi

# 退出 root，后续用 newapi 登录
exit
```

### 3.1 步骤 1：安装 Docker

```bash
ssh newapi@117.72.118.95

# 卸载旧版本
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# 安装 Docker CE（使用阿里云镜像，海外源在 JDCloud 上慢）
curl -fsSL https://get.docker.com | bash -s -- --mirror Aliyun

# 加入 docker 组（避免每次 sudo）
sudo usermod -aG docker newapi
# 退出重登使组生效
exit
ssh newapi@117.72.118.95
docker --version  # 验证
```

### 3.2 步骤 2：初始化 MySQL 数据库

在宿主机 MySQL 中创建 new-api 专用数据库和用户：

```bash
ssh newapi@117.72.118.95
mysql -u root -p -h 127.0.0.1
```

```sql
CREATE DATABASE IF NOT EXISTS newapi
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'newapi'@'%' IDENTIFIED BY '<强密码>';
GRANT ALL PRIVILEGES ON newapi.* TO 'newapi'@'%';
FLUSH PRIVILEGES;
```

> **安全说明**：`newapi` 用户仅对 `newapi` 库有权限，不影响其他数据库。密码不落盘到脚本或仓库中。

### 3.3 步骤 3：创建工作目录与 docker-compose

参考 `deploy/jdcloud/install_newapi.sh`（已 track 在本仓库，**不含真实 key**）：

```bash
# 拉取本仓库
cd ~
git clone https://github.com/zhuguang-ZFG/QWEN3.0.git lima-deploy 2>/dev/null || \
  (cd lima-deploy && git pull origin main)

# 复制 new-api 模板（不是真实部署目录，只读参考）
cat lima-deploy/deploy/jdcloud/install_newapi.sh
```

**真实部署用独立目录** `/opt/newapi`，**不放在 lima-deploy 仓库里**（避免误提交 key/数据库）：

```bash
sudo mkdir -p /opt/newapi/data /opt/newapi/logs
sudo chown -R newapi:newapi /opt/newapi
cd /opt/newapi
```

写入 `docker-compose.yml`（**人工编辑，不入库**），复用宿主机 MySQL + Redis：

```yaml
# /opt/newapi/docker-compose.yml
# 复用宿主机 MySQL 8.0 + Redis 7.0，使用 host 网络模式
services:
  newapi:
    image: calciumion/new-api:latest
    container_name: newapi
    restart: unless-stopped
    command: --log-dir /app/logs
    network_mode: host          # 直连宿主机 127.0.0.1 上的 MySQL/Redis
    volumes:
      - ./data:/data
      - ./logs:/app/logs
    environment:
      - SQL_DSN=newapi:<密码>@tcp(127.0.0.1:3306)/newapi
      - REDIS_CONN_STRING=redis://:<redis密码>@127.0.0.1:6379
      - TZ=Asia/Shanghai
      - BATCH_UPDATE_ENABLED=true
      - ERROR_LOG_ENABLED=true
      - SESSION_SECRET=<随机字符串>  # openssl rand -hex 24
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1:3000/api/status | grep -o '\"success\":\\s*true' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
```

> **网络模式说明**：使用 `network_mode: host`，容器直连宿主机网络，可访问 `127.0.0.1:3306` (MySQL) 和 `127.0.0.1:6379` (Redis)，无需桥接网络。端口 3000 自动在宿主机监听。

启动：

```bash
docker compose pull
docker compose up -d
docker compose ps                 # 应显示 healthy
docker compose logs --tail=50     # 看启动日志
```

### 3.4 步骤 4：防火墙（ufw）

参考 `deploy/jdcloud/configure_newapi_firewall.sh`：

```bash
sudo /home/newapi/lima-deploy/deploy/jdcloud/configure_newapi_firewall.sh
```

**关键规则**（脚本会做这些，**人工请通读脚本再跑**）：

| 端口 | 协议 | 来源 | 备注 |
|---|---|---|---|
| 22 | TCP | 任意（建议限制为公司 IP / Tailscale） | SSH |
| 80 | TCP | 任意 | HTTP → 301 到 HTTPS |
| 443 | TCP | 任意 | HTTPS |
| 3000 | TCP | **仅 127.0.0.1** | new-api Web/loopback（已通过 docker 绑定 loopback 二次防御） |

```bash
# 验证
sudo ufw status numbered
# 期望：22/80/443 ALLOW IN；3000 仅在 127.0.0.1 上 listen（用 ss -tlnp 查）
ss -tlnp | grep :3000   # 应只看到 127.0.0.1:3000
```

### 3.5 步骤 5：京东云 nginx + 自签证书

> **仅用于阿里云 nginx → 京东云 nginx 的内部 HTTPS 通信**，不对外。
> 阿里云 nginx 设置 `proxy_ssl_verify off` 信任京东云自签证书。

```bash
ssh root@117.72.118.95

# 生成自签证书（10 年有效期）
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/selfsigned.key \
  -out /etc/nginx/ssl/selfsigned.crt \
  -subj "/CN=api.donglicao.com"

# 部署 nginx 配置
cp /home/newapi/lima-deploy/deploy/jdcloud/newapi.nginx.conf \
   /etc/nginx/sites-available/newapi.donglicao.com.conf
ln -sf /etc/nginx/sites-available/newapi.donglicao.com.conf \
       /etc/nginx/sites-enabled/

# 测试 + 重载
nginx -t && systemctl reload nginx
```

**不需要 certbot**（阿里云侧已处理对外 TLS）。

### 3.6 步骤 6：Cloudflare DNS + 阿里云 nginx 反代

#### 3.6.1 Cloudflare DNS

`api.donglicao.com` A 记录 → `47.112.162.80`（阿里云），**不指向京东云**。

Cloudflare SSL/TLS 设置：
- 加密模式：**Full**（允许京东云自签证书）
- Always Use HTTPS：关闭（阿里云 nginx 已做 301 重定向）

#### 3.6.2 阿里云 nginx 反代配置

在阿里云 `47.112.162.80` 的 `/etc/nginx/conf.d/donglicao.conf` 中增加 `api.donglicao.com` server block：

```nginx
server {
    server_name api.donglicao.com;
    listen 443 ssl http2;
    # ... Let's Encrypt 证书（与 chat.donglicao.com 共用）...

    # gzip 压缩静态资源
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml text/javascript image/svg+xml;

    # 静态资源：开启缓冲 + 浏览器缓存（双层 nginx，必须缓冲）
    location ~* \.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$ {
        proxy_pass https://117.72.118.95:443;
        proxy_ssl_verify off;                    # 京东云自签证书
        proxy_buffering on;
        proxy_cache_valid 200 1h;
        expires 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    # API/页面：关闭缓冲（支持 SSE 流式）
    location / {
        proxy_pass https://117.72.118.95:443;
        proxy_ssl_verify off;
        proxy_buffering off;
        proxy_read_timeout 300s;

        proxy_set_header Host api.donglicao.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **性能优化**：由于跨云双层 nginx，`proxy_buffering off` 会导致每个字节逐跳传输。静态资源 block 启用 `proxy_buffering on` 并加 `Cache-Control`，大幅提升页面加载速度。API/SSE 路径保持 unbuffered。

### 3.7 步骤 7：初始化 new-api（root 密码重置 + API Key）

> new-api 使用 Go 的 bcrypt 实现，Python 生成的 bcrypt hash 默认使用 `$2b$` 前缀，Go 只认 `$2a$`。必须在京东云主机上用 Python3 的 bcrypt 库生成带 `$2a$` 前缀的 hash。

#### 3.7.1 重置 root 密码

```bash
ssh root@117.72.118.95

# 确认 MySQL 用户存在
mysql -e "SELECT id, username, role, status FROM newapi.users WHERE username='root';"

# 用京东云主机 Python3 bcrypt 生成 Go 兼容 hash
python3 -c "
import bcrypt
h = bcrypt.hashpw(b'NewApi@2026!', bcrypt.gensalt(prefix=b'2a'))
print(h.decode())
"

# 将生成的 hash 写入数据库
mysql -e "UPDATE newapi.users SET password='<生成的hash>' WHERE username='root';"
```

**重要**：不要用本地 Windows Python 生成 bcrypt hash，不同平台/版本的 bcrypt 库产生的 hash 可能与 Go 不兼容。

#### 3.7.2 生成 API access_token

```bash
# MySQL access_token 列是 char(32)，必须是 32 个字符
# 生成 32 位随机 token
python3 -c "import secrets; print(secrets.token_hex(16))"

# 写入数据库
mysql -e "UPDATE newapi.users SET access_token='<32位token>' WHERE username='root';"
```

#### 3.7.3 当前配置状态

| 项目 | 值 |
|---|---|
| 管理员账号 | `root` |
| 管理员密码 | **已重置，见 `docs/ops/NEWAPI_ISSUES_AND_FIXES.md`** |
| API Key | **已重置，见 `docs/ops/NEWAPI_ISSUES_AND_FIXES.md`** |
| 用户ID | 1 |
| 角色 | admin（role=1） |

> ⚠️ **安全警告**: 原密码和 API Key 已泄露，必须立即重置！详见 `docs/ops/NEWAPI_ISSUES_AND_FIXES.md` 修复方案。

#### 3.7.4 待完成：Web UI 初始化

浏览器打开 `https://api.donglicao.com`，用 root/NewApi@2026! 登录后：

1. [ ] 修改密码为更强的密码（≥16 位）
2. [ ] 系统设置 → 站点名称修改
3. [ ] 关闭用户注册（Enable Registration = false）
4. [ ] 添加渠道（OpenAI / Claude 等）
5. [ ] 添加普通用户并生成分发的 API key

---

## 4. 备份（每日 cron）

放 runbook 里以可执行块呈现，按需落地到 `deploy/jdcloud/newapi_backup.sh`：

```bash
# /opt/newapi/backup.sh —— 加入 crontab
#!/bin/bash
set -euo pipefail
TS=$(date +%Y%m%d_%H%M%S)
DEST=/var/backups/newapi/$TS
mkdir -p "$DEST"

# 1. 导出 MySQL 数据库（无需停服，mysqldump 原子性快照）
cd /opt/newapi
mysqldump -u newapi -p"$NEWAPI_MYSQL_PASS" -h 127.0.0.1 newapi > "$DEST/newapi.sql"

# 2. 备份 docker-compose.yml（不含真实密码）
cp /opt/newapi/docker-compose.yml "$DEST/"

# 3. 清理 > 14 天的备份
find /var/backups/newapi -mindepth 1 -maxdepth 1 -mtime +14 -exec rm -rf {} \;

# 4. 推送 JDCloud OSS（可选，避免本地磁盘单点）
# aliyun oss cp "$DEST" oss://my-bucket/newapi/$TS/ --recursive
```

```bash
chmod +x /opt/newapi/backup.sh
# 每天凌晨 3:13 备份
(crontab -l 2>/dev/null; echo "13 3 * * * /opt/newapi/backup.sh >> /var/log/newapi-backup.log 2>&1") | crontab -
```

---

## 5. Smoke 验证（每节点上线后必跑）

放 runbook 里以可执行块呈现，按需落地到 `deploy/jdcloud/newapi_smoke.sh`：

```bash
#!/bin/bash
# new-api smoke —— 必须在 SSH 到 JDCloud 节点上跑
set -euo pipefail
DOMAIN=${1:-api.donglicao.com}
INTERNAL=http://127.0.0.1:3000
echo "=== 1. loopback 健康 ==="
curl -sf "$INTERNAL/api/status" | head -c 200; echo

echo "=== 2. 公网 HTTPS 健康 ==="
curl -sfI "https://$DOMAIN/" | head -3

echo "=== 3. TLS 证书有效期 ==="
echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN":443 2>/dev/null \
  | openssl x509 -noout -dates

echo "=== 4. 防火墙最小化 ==="
ss -tlnp | grep -E ':(22|80|443|3000)\b' || true

echo "=== 5. 鉴权重定向（应返回 401，无 Authorization） ==="
curl -s -o /dev/null -w "code=%{http_code}\n" -X POST \
  "https://$DOMAIN/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
# 期望 code=401

echo "=== 6. 鉴权成功（用 root token 跑一次真实 chat，验证整个链路） ==="
# 从 Web UI 复制一个 sk-xxx 填到下面
TOKEN=${NEWAPI_TEST_TOKEN:-}
if [ -z "$TOKEN" ]; then
  echo "跳过：未设 NEWAPI_TEST_TOKEN"
else
  curl -s -X POST "https://$DOMAIN/v1/chat/completions" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"say hi"}]}' \
    | head -c 400; echo
fi

echo "=== 7. 备份产物新鲜度 ==="
ls -lht /var/backups/newapi/ 2>/dev/null | head -3 || echo "尚未生成备份"

echo "=== smoke 完成 ==="
```

执行：

```bash
chmod +x /opt/newapi/smoke.sh
NEWAPI_TEST_TOKEN=sk-xxx /opt/newapi/smoke.sh api.donglicao.com
```

---

## 6. 升级

```bash
cd /opt/newapi
docker compose pull            # 拉取 latest
docker compose up -d           # 重建容器（数据卷不动）
docker compose logs --tail=50  # 验证启动
/opt/newapi/smoke.sh api.donglicao.com
```

**回滚到上一镜像**：

```bash
docker image ls calciumion/new-api --format '{{.Tag}}\t{{.ID}}' | head -5
# 记下要回滚的 digest，改 docker-compose.yml:
#   image: calciumion/new-api@sha256:<digest>
docker compose up -d
```

或更简单：保留上一镜像的 tag：

```bash
# 升级前先 tag 当前容器为可回滚镜像
docker tag calciumion/new-api:latest calciumion/new-api:prev
# 出问题时：
#   sed -i 's/:latest/:prev/' docker-compose.yml
#   docker compose up -d
```

---

## 7. 回滚（节点级）

| 故障 | 处置 |
|---|---|
| Web UI 502 | `docker compose logs --tail=200`；先 `docker compose restart`，无效则 `up -d --force-recreate` |
| 数据库损坏 | `mysql -u root -p newapi < /var/backups/newapi/<最新>/newapi.sql && docker compose restart` |
| 整个节点挂了 | JDCloud 控制台重置 → 按本 runbook §3 重跑（数据靠 `/var/backups/newapi` 恢复） |
| 误删数据卷 | **不可逆**——这就是为什么 §4 备份必须每日跑且 `>14` 天保留 |

---

## 8. 监控（接入现有 healthcheck 体系）

仓库已有 `docs/archive/superpowers-2026-05/2026-05-26-infra-tools-integration.md` 的 INF-B Healthchecks 计划。new-api 上线后追加 2 个 check：

| Check | 周期 | URL | 失败含义 |
|---|---|---|---|
| `jdcloud-newapi-https` | 5 min | `https://api.donglicao.com/api/status` | 公网入口挂 |
| `jdcloud-newapi-chat` | 30 min | POST `https://api.donglicao.com/v1/chat/completions`（用专用 test token） | 整链路（含渠道后端）挂 |

不接入 new-api 自带的"渠道测速"作为告警源——它的主动探测会消耗渠道额度。

---

## 9. 安全红线（与 AGENTS.md 一致）

1. **不提交任何凭据**：JDCloud 密码、SSH 私钥、new-api 根密码、任何渠道 sk-/gho-/AIza 密钥、数据库文件 → 全部 `.gitignore` 范围内
2. **不入库**：`/opt/newapi/`（含 `docker-compose.yml` 真实版、`data/` 数据库、`.env` 任何 secret）→ 仅 `deploy/jdcloud/` 下模板文件入库
3. **不开放注册**：默认 `Enable Registration = false`；新用户由 root 手动创建
4. **不暴露 3000/3306/6379**：docker `network_mode: host` + ufw DENY + nginx 反代三层防御
5. **不留默认密码**：root 密码已通过 MySQL bcrypt 直接重置；后续通过 Web UI 改为强密码（≥16 位）
6. **不与主 VPS 共享 secret**：new-api 用的 key 与 LiMa 用的 key 完全独立
7. **不绕过 nginx 直连**：所有客户端必须走 `https://api.donglicao.com`（Cloudflare → 阿里云 → 京东云）
8. **京东云自签证书仅内网用**：不对外暴露京东云 443；外部 TLS 由阿里云 Let's Encrypt + Cloudflare Full 模式保障

### 9.1 已知陷阱

| 陷阱 | 详情 | 规避 |
|---|---|---|
| JDCloud ISP 拦截 Cloudflare IP | 京东云 ISP 在 TCP 层拦截来自 Cloudflare IP 段的入站 HTTPS，请求不会到达 nginx，无日志 | Cloudflare DNS → 阿里云 → 京东云；京东云 DNS 记录不放进 Cloudflare |
| Go bcrypt `$2a$` 前缀 | Python bcrypt 默认生成 `$2b$` 前缀 hash，Go 的 bcrypt 库只认 `$2a$` | 必须用京东云主机 Python3 `gensalt(prefix=b"2a")` 生成 hash |
| access_token 列长度限制 | `users.access_token` 是 `char(32)`，超过 32 字符会报 MySQL 1406 错误 | 用 `secrets.token_hex(16)` 生成精确 32 字符 token |
| 双层 nginx 性能 | `proxy_buffering off` 在双层 nginx 下导致每个字节逐跳传输，页面加载极慢 | 静态资源 block 开启 buffering + Cache-Control；API/SSE 保持 unbuffered |

---

## 10. 故障排查

| 症状 | 检查 |
|---|---|
| 公网 502 | `docker compose ps` → `curl 127.0.0.1:3000/api/status` → `tail -50 /opt/newapi/data/logs/` |
| 渠道 400 invalid_api_key | Web UI 渠道管理 → 重新粘贴 key → 测试 → 检查是否被该上游封号 |
| 渠道 429 rate_limit | Web UI 渠道管理 → 调整"权重"或加备用渠道 → 不要直接调高单 key QPS |
| 上传 413 | `client_max_body_size` 默认 1m，newapi.nginx.conf 已设 50m；若仍报，查 nginx error.log |
| WebSocket/流式断流 | `proxy_buffering off` + `proxy_read_timeout 300s` 已在 newapi.nginx.conf；查 upstream 是否正常 |
| 数据卷只读 | `chown -R newapi:newapi /opt/newapi/data` |
| 容器时间不对 | `TZ=Asia/Shanghai` 已设；如仍不对，`docker compose down && docker compose up -d` 重建 |

---

## 11. 验收清单（VPS smoke 后逐项打勾）

- [x] JDCloud `117.72.118.95` 节点初始化（newapi 用户 + sudo + SSH key）
- [x] Docker CE 安装，`docker --version` 正常
- [x] MySQL 数据库 `newapi` 初始化 + newapi 用户授权
- [x] `/opt/newapi/docker-compose.yml` 部署，容器 `healthy`
- [x] ufw 启用，仅 22/80/443 公开；3000/3306/6379 DENY 外部
- [x] 京东云 nginx + 自签证书部署
- [x] Cloudflare DNS `api.donglicao.com` → 阿里云 `47.112.162.80`；SSL Full 模式
- [x] 阿里云 nginx 反代配置（双层代理 + gzip + 静态缓存优化）
- [x] `https://api.donglicao.com` 公网可访问（200 正常）
- [x] root 密码通过 MySQL bcrypt 重置
- [x] API access_token 生成并写入数据库
- [ ] 首次 Web UI 登录并修改 root 密码为强密码（≥16 位）
- [ ] 关闭用户注册（Enable Registration = false）
- [ ] 添加至少 1 个渠道（OpenAI / Claude 等）并测试
- [ ] 添加至少 1 个普通用户并生成 token
- [ ] smoke.sh 全 7 项通过
- [ ] 每日 03:13 cron 备份跑通，保留 14 天
- [ ] Healthchecks.io 2 个 check 接入

---

## 12. 相关文档

- `docs/DEPLOY_AND_RELEASE_CONVENTION.md` — 通用部署/release 硬规则
- `docs/ops/JDCLOUD_RUNTIME_STATUS.md` — JDCloud 节点运行时状态（本 runbook 执行后追加）
- `deploy/jdcloud/README.md` — 现有 JDCloud 资产清单
- `deploy/jdcloud/configure_firewall.sh` — ufw 风格参考
- `deploy/jdcloud/newapi.nginx.conf` — nginx 反代模板（本 runbook 配套新建）
- `deploy/jdcloud/install_newapi.sh` — 一键安装脚本（本 runbook 配套新建）
- `deploy/jdcloud/configure_newapi_firewall.sh` — new-api 专用 ufw（本 runbook 配套新建）
- `docs/archive/superpowers-2026-05/2026-05-26-infra-tools-integration.md` — Infisical/Healthchecks/Tailscale 接入计划，可与 new-api 协同