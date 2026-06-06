#!/usr/bin/env bash
# deploy_nginx.sh — Deploy Nginx configs from repo to VPS
# Usage: bash deploy/nginx/deploy_nginx.sh
#
# Requires SSH key: ~/.ssh/id_ed25519
# VPS: root@47.112.162.80

set -euo pipefail

VPS="root@47.112.162.80"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $VPS"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_DIR="/etc/nginx/conf.d"
BACKUP_TS="$(date +%Y%m%d_%H%M%S)"

echo "=== LiMa Nginx Deploy ==="
echo "Source: $SCRIPT_DIR"
echo "Target: $VPS:$CONF_DIR"
echo ""

# 1. Backup existing configs
echo "[1/4] Backing up existing configs..."
$SSH "cd $CONF_DIR && for f in chat.donglicao.com.conf www.donglicao.com.conf donglicao.conf lima.257339.xyz.conf; do [ -f \$f ] && cp \$f \$f.bak.$BACKUP_TS; done; echo 'backup done'"

# 2. Upload new configs
echo "[2/4] Uploading configs..."
for conf in chat.donglicao.com.conf www.donglicao.com.conf donglicao.conf lima.257339.xyz.conf; do
    echo "  -> $conf"
    $SCP "$SCRIPT_DIR/$conf" "$VPS:$CONF_DIR/$conf"
done

# 3. Test nginx config
echo "[3/4] Testing nginx configuration..."
$SSH "nginx -t"
if [ $? -ne 0 ]; then
    echo "ERROR: nginx -t failed! Rolling back..."
    $SSH "cd $CONF_DIR && for f in chat.donglicao.com.conf www.donglicao.com.conf donglicao.conf lima.257339.xyz.conf; do [ -f \$f.bak.$BACKUP_TS ] && cp \$f.bak.$BACKUP_TS \$f; done"
    $SSH "systemctl reload nginx"
    echo "Rollback complete."
    exit 1
fi

# 4. Reload nginx
echo "[4/4] Reloading nginx..."
$SSH "systemctl reload nginx"

echo ""
echo "=== Deploy complete ==="
echo "Backup tag: $BACKUP_TS"
