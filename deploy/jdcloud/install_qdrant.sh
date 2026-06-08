#!/bin/bash
# 京东云 Qdrant 安装脚本
# 服务器: 117.72.118.95
# 用途: LiMa 代码向量检索

set -e

echo "=========================================="
echo "Phase 2.1: 安装 Qdrant"
echo "=========================================="

# 检查 Docker
echo "[1/5] 检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "[OK] Docker 已安装"
else
    echo "[OK] Docker 已安装"
    docker --version
fi

# 创建数据目录
echo "[2/5] 创建数据目录..."
mkdir -p /opt/qdrant/storage
mkdir -p /opt/qdrant/snapshots
echo "[OK] 目录已创建"

# 拉取 Qdrant 镜像
echo "[3/5] 拉取 Qdrant 镜像..."
docker pull qdrant/qdrant:latest
echo "[OK] 镜像已拉取"

# 启动 Qdrant
echo "[4/5] 启动 Qdrant 容器..."
docker run -d \
    --name qdrant \
    --restart unless-stopped \
    -p 6333:6333 \
    -p 6334:6334 \
    -v /opt/qdrant/storage:/qdrant/storage:z \
    -v /opt/qdrant/snapshots:/qdrant/snapshots:z \
    qdrant/qdrant:latest

# 等待启动
sleep 5

# 检查健康
echo "[5/5] 检查 Qdrant 健康状态..."
max_attempts=10
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://127.0.0.1:6333/health > /dev/null 2>&1; then
        echo "[OK] Qdrant 运行正常"
        curl -s http://127.0.0.1:6333/health | python3 -m json.tool
        break
    else
        attempt=$((attempt + 1))
        echo "等待 Qdrant 启动... ($attempt/$max_attempts)"
        sleep 2
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo "[ERROR] Qdrant 启动失败"
    docker logs qdrant
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Qdrant 安装完成"
echo "=========================================="
echo ""
echo "访问信息:"
echo "  HTTP API: http://127.0.0.1:6333"
echo "  gRPC API: http://127.0.0.1:6334"
echo "  Web UI: http://117.72.118.95:6333/dashboard"
echo ""
echo "下一步: 配置防火墙"
echo "  运行: bash /tmp/configure_qdrant_firewall.sh"
