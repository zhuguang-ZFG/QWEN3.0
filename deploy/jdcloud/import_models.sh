#!/bin/bash
# NewAPI 模型导入脚本（MySQL 批量导入）
# 用途：从 LiMa 优秀模型列表批量导入到 NewAPI
# 前提：newapi_models_export.json 已上传到 /tmp/
# 执行：ssh root@117.72.118.95，然后运行此脚本

set -euo pipefail

echo "=========================================="
echo "NewAPI 模型批量导入"
echo "=========================================="
echo ""

# 检查配置文件
if [ ! -f /tmp/newapi_models_export.json ]; then
    echo "❌ 未找到 /tmp/newapi_models_export.json"
    echo "请先执行: scp newapi_models_export.json root@117.72.118.95:/tmp/"
    exit 1
fi

echo "✅ 找到配置文件"
echo ""
echo "统计："
python3 -c "
import json
with open('/tmp/newapi_models_export.json') as f:
    data = json.load(f)
for cat, channels in data.items():
    print(f'  {cat}: {len(channels)} 个渠道')
"
echo ""
read -p "继续导入？(y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 生成 SQL
echo ""
echo "生成 SQL 插入语句..."
python3 << 'PYTHON_SCRIPT' > /tmp/newapi_channels.sql
import json

with open('/tmp/newapi_models_export.json') as f:
    data = json.load(f)

print("-- NewAPI 渠道批量导入")
print("-- 生成时间: 2026-06-11")
print("-- 来源: LiMa backends_registry")
print("")

for category in ['flagship', 'cost_effective', 'specialized', 'china']:
    if category not in data:
        continue

    print(f"-- {category.upper()}")
    for ch in data[category]:
        name = ch['name'].replace("'", "''")  # SQL 转义
        models = ','.join(ch['models'])
        base_url = ch['base_url']
        priority = ch['priority']

        # 注意：key 字段需要手动替换为真实密钥
        print(f"INSERT INTO newapi.channels (type, name, base_url, `key`, models, priority, status)")
        print(f"VALUES (15, '{name}', '{base_url}', '<<REPLACE_WITH_REAL_KEY>>', '{models}', {priority}, 1);")
        print("")

print("-- 导入完成后，替换 <<REPLACE_WITH_REAL_KEY>> 为真实 API Key")
PYTHON_SCRIPT

echo "✅ SQL 文件已生成: /tmp/newapi_channels.sql"
echo ""
echo "⚠️  重要：SQL 中的密钥为占位符 <<REPLACE_WITH_REAL_KEY>>"
echo "⚠️  你需要手动替换为真实 API Key 后再执行"
echo ""

# 显示预览
echo "预览前 10 行："
head -20 /tmp/newapi_channels.sql
echo "..."
echo ""

read -p "打开编辑器手动替换密钥？(y/N): " EDIT_SQL
if [[ "$EDIT_SQL" =~ ^[Yy]$ ]]; then
    ${EDITOR:-vim} /tmp/newapi_channels.sql
fi

echo ""
read -p "准备好执行 SQL 了吗？(y/N): " READY
if [[ ! "$READY" =~ ^[Yy]$ ]]; then
    echo "SQL 文件已保存到: /tmp/newapi_channels.sql"
    echo "手动执行: mysql -u root -p newapi < /tmp/newapi_channels.sql"
    exit 0
fi

# 执行 SQL
echo ""
read -sp "输入 MySQL root 密码: " MYSQL_PASS
echo ""

mysql -u root -p"$MYSQL_PASS" -h 127.0.0.1 newapi < /tmp/newapi_channels.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 导入成功！"
    echo ""
    echo "验证："
    mysql -u root -p"$MYSQL_PASS" -h 127.0.0.1 newapi -e "SELECT COUNT(*) AS total_channels FROM channels;"
    echo ""
    echo "下一步："
    echo "1. 打开 https://api.donglicao.com/channel 查看渠道列表"
    echo "2. 逐个测试渠道连通性"
    echo "3. 根据实际情况调整优先级"
else
    echo "❌ 导入失败，请检查错误信息"
    exit 1
fi
