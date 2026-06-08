#!/bin/bash
# 验证 VPS 部署

VPS="https://chat.donglicao.com"

echo "=== 验证 VPS 部署 ==="
echo

echo "1. 健康检查"
health=$(curl -s "$VPS/health")
if echo "$health" | grep -q '"status":"ok"'; then
    echo "✓ 健康检查通过"
    echo "$health" | head -3
else
    echo "✗ 健康检查失败"
    echo "$health"
    exit 1
fi

echo
echo "2. 管理页面"
admin=$(curl -s "$VPS/admin")
if echo "$admin" | grep -qi "admin"; then
    echo "✓ 管理页面可访问"
else
    echo "✗ 管理页面失败"
    exit 1
fi

echo
echo "3. 后端 API（未认证）"
backends=$(curl -s "$VPS/admin/api/backends")
if echo "$backends" | grep -q "Unauthorized"; then
    echo "✓ 后端 API 正常（需要认证）"
else
    echo "✗ 后端 API 异常"
    echo "$backends"
fi

echo
echo "=== 所有验证通过 ==="
