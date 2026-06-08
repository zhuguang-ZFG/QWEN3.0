#!/bin/bash
# 京东云 Hermes Agent Gateway 自动化部署脚本
# 服务器: 117.72.118.95 (2核4G 入门型)
# 用途: 为 LiMa 增加多步骤自主任务执行能力

set -e

echo "=========================================="
echo "京东云 Hermes Agent Gateway 部署脚本"
echo "=========================================="

# 1. 检查系统环境
echo ""
echo "[1/7] 检查系统环境..."
uname -a
free -h
df -h /

# 2. 更新系统并安装依赖
echo ""
echo "[2/7] 安装系统依赖..."
apt update
apt install -y python3 python3-pip python3-venv git curl nginx

# 3. 创建工作目录
echo ""
echo "[3/7] 创建工作目录..."
mkdir -p /opt/hermes-gateway
cd /opt/hermes-gateway

# 4. 创建 Python 虚拟环境
echo ""
echo "[4/7] 创建 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 5. 安装 Python 依赖
echo ""
echo "[5/7] 安装 Python 依赖..."
cat > requirements.txt <<EOF
fastapi==0.115.0
uvicorn[standard]==0.32.0
httpx==0.28.1
openai==1.57.0
pydantic==2.10.3
EOF

pip install --upgrade pip
pip install -r requirements.txt

# 6. 创建配置文件
echo ""
echo "[6/7] 创建配置文件..."
cat > /opt/hermes-gateway/.env <<EOF
LIMA_BASE_URL=http://47.112.162.80:8080/v1
LIMA_API_KEY=REPLACE_WITH_YOUR_KEY
LIMA_MODEL=lima-1.3
LIMA_TIMEOUT=120
HERMES_API_PORT=8699
HERMES_GATEWAY_PORT=18790
HERMES_DEBUG=0
EOF

# 7. 创建 systemd 服务
echo ""
echo "[7/7] 创建 systemd 服务..."
cat > /etc/systemd/system/hermes-gateway.service <<EOF
[Unit]
Description=Hermes Agent Gateway for LiMa
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/hermes-gateway
EnvironmentFile=/opt/hermes-gateway/.env
ExecStart=/opt/hermes-gateway/venv/bin/python hermes_api.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

# 资源限制（入门型服务器保护）
MemoryMax=1G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo ""
echo "=========================================="
echo "✓ 环境准备完成"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "1. 上传 hermes_api.py, hermes_bridge.py 到 /opt/hermes-gateway/"
echo "2. 编辑 /opt/hermes-gateway/.env，填入正确的 LIMA_API_KEY"
echo "3. 启动服务: systemctl start hermes-gateway"
echo "4. 查看状态: systemctl status hermes-gateway"
echo "5. 查看日志: journalctl -u hermes-gateway -f"
echo ""
