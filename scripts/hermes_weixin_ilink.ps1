# Hermes Agent — WeChat (Weixin) iLink: QR login + start gateway
# Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/weixin
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

pip install "hermes-agent[messaging]" aiohttp cryptography qrcode -q 2>$null | Out-Null

Write-Host "=== QR login (opens browser + terminal ASCII QR) ==="
python "$Root\scripts\hermes_weixin_qr_login.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Hermes = "C:\Python311\Scripts\hermes.exe"
$st = & $Hermes gateway status 2>&1 | Out-String
if ($st -notmatch "running") {
    Write-Host "=== Starting gateway ==="
    Start-Process -FilePath $Hermes -ArgumentList "gateway","run","--accept-hooks" -WindowStyle Minimized
    Start-Sleep 12
    & $Hermes gateway status
}
Write-Host ""
Write-Host "Done. Send a DM to the iLink bot from another WeChat account."
Write-Host "QR page (if re-login): $Root\data\hermes_weixin_login_qr.html"
