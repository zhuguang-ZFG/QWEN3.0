#!/bin/bash
# Setup GitHub Secrets for LiMa CI/CD
# Run after: gh auth login
#
# Usage: bash scripts/setup_github_secrets.sh

set -euo pipefail

REPO="zhuguang-ZFG/QWEN3.0"

echo "Setting GitHub secrets for $REPO ..."
echo "(You'll be prompted for each secret value)"
echo ""

# VPS SSH private key
gh secret set VPS_SSH_KEY --repo "$REPO" < ~/.ssh/id_ed25519
echo "  VPS_SSH_KEY: set"

# VPS connection
gh secret set VPS_HOST --repo "$REPO" --body "47.112.162.80"
echo "  VPS_HOST: set"

gh secret set VPS_USER --repo "$REPO" --body "root"
echo "  VPS_USER: set"

# Telegram notifications
echo ""
echo "Enter Telegram Bot Token:"
gh secret set TELEGRAM_BOT_TOKEN --repo "$REPO"
echo "  TELEGRAM_BOT_TOKEN: set"

echo "Enter Telegram Chat ID:"
gh secret set TELEGRAM_CHAT_ID --repo "$REPO"
echo "  TELEGRAM_CHAT_ID: set"

echo ""
echo "Done! All 5 secrets configured."
echo "Next: push to main to trigger the deploy workflow."
