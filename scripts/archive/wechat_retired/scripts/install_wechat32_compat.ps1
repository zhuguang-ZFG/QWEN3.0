# WeChat 3.9.12 32-bit + ARM64WOWONAMD64 compat (fix "version too low" on Win10/11 x64)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Dir = Join-Path $Root "data\wechat_install"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

# Official 32-bit legacy installer (pc.weixin.qq.com)
$Urls = @(
    "https://dldir1v6.qq.com/weixin/Windows/WeChatSetup.exe",
    "https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe"
)
$Setup = Join-Path $Dir "WeChatSetup-32.exe"

if (-not (Test-Path $Setup) -or ((Get-Item $Setup).Length -lt 50MB)) {
    Write-Host "Downloading WeChat 3.9.12 32-bit installer..."
    $ok = $false
    foreach ($u in $Urls) {
        try {
            curl.exe -L --retry 3 -o $Setup $u
            if ((Get-Item $Setup).Length -gt 50MB) { $ok = $true; break }
        } catch { }
    }
    if (-not $ok) { throw "32-bit WeChat download failed" }
}

Write-Host "Installing 32-bit WeChat..."
$proc = Start-Process -FilePath $Setup -ArgumentList "/S" -Wait -PassThru
Write-Host "Installer exit:" $proc.ExitCode

$Candidates = @(
    "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
    "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
)
$WeChatExe = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $WeChatExe) { throw "WeChat.exe not found after install" }
Write-Host "WeChat:" $WeChatExe

# Registry compat layer (per WeChat3.9-32bit-Compatibility-Launcher)
$RegPath = Join-Path $Dir "wechat_compat.reg"
$Escaped = $WeChatExe -replace '\\', '\\'
@"
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers]
"$WeChatExe"="~ ARM64WOWONAMD64"
"@ | Set-Content -Path $RegPath -Encoding Unicode
reg import $RegPath | Out-Null
Write-Host "Compat registry applied."

# Skyler1n starter (more reliable than raw WeChat.exe on Win11)
$Bat = Join-Path (Split-Path $WeChatExe -Parent) "启动微信-LiMa.bat"
$StarterUrl = "https://github.com/Skyler1n/WeChat3.9-32bit-Compatibility-Launcher/releases/download/V1.0.0/wechat_starter_v1.0.0.exe"
$Starter = Join-Path $Dir "wechat_starter.exe"
if (-not (Test-Path $Starter) -or ((Get-Item $Starter).Length -lt 1MB)) {
    curl.exe -L --retry 3 -o $Starter $StarterUrl
}
$StarterDest = Join-Path (Split-Path $WeChatExe -Parent) "wechat_starter.exe"
Copy-Item $Starter $StarterDest -Force
$layers = "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
if (-not (Test-Path $layers)) { New-Item -Path $layers -Force | Out-Null }
Set-ItemProperty -Path $layers -Name $WeChatExe -Value "~ ARM64WOWONAMD64" -Type String -Force

@"
@echo off
cd /d "%~dp0"
start "" "%~dp0wechat_starter.exe"
"@ | Set-Content -Path $Bat -Encoding ASCII -Force

Write-Host "Starting WeChat via wechat_starter (compat layer)..."
Get-Process WeChat* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Start-Process $StarterDest

Write-Host ""
Write-Host "OK. ALWAYS use: $Bat  or desktop 微信-LiMa.lnk  (NOT the normal WeChat shortcut)"
Write-Host "After phone login, run: powershell -File D:\GIT\scripts\start_wechat_lima_bridge.ps1"
Write-Host ""
Write-Host "NOTE: wcferry hooks WeChat 3.9.12.51 from WeChatFerry release (32-bit client)."
Write-Host "  Host OS + Python must be 64-bit. Run: scripts\install_wechat_wcf.ps1"
