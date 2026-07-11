# DEPRECATED for daily use — public HTTPS already routes Claude chat to :3001.
# JDCloud nginx (api.donglicao.com):
#   location = /v1/chat/completions → 127.0.0.1:3001
#   location = /v1/messages         → 127.0.0.1:3001
# Set providers.newapi-claude.base_url = "https://api.donglicao.com/v1"
#
# Only use this tunnel for offline/debug when public edge is down.
# Do NOT run chat smoke / cache probes against Claude (burns upstream quota).

$ErrorActionPreference = "Stop"
Write-Host "NOTE: Prefer https://api.donglicao.com/v1 (no tunnel). Continuing optional tunnel..." -ForegroundColor Yellow
$Host_ = if ($env:LIMA_JDCLOUD_SERVER) { $env:LIMA_JDCLOUD_SERVER } else { "117.72.118.95" }
$Key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }
$sshArgs = @("-N", "-L", "3001:127.0.0.1:3001", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new")
if (Test-Path $Key) { $sshArgs += @("-i", $Key) }
ssh @sshArgs "root@$Host_"
