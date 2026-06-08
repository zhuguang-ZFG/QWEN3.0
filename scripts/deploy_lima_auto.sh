#!/bin/bash
# LiMa 自动化部署脚本
# 执行原则: Superpowers ✅

set -e

echo "======================================"
echo "LiMa 自动化部署"
echo "======================================"

# 1. 备份当前版本
backup_current_version() {
    echo ""
    echo "[1/6] 备份当前版本..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    cd /opt && tar -czf lima-router.backup.$timestamp.tar.gz lima-router/
    echo "[OK] 备份完成: lima-router.backup.$timestamp.tar.gz"
}

# 2. 拉取最新代码
pull_latest_code() {
    echo ""
    echo "[2/6] 拉取最新代码..."
    cd /opt/lima-router
    git fetch origin
    git pull origin codex/free-web-ai-probe
    echo "[OK] 代码更新完成"
}

# 3. 安装依赖
install_dependencies() {
    echo ""
    echo "[3/6] 安装依赖..."
    cd /opt/lima-router
    if [ -f requirements.txt ]; then
        .venv/bin/pip install -r requirements.txt -q
        echo "[OK] 依赖安装完成"
    else
        echo "[INFO] 未找到 requirements.txt"
    fi
}

# 4. 重启服务
restart_service() {
    echo ""
    echo "[4/6] 重启服务..."
    systemctl restart lima-router
    sleep 3
    status=$(systemctl is-active lima-router)
    if [ "$status" = "active" ]; then
        echo "[OK] 服务重启完成: $status"
    else
        echo "[ERROR] 服务状态异常: $status"
        exit 1
    fi
}

# 5. 验证部署
verify_deployment() {
    echo ""
    echo "[5/6] 验证部署..."

    # 健康检查
    response=$(curl -s http://127.0.0.1:8080/health)
    if echo "$response" | grep -q "ok"; then
        echo "[OK] 健康检查通过"
    else
        echo "[WARN] 健康检查响应异常"
    fi

    # 后端数量
    backend_count=$(cd /opt/lima-router && python3 -c "import backends_registry; print(len(backends_registry.BACKENDS))" 2>/dev/null || echo "0")
    echo "[INFO] 后端配置: $backend_count 个"

    # OpenCode 模块
    opencode_count=$(ls /opt/lima-router/opencode_*.py 2>/dev/null | wc -l)
    echo "[INFO] OpenCode 模块: $opencode_count 个"
}

# 6. 生成部署报告
generate_report() {
    echo ""
    echo "[6/6] 生成部署报告..."

    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    git_commit=$(cd /opt/lima-router && git log -1 --oneline 2>/dev/null || echo "Unknown")

    cat > /tmp/lima_deploy_report.txt << EOREPORT
LiMa 部署报告
========================================
时间: $timestamp
Git 提交: $git_commit
后端数量: $backend_count
OpenCode: $opencode_count 个模块
服务状态: $(systemctl is-active lima-router)
========================================
EOREPORT

    cat /tmp/lima_deploy_report.txt
    echo "[OK] 报告已保存: /tmp/lima_deploy_report.txt"
}

# 主流程
main() {
    backup_current_version
    pull_latest_code
    install_dependencies
    restart_service
    verify_deployment
    generate_report

    echo ""
    echo "======================================"
    echo "[成功] 部署完成"
    echo "======================================"
}

# 错误处理
trap 'echo "[错误] 部署失败，请检查日志"; exit 1' ERR

# 执行
main
