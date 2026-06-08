#!/bin/bash
# 京东云防火墙配置脚本
# 仅允许阿里云 VPS 访问 Redis 和 Qdrant

set -e

echo "=========================================="
echo "Phase 1.3: 配置防火墙"
echo "=========================================="

# 安装 ufw
echo "[1/5] 安装 ufw..."
apt install -y ufw

# 默认策略
echo "[2/5] 设置默认策略..."
ufw default deny incoming
ufw default allow outgoing

# 允许 SSH（避免锁死）
echo "[3/5] 允许 SSH..."
ufw allow 22/tcp comment 'SSH'

# 允许阿里云 VPS 访问 Redis
echo "[4/5] 允许阿里云访问 Redis..."
ufw allow from 47.112.162.80 to any port 6379 proto tcp comment 'LiMa Redis'

# 允许阿里云 VPS 访问 Qdrant（预留）
ufw allow from 47.112.162.80 to any port 6333 proto tcp comment 'LiMa Qdrant'

# 启用防火墙
echo "[5/5] 启用防火墙..."
ufw --force enable

# 查看状态
echo ""
echo "防火墙规则:"
ufw status numbered

echo ""
echo "=========================================="
echo "✓ 防火墙配置完成"
echo "=========================================="
echo ""
echo "Redis (6379) 仅允许 47.112.162.80 访问"
echo "Qdrant (6333) 仅允许 47.112.162.80 访问"
echo ""
echo "下一步: 在阿里云 VPS 测试连接"
echo "  运行: bash scripts/test_redis_connection.sh"
