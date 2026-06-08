#!/bin/bash
# 阿里云 VPS 测试 Redis 连接脚本
# 在阿里云 VPS 上执行

set -e

echo "=========================================="
echo "Phase 1.4: 测试 Redis 连接"
echo "=========================================="

# 检查环境变量
if [ -z "$REDIS_PASSWORD" ]; then
    echo "[ERROR] REDIS_PASSWORD 环境变量未设置"
    echo ""
    echo "请先设置密码:"
    echo "  export REDIS_PASSWORD='<京东云生成的密码>'"
    echo ""
    exit 1
fi

REDIS_HOST="117.72.118.95"
REDIS_PORT="6379"

echo "连接信息:"
echo "  主机: ${REDIS_HOST}"
echo "  端口: ${REDIS_PORT}"
echo ""

# 安装 redis-tools（如果未安装）
if ! command -v redis-cli &> /dev/null; then
    echo "安装 redis-cli..."
    apt update && apt install -y redis-tools
fi

# 测试 1: Ping
echo "[测试 1/4] Ping 连接..."
RESULT=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping 2>&1)

if [ "$RESULT" == "PONG" ]; then
    echo "✓ Ping 成功"
else
    echo "✗ Ping 失败: $RESULT"
    exit 1
fi

# 测试 2: 写入
echo "[测试 2/4] 测试写入..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET lima:test:$(date +%s) "test_value" > /dev/null
echo "✓ 写入成功"

# 测试 3: 读取
echo "[测试 3/4] 测试读取..."
TEST_KEY="lima:test:connection"
TEST_VALUE="Hello from LiMa @ $(date)"
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET "$TEST_KEY" "$TEST_VALUE" > /dev/null

RETRIEVED=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD GET "$TEST_KEY")

if [ "$RETRIEVED" == "$TEST_VALUE" ]; then
    echo "✓ 读取成功"
else
    echo "✗ 读取失败"
    echo "  期望: $TEST_VALUE"
    echo "  实际: $RETRIEVED"
    exit 1
fi

# 测试 4: 统计信息
echo "[测试 4/4] 获取统计信息..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD INFO server | grep redis_version

# 清理测试数据
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD DEL "$TEST_KEY" > /dev/null

echo ""
echo "=========================================="
echo "✓ Redis 连接测试通过"
echo "=========================================="
echo ""
echo "下一步: 集成到 LiMa"
echo "  1. 部署 semantic_cache_enhanced.py"
echo "  2. 配置环境变量"
echo "  3. 重启 lima-router"
echo ""
echo "环境变量配置:"
echo "  export REDIS_HOST=117.72.118.95"
echo "  export REDIS_PORT=6379"
echo "  export REDIS_PASSWORD='<密码>'"
echo "  export LIMA_REDIS_CACHE_ENABLED=1"
