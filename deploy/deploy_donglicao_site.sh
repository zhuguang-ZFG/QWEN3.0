#!/usr/bin/env bash
# deploy_donglicao_site.sh — Deploy donglicao-site files to VPS
# Usage: bash deploy/deploy_donglicao_site.sh
#
# Requires SSH key: ~/.ssh/id_ed25519
# VPS: root@47.112.162.80

set -euo pipefail

VPS="root@47.112.162.80"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $VPS"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="$SCRIPT_DIR/donglicao-site"
REMOTE_DIR="/var/www/chat"
BACKUP_TS="$(date +%Y%m%d_%H%M%S)"

echo "=== DongLiCao Site Deploy ==="
echo "Source: $SITE_DIR"
echo "Target: $VPS:$REMOTE_DIR"
echo ""

# 1. Backup existing files
echo "[1/4] Backing up existing files..."
$SSH "cd $REMOTE_DIR && [ -f index.html ] && cp index.html index.html.bak.$BACKUP_TS; echo 'backup done'"

# 2. Upload new files
echo "[2/4] Uploading files..."
for file in index.html lima-demo.js; do
    if [ -f "$SITE_DIR/$file" ]; then
        echo "  -> $file"
        $SCP "$SITE_DIR/$file" "$VPS:$REMOTE_DIR/$file"
    fi
done

# 3. Set permissions
echo "[3/4] Setting permissions..."
$SSH "chmod 644 $REMOTE_DIR/*.html $REMOTE_DIR/*.js 2>/dev/null || true"

# 4. Verify deployment
echo "[4/4] Verifying deployment..."
$SSH "curl -sf https://chat.donglicao.com/ | head -5"

echo ""
echo "=== Deploy complete ==="
echo "Backup tag: $BACKUP_TS"
echo "URL: https://chat.donglicao.com/"
