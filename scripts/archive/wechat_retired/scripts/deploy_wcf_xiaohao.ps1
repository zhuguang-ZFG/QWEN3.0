# LiMa WCF xiaohao redeploy (64-bit Windows): install -> compat -> optional bridge
param(
    [switch]$SkipInstall,
    [switch]$StartBridge
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\WeChat-Arch.ps1")

$hostCheck = Test-LiMaWcfHostOk
if (-not $hostCheck.Ok) {
    Write-Host $hostCheck.Message
    exit 1
}

Write-Host "=== LiMa WCF redeploy (64-bit host OK) ==="
Write-LiMaWeChatArchBrief

$oldWx = "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe"
if (-not $SkipInstall -and -not (Test-Path $oldWx)) {
    Write-Host "WeChat 3.9.12.51 not found. Launching installer GUI..."
    Write-Host "Complete the wizard, then re-run: deploy_wcf_xiaohao.ps1 -SkipInstall"
    Start-Process "D:\GIT\data\wechat_install\WeChatSetup-3.9.12.51.exe"
    exit 10
}

if (-not (Test-Path $oldWx)) {
    throw "WeChat 3.9.12.51 missing at $oldWx"
}

Write-Host "=== compat + 微信-LiMa shortcut ==="
& (Join-Path $PSScriptRoot "fix_wechat_login.ps1")

Write-Host "=== VPS channel (remote) ==="
$Key = "$env:USERPROFILE\.ssh\id_ed25519"
$Vps = "47.112.162.80"
ssh -i $Key root@$Vps "grep '^WECHAT_BRIDGE_ENABLED=' /opt/lima-router/.env; curl -s -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:8080/health"

Write-Host ""
Write-Host "=== local wcferry check ==="
& (Join-Path $PSScriptRoot "check_wcferry.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Login with 微信-LiMa, then: deploy_wcf_xiaohao.ps1 -SkipInstall -StartBridge"
    exit 2
}

if ($StartBridge) {
    & (Join-Path $PSScriptRoot "start_wechat_lima_bridge.ps1")
}

Write-Host ""
Write-Host "Done. Test: another WeChat account sends 你好 to the small account."
