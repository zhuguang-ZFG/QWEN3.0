#!/bin/bash
# 京东云 Qdrant 防火墙配置
# 仅允许阿里云 VPS 访问

set -e

echo "=========================================="
echo "Phase 2.2: 配置 Qdrant 防火墙"
echo "=========================================="

# 允许阿里云 VPS 访问 Qdrant HTTP API (6333)
echo "[1/2] 配置 Qdrant HTTP API 规则..."
ufw allow from 47.112.162.80 to any port 6333 proto tcp comment 'LiMa Qdrant HTTP'

# 允许内网访问 (Tailscale)
ufw allow from 100.64.0.0/10 to any port 6333 proto tcp comment 'Qdrant Tailscale'

echo "[2/2] 重载防火墙..."
ufw reload

echo ""
echo "防火墙规则:"
ufw status | grep 6333

echo ""
echo "=========================================="
echo "✓ Qdrant 防火墙配置完成"
echo "=========================================="
echo ""
echo "Qdrant (6333) 仅允许:"
echo "  - 47.112.162.80 (阿里云公网)"
echo "  - 100.64.0.0/10 (Tailscale 内网)"
echo ""
echo "下一步: 在阿里云测试连接"
