# Start SSH tunnel + WCF->LiMa bridge (run after WeChat PC login)
$ErrorActionPreference = "Stop"
$Vps = if ($env:LIMA_VPS_HOST) { $env:LIMA_VPS_HOST } else { "47.112.162.80" }
$Key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }
$Root = Split-Path $PSScriptRoot -Parent

# Kill old tunnel on 8080 if any
Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "Starting SSH tunnel localhost:8080 -> VPS:8080 ..."
$tunnel = Start-Process ssh -ArgumentList @(
    "-N", "-L", "8080:127.0.0.1:8080", "-i", $Key, "root@$Vps"
) -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3

$tok = (ssh -i $Key root@$Vps "grep '^LIMA_WECHAT_SIDECAR_TOKEN=' /opt/lima-router/.env | cut -d= -f2-").Trim()
$env:LIMA_WECHAT_SIDECAR_TOKEN = $tok
$env:LIMA_CHANNEL_BASE_URL = "http://127.0.0.1:8080"

Set-Location $Root
Write-Host "Checking WeChat login via wcferry..."
python -c @"
from wcferry import Wcf
w = Wcf()
print('wechat_login', w.is_login())
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "请先完成 PC 微信扫码登录，再重新运行本脚本。"
    exit 2
}

Write-Host "Bridge running (Ctrl+C to stop). Send 你好 to this WeChat from another account."
python -m wechat_bridge.wcf_lima_bridge
