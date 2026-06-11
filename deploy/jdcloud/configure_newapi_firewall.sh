#!/bin/bash
# 京东云 new-api 专用防火墙配置脚本
# 节点: 117.72.118.95
# 规则: 仅开 22/80/443；3000/3306/6379 拒绝外部（host 网络模式下容器监听 0.0.0.0，需 ufw 拦截）
# 关联: docs/ops/JDCLOUD_NEWAPI_DEPLOY.md §3.4

set -e

echo "=========================================="
echo "Phase 2: 配置 new-api 防火墙"
echo "  (host 网络模式 - ufw 保护 3000/3306/6379)"
echo "=========================================="

# 1. 安装 ufw（如未装）
echo "[1/7] 安装 ufw..."
if ! command -v ufw >/dev/null 2>&1; then
  sudo apt install -y ufw
fi

# 2. 默认策略
echo "[2/7] 设置默认策略..."
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 3. SSH（避免锁死）
echo "[3/7] 允许 SSH..."
sudo ufw allow 22/tcp comment 'SSH'

# 4. HTTP / HTTPS（nginx 公网入口）
echo "[4/7] 允许 HTTP/HTTPS..."
sudo ufw allow 80/tcp comment 'HTTP (redirect to HTTPS)'
sudo ufw allow 443/tcp comment 'HTTPS (new-api via nginx)'

# 5. 阻止外部访问 3000（host 网络模式下容器监听 0.0.0.0:3000，必须用 ufw 拦截）
echo "[5/7] 拒绝外部访问 new-api 3000..."
sudo ufw deny 3000/tcp comment 'Block direct access to new-api (host network mode)'

# 6. 保护 MySQL/Redis 仅允许本地（已有规则则跳过）
echo "[6/7] 确认 MySQL/Redis 不暴露..."
sudo ufw deny 3306/tcp comment 'MySQL - block external (local only)'
sudo ufw deny 6379/tcp comment 'Redis - block external (local only)'

# 7. 启用防火墙
echo "[7/7] 启用 ufw..."
sudo ufw --force enable

# 展示状态
echo ""
echo "=========================================="
echo "防火墙规则:"
echo "=========================================="
sudo ufw status numbered

echo ""
echo "=========================================="
echo "✓ new-api 防火墙配置完成"
echo "=========================================="
echo ""
echo "  22    (SSH)            ALLOW IN    任意"
echo "  80    (HTTP→HTTPS)     ALLOW IN    任意"
echo "  443   (HTTPS)          ALLOW IN    任意"
echo "  3000  (new-api Web)    DENY  IN    全部（host 网络模式，仅通过 nginx 反代访问）"
echo "  3306  (MySQL)          DENY  IN    全部（仅本地访问）"
echo "  6379  (Redis)          DENY  IN    全部（仅本地访问）"
echo ""
echo "下一步: 配置 nginx 反代（newapi.nginx.conf）+ certbot 申请 TLS"
