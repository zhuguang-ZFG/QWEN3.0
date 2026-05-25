# Install WeChat 3.9.12.51 (32-bit client) + wcferry + Win11 compat launcher
# Host must be 64-bit Windows + 64-bit Python. WeChat installer PE is 32-bit (not a mismatch).
param(
    [switch]$SilentInstall
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\WeChat-Arch.ps1")

$hostCheck = Test-LiMaWcfHostOk
if (-not $hostCheck.Ok) {
    Write-Host $hostCheck.Message
    exit 1
}
Write-LiMaWeChatArchBrief

$Root = Split-Path $PSScriptRoot -Parent
$Dir = Join-Path $Root "data\wechat_install"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

$WeChatUrl = "https://github.com/lich0821/WeChatFerry/releases/download/v39.5.2/WeChatSetup-3.9.12.51.exe"
$WeChatExe = Join-Path $Dir "WeChatSetup-3.9.12.51.exe"

if (-not (Test-Path $WeChatExe) -or ((Get-Item $WeChatExe).Length -lt 200MB)) {
    Write-Host "Downloading WeChat 3.9.12.51 (~272MB, 32-bit client)..."
    curl.exe -L --retry 3 --retry-delay 5 -o $WeChatExe $WeChatUrl
}
if (-not (Test-Path $WeChatExe)) { throw "download failed: $WeChatExe" }

$peLabel = Get-PeArchLabel $WeChatExe
Write-Host "Installer PE:" $peLabel
Write-Host "NOTE: On Win11 the WCF .51 installer may still place a 64-bit WeChat.exe."
Write-Host "      If fix_wechat_login reports 64-bit, run: scripts\fix_wechat_version_low.ps1"

Write-Host "=== wcferry (Python 64-bit) ==="
pip install "wcferry==39.5.2.0" -q
pip show wcferry | Select-String Version

$sdkDir = python -c "import wcferry, pathlib; print(pathlib.Path(wcferry.__file__).parent)"
$sdk = Join-Path $sdkDir "sdk.dll"
if (Test-Path $sdk) {
    Write-Host "wcferry sdk.dll PE:" (Get-PeArchLabel $sdk)
}

function Find-WeChatExe {
    @(
        "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
        "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ($SilentInstall) {
    Write-Host ""
    Write-Host "WARN: Silent /S often fails. Prefer default GUI install."
    $proc = Start-Process -FilePath $WeChatExe -ArgumentList "/S" -Wait -PassThru
    Write-Host "Installer exit code:" $proc.ExitCode
    if (-not (Find-WeChatExe)) {
        Write-Host "Silent install failed. Re-run without -SilentInstall."
        exit 1
    }
}

Write-Host ""
Write-Host "=== WeChat GUI + compat (32-bit client, fix_wechat_login.ps1) ==="
Write-Host "If installer says 64-bit required: you are on 32-bit Windows — WCF cannot run here."
Write-Host ""
& (Join-Path $PSScriptRoot "fix_wechat_login.ps1")

Write-Host ""
Write-Host "Next:"
Write-Host "  1) Login via desktop 微信-LiMa (32-bit WeChat + compat)"
Write-Host "  2) scripts\check_wcferry.ps1"
Write-Host "  3) SSH tunnel + scripts\start_wechat_lima_bridge.ps1"
Write-Host "Doc: $Root\docs\WECHAT_WCF_XIAOHAO.md"
