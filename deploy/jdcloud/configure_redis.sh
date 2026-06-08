#!/bin/bash
# 京东云 Redis 安全配置脚本
# 生成随机密码并配置 Redis

set -e

echo "=========================================="
echo "Phase 1.2: 配置 Redis"
echo "=========================================="

# 备份原始配置
echo "[1/6] 备份原始配置..."
cp /etc/redis/redis.conf /etc/redis/redis.conf.backup.$(date +%Y%m%d_%H%M%S)

# 生成强密码
echo "[2/6] 生成 Redis 密码..."
REDIS_PASSWORD=$(openssl rand -base64 32)

echo ""
echo "=========================================="
echo "重要：请妥善保存以下密码！"
echo "=========================================="
echo "REDIS_PASSWORD=${REDIS_PASSWORD}"
echo ""
echo "将此密码保存到本地文件："
echo "  C:\\Users\\zhugu\\Downloads\\redis_password.txt"
echo "=========================================="
echo ""
read -p "按回车继续（确认已保存密码）..."

# 修改配置
echo "[3/6] 写入配置文件..."
cat > /etc/redis/redis.conf <<EOF
# Redis 配置 - LiMa 缓存专用
# 生成时间: $(date)
# 服务器: 117.72.118.95

# ============================================
# 网络配置
# ============================================
bind 0.0.0.0
port 6379
protected-mode yes
requirepass ${REDIS_PASSWORD}
timeout 300
tcp-keepalive 300

# ============================================
# 内存配置
# ============================================
maxmemory 1gb
maxmemory-policy allkeys-lru

# ============================================
# 持久化配置
# ============================================
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

# ============================================
# 日志配置
# ============================================
loglevel notice
logfile /var/log/redis/redis-server.log

# ============================================
# 数据库配置
# ============================================
databases 16

# ============================================
# 安全配置（禁用危险命令）
# ============================================
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN SHUTDOWN_$(openssl rand -hex 8)

# ============================================
# 性能优化
# ============================================
# 关闭 RDB 持久化期间的写入阻塞
stop-writes-on-bgsave-error no

# 慢查询日志
slowlog-log-slower-than 10000
slowlog-max-len 128
EOF

# 设置权限
echo "[4/6] 设置文件权限..."
chown redis:redis /etc/redis/redis.conf
chmod 640 /etc/redis/redis.conf

# 启动 Redis
echo "[5/6] 启动 Redis..."
systemctl enable redis-server
systemctl start redis-server

# 等待启动
sleep 2

# 检查状态
echo "[6/6] 检查 Redis 状态..."
systemctl status redis-server --no-pager

# 测试连接
echo ""
echo "测试 Redis 连接..."
redis-cli -a "${REDIS_PASSWORD}" ping

echo ""
echo "=========================================="
echo "✓ Redis 配置完成"
echo "=========================================="
echo ""
echo "Redis 信息:"
echo "  主机: 117.72.118.95"
echo "  端口: 6379"
echo "  密码: ${REDIS_PASSWORD}"
echo ""
echo "下一步: 运行 configure_firewall.sh 配置防火墙"
