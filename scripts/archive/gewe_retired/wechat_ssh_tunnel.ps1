# Open local browser to VPS sidecar login page (requires SSH key).
# Usage: .\scripts\wechat_ssh_tunnel.ps1
# Then open: http://127.0.0.1:9919/login-qr
$host = if ($env:LIMA_VPS_HOST) { $env:LIMA_VPS_HOST } else { "47.112.162.80" }
$key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }
Write-Host "Tunnel: http://127.0.0.1:9919/login-qr  (Ctrl+C to stop)"
ssh -N -L 9919:127.0.0.1:9919 -i $key root@$host
