# Quick wcferry health check (WeChat 3.9.12.51 + wcferry 39.5.2)
$ErrorActionPreference = "Continue"
$WantVer = "3.9.12.51"

$WeChat = @(
    "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
    "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $WeChat) {
    Write-Host "FAIL: WeChat not found. Run: scripts\install_wechat_wcf.ps1"
    exit 1
}

$WxDir = Split-Path $WeChat -Parent
$Starter = Join-Path $WxDir "wechat_starter.exe"
$ver = (Get-Item $WeChat).VersionInfo.FileVersion
Write-Host "WeChat:" $WeChat
Write-Host "Version:" $ver "(want $WantVer)"
if ($ver -ne $WantVer) {
    Write-Host "WARN: Use pinned installer: D:\GIT\data\wechat_install\WeChatSetup-3.9.12.51.exe"
}
if (-not (Test-Path $Starter)) {
    Write-Host "WARN: wechat_starter.exe missing. Run: scripts\fix_wechat_login.ps1"
}

Get-Process WeChat* -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 2
foreach ($p in 10086, 10087) {
    $hit = netstat -ano | Select-String ":$p "
    if ($hit) { Write-Host "WARN: port $p in use`n$hit" }
}

$Launch = if (Test-Path $Starter) { $Starter } else { $WeChat }
Write-Host "Starting WeChat via:" $Launch
Start-Process $Launch
Start-Sleep 10
if (-not (Get-Process WeChat -EA SilentlyContinue)) {
    Write-Host "FAIL: WeChat did not start. Use desktop 微信-LiMa.lnk if version-too-low."
    exit 1
}

Write-Host "Testing wcferry..."
python -c "from wcferry import Wcf; w=Wcf(block=False); import time; time.sleep(2); print('is_login', w.is_login())"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "If init failed:"
    Write-Host "  1) Login via 微信-LiMa shortcut (not green WeChat icon)"
    Write-Host "  2) Run as Administrator  3) Kill all WeChat* in Task Manager and retry"
    exit 1
}
Write-Host "OK: wcferry initialized"
