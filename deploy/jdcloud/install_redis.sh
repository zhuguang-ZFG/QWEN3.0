#!/bin/bash
# 京东云 Redis 安装脚本
# 服务器: 117.72.118.95
# 用途: LiMa 缓存层

set -e

echo "=========================================="
echo "Phase 1.1: 安装 Redis"
echo "=========================================="

# 更新系统
echo "[1/5] 更新系统包..."
apt update

# 安装 Redis
echo "[2/5] 安装 Redis..."
apt install -y redis-server redis-tools

# 检查版本
echo "[3/5] 检查版本..."
redis-server --version

# 创建备份目录
echo "[4/5] 创建备份目录..."
mkdir -p /var/backups/redis

# 停止 Redis（稍后配置后启动）
echo "[5/5] 停止 Redis（等待配置）..."
systemctl stop redis-server

echo ""
echo "=========================================="
echo "✓ Redis 安装完成"
echo "=========================================="
echo ""
echo "下一步: 运行 configure_redis.sh 配置 Redis"
