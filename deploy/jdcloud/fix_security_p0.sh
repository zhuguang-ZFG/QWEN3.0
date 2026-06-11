#!/bin/bash
# NewAPI P0 安全修复脚本
# 用途：重置泄露凭据 + 加固 MySQL 访问控制
# 执行：ssh root@117.72.118.95，然后运行此脚本
# 日期：2026-06-11

set -euo pipefail

echo "=========================================="
echo "NewAPI P0 安全修复"
echo "=========================================="
echo ""
echo "⚠️  警告：此脚本将重置 root 密码和 API Key"
echo "⚠️  请准备好新密码（至少 16 位）"
echo ""
read -p "按 Enter 继续，Ctrl+C 取消..."

# 1. 生成新密码 hash
echo ""
echo "=== 步骤 1/4：生成新密码 hash ==="
read -sp "输入新 root 密码（至少 16 位）: " NEW_PASSWORD
echo ""
read -sp "确认新密码: " NEW_PASSWORD_CONFIRM
echo ""

if [ "$NEW_PASSWORD" != "$NEW_PASSWORD_CONFIRM" ]; then
    echo "❌ 密码不匹配，退出"
    exit 1
fi

if [ ${#NEW_PASSWORD} -lt 16 ]; then
    echo "❌ 密码长度不足 16 位，退出"
    exit 1
fi

echo "生成 bcrypt hash（Go 兼容 \$2a\$ 前缀）..."
NEW_PASSWORD_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$NEW_PASSWORD', bcrypt.gensalt(prefix=b'2a')).decode())")
echo "✅ Hash 生成完成"

# 2. 生成新 API token
echo ""
echo "=== 步骤 2/4：生成新 API access_token ==="
NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")
echo "✅ 新 Token: $NEW_TOKEN"

# 3. 更新数据库
echo ""
echo "=== 步骤 3/4：更新数据库 ==="
read -sp "输入 MySQL root 密码: " MYSQL_ROOT_PASS
echo ""

# 检查 newapi 用户是否存在
USER_EXISTS=$(mysql -u root -p"$MYSQL_ROOT_PASS" -h 127.0.0.1 -se "SELECT COUNT(*) FROM mysql.user WHERE User='newapi' AND Host='%';")

if [ "$USER_EXISTS" -gt 0 ]; then
    echo "重置 root 密码..."
    mysql -u root -p"$MYSQL_ROOT_PASS" -h 127.0.0.1 <<EOF
UPDATE newapi.users SET password='$NEW_PASSWORD_HASH' WHERE username='root';
UPDATE newapi.users SET access_token='$NEW_TOKEN' WHERE username='root';
EOF
    echo "✅ 凭据已更新"

    echo ""
    echo "=== 步骤 4/4：加固 MySQL 访问控制 ==="
    read -p "限制 newapi 用户为 127.0.0.1？这会影响远程连接。(y/N): " RESTRICT_MYSQL

    if [[ "$RESTRICT_MYSQL" =~ ^[Yy]$ ]]; then
        # 生成新的 MySQL newapi 用户密码
        read -sp "输入新的 MySQL newapi 用户密码（至少 16 位）: " NEWAPI_MYSQL_PASS
        echo ""

        mysql -u root -p"$MYSQL_ROOT_PASS" -h 127.0.0.1 <<EOF
DROP USER IF EXISTS 'newapi'@'%';
CREATE USER 'newapi'@'127.0.0.1' IDENTIFIED BY '$NEWAPI_MYSQL_PASS';
GRANT ALL PRIVILEGES ON newapi.* TO 'newapi'@'127.0.0.1';
FLUSH PRIVILEGES;
EOF
        echo "✅ MySQL 用户已限制为 127.0.0.1"

        # 更新 docker-compose.yml
        echo ""
        echo "更新 docker-compose.yml 中的 SQL_DSN..."
        cd /opt/newapi
        if [ -f docker-compose.yml ]; then
            sed -i.bak "s/SQL_DSN=newapi:[^@]*@tcp/SQL_DSN=newapi:$NEWAPI_MYSQL_PASS@tcp/" docker-compose.yml
            echo "✅ docker-compose.yml 已更新（备份: docker-compose.yml.bak）"

            echo ""
            read -p "重启 new-api 容器以应用更改？(y/N): " RESTART_CONTAINER
            if [[ "$RESTART_CONTAINER" =~ ^[Yy]$ ]]; then
                docker compose restart
                echo "✅ 容器已重启"
            else
                echo "⚠️  请手动执行: docker compose -f /opt/newapi/docker-compose.yml restart"
            fi
        else
            echo "⚠️  未找到 /opt/newapi/docker-compose.yml，请手动更新 SQL_DSN"
        fi
    else
        echo "⏭️  跳过 MySQL 限制"
    fi
else
    echo "⚠️  未找到 newapi@'%' 用户，仅更新密码和 token"
    mysql -u root -p"$MYSQL_ROOT_PASS" -h 127.0.0.1 <<EOF
UPDATE newapi.users SET password='$NEW_PASSWORD_HASH' WHERE username='root';
UPDATE newapi.users SET access_token='$NEW_TOKEN' WHERE username='root';
EOF
    echo "✅ 凭据已更新"
fi

# 5. 验证
echo ""
echo "=========================================="
echo "修复完成！"
echo "=========================================="
echo ""
echo "📋 新凭据（请妥善保管）："
echo "-------------------------------------------"
echo "Web UI URL: https://api.donglicao.com"
echo "用户名: root"
echo "密码: <你刚才输入的密码>"
echo "API Token: $NEW_TOKEN"
echo "-------------------------------------------"
echo ""
echo "⚠️  重要："
echo "1. 立即用新密码登录 Web UI 验证"
echo "2. 将新凭据保存到 Infisical 或密码管理器"
echo "3. 从本地删除此脚本的 shell 历史"
echo ""
echo "清理历史命令："
echo "  history -c && history -w"
echo ""
