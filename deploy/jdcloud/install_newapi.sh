#!/bin/bash
# 京东云 new-api 一键安装脚本
# 服务器: 117.72.118.95
# 用途: 在 JDCloud 备节点部署 new-api（OpenAI 聚合/用户/计费），复用宿主机 MySQL 8.0 + Redis 7.0
# 关联: docs/ops/JDCLOUD_NEWAPI_DEPLOY.md

set -e

# ── 颜色输出 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 配置常量（无敏感信息，密码由操作员在运行时输入）───────────────────────
NEWAPI_DIR="/opt/newapi"
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
NEWAPI_DB="newapi"
NEWAPI_MYSQL_USER="newapi"
# NEWAPI_MYSQL_PASS  ← 不在脚本中硬编码，运行时交互式输入
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
# REDIS_PASS          ← 同上，运行时输入
SESSION_SECRET="$(openssl rand -hex 24 2>/dev/null || head -c 48 /dev/urandom | base64 | tr -d '\n')"

echo "=========================================="
echo " Phase 1: 安装 new-api (Docker + MySQL)"
echo " 服务器: 117.72.118.95"
echo "=========================================="

# ── 1.1 检查 Docker ──────────────────────────────────────────────────────
info "[1/7] 检查 Docker..."
if ! command -v docker >/dev/null 2>&1; then
  error "未检测到 Docker，请先运行: curl -fsSL https://get.docker.com | bash -s -- --mirror Aliyun"
fi
if ! docker compose version >/dev/null 2>&1; then
  error "未检测到 docker compose plugin，请升级 Docker CE 20.10+"
fi
docker --version

# ── 1.2 交互式收集密码（不落盘）──────────────────────────────────────────
info "[2/7] 请输入数据库凭据（仅用于本次部署，不写入磁盘）..."
read -r -s -p "  MySQL newapi 用户密码: " NEWAPI_MYSQL_PASS; echo
[ -z "$NEWAPI_MYSQL_PASS" ] && error "MySQL 密码不能为空"
read -r -s -p "  Redis 密码（直接回车则无密码）: " REDIS_PASS; echo

# ── 1.3 在宿主机 MySQL 创建数据库和用户 ─────────────────────────────────
info "[3/7] 初始化 MySQL 数据库和用户..."
read -r -s -p "  请输入 MySQL root 密码（用于创建用户）: " MYSQL_ROOT_PASS; echo

mysql -u root -p"$MYSQL_ROOT_PASS" -h "$MYSQL_HOST" -P "$MYSQL_PORT" <<EOSQL
CREATE DATABASE IF NOT EXISTS ${NEWAPI_DB}
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${NEWAPI_MYSQL_USER}'@'%' IDENTIFIED BY '${NEWAPI_MYSQL_PASS}';
GRANT ALL PRIVILEGES ON ${NEWAPI_DB}.* TO '${NEWAPI_MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
EOSQL
info "✓ 数据库 ${NEWAPI_DB} 和用户 ${NEWAPI_MYSQL_USER} 创建完成"
unset MYSQL_ROOT_PASS  # 清除 root 密码

# ── 1.4 创建工作目录 ─────────────────────────────────────────────────────
info "[4/7] 创建 ${NEWAPI_DIR} 工作目录..."
sudo mkdir -p "${NEWAPI_DIR}/data" "${NEWAPI_DIR}/logs"
sudo chown -R "$USER":"$USER" "${NEWAPI_DIR}"

# ── 1.5 写入 docker-compose.yml（复用宿主机 MySQL/Redis，host 网络模式）
info "[5/7] 写入 docker-compose.yml..."
REDIS_CONN="redis://"
[ -n "$REDIS_PASS" ] && REDIS_CONN="redis://:${REDIS_PASS}@"
REDIS_CONN="${REDIS_CONN}${REDIS_HOST}:${REDIS_PORT}"

cat > "${NEWAPI_DIR}/docker-compose.yml" <<EOF
# ${NEWAPI_DIR}/docker-compose.yml
# 由 deploy/jdcloud/install_newapi.sh 自动生成
# 复用宿主机 MySQL 8.0 + Redis 7.0，使用 host 网络模式
# 真实渠道 key、用户 token 在 Web UI 中配置，不写入此文件
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
      - SQL_DSN=${NEWAPI_MYSQL_USER}:${NEWAPI_MYSQL_PASS}@tcp(${MYSQL_HOST}:${MYSQL_PORT})/${NEWAPI_DB}
      - REDIS_CONN_STRING=${REDIS_CONN}
      - TZ=Asia/Shanghai
      - BATCH_UPDATE_ENABLED=true
      - ERROR_LOG_ENABLED=true
      - SESSION_SECRET=${SESSION_SECRET}
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1:3000/api/status | grep -o '\"success\":\\\\s*true' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF

# 清除密码变量（安全）
unset NEWAPI_MYSQL_PASS REDIS_PASS SESSION_SECRET REDIS_CONN

# ── 1.6 拉镜像 + 启动 ───────────────────────────────────────────────────
info "[6/7] 拉取镜像并启动..."
cd "${NEWAPI_DIR}"
docker compose pull
docker compose up -d

info "等待容器 healthy（最多 60s）..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:3000/api/status >/dev/null 2>&1; then
    info "✓ new-api 启动成功（第 ${i}s）"
    break
  fi
  if [ "$i" -eq 60 ]; then
    warn "60s 超时，请手动检查: docker compose logs --tail=50"
  fi
  sleep 1
done
docker compose ps

# ── 1.7 验证 ─────────────────────────────────────────────────────────────
info "[7/7] loopback 健康检查..."
curl -sf http://127.0.0.1:3000/api/status | head -c 200; echo

echo ""
echo "=========================================="
echo " ✓ new-api 安装完成（MySQL + Redis 复用）"
echo "=========================================="
echo ""
echo " 数据库: MySQL ${NEWAPI_DB} @ ${MYSQL_HOST}:${MYSQL_PORT}"
echo " Redis:  ${REDIS_HOST}:${REDIS_PORT}"
echo " Web UI: http://127.0.0.1:3000"
echo ""
echo "下一步:"
echo "  1. 配置防火墙: bash deploy/jdcloud/configure_newapi_firewall.sh"
echo "  2. 部署 nginx 反代:"
echo "     sudo cp deploy/jdcloud/newapi.nginx.conf \\"
echo "       /etc/nginx/sites-available/api.donglicao.com.conf"
echo "     sudo ln -sf /etc/nginx/sites-available/api.donglicao.com.conf \\"
echo "       /etc/nginx/sites-enabled/"
echo "  3. 申请 TLS: sudo certbot --nginx -d api.donglicao.com"
echo "  4. 浏览器打开 https://api.donglicao.com，默认 root / 123456，立即改密码"
echo "  5. 关闭注册，添加渠道，添加用户 → 复制 sk-xxx 令牌"
echo ""
echo "回滚: cd ${NEWAPI_DIR} && docker compose down   # MySQL 数据不动"
echo ""
