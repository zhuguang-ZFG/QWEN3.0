# Fix "version too low" / apply compat: GUI 3.9.12.51 + wechat_starter (Win10/11 x64)
# Usually invoked by install_wechat_wcf.ps1; safe to re-run alone.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Dir = Join-Path $Root "data\wechat_install"
$Setup = Join-Path $Dir "WeChatSetup-3.9.12.51.exe"
$StarterSrc = Join-Path $Dir "wechat_starter.exe"
$StarterUrl = "https://github.com/Skyler1n/WeChat3.9-32bit-Compatibility-Launcher/releases/download/V1.0.0/wechat_starter_v1.0.0.exe"

$weixin4 = "${env:ProgramFiles}\Tencent\Weixin\Weixin.exe"
if (Test-Path $weixin4) {
    $v = (Get-Item $weixin4).VersionInfo.FileVersion
    Write-Host "NOTE: Weixin $v is installed (4.x). LiMa WCF uses separate WeChat 3.9.12.51."
    Write-Host "      Do NOT use Public Desktop 微信.lnk for the bridge; use 微信-LiMa only."
}

if (-not (Test-Path $Setup)) {
    Write-Host "Downloading WeChat 3.9.12.51..."
    curl.exe -L --retry 3 -o $Setup "https://github.com/lich0821/WeChatFerry/releases/download/v39.5.2/WeChatSetup-3.9.12.51.exe"
}
if (-not (Test-Path $StarterSrc) -or ((Get-Item $StarterSrc).Length -lt 1MB)) {
    curl.exe -L --retry 3 -o $StarterSrc $StarterUrl
}

$WeChatExe = @(
    "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
    "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $WeChatExe) {
    Write-Host ""
    Write-Host ">>> WeChat not installed. Opening installer GUI - click through to finish install <<<"
    Write-Host ""
    Start-Process -FilePath $Setup -Wait
    $WeChatExe = @(
        "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
        "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $WeChatExe) { throw "Install finished but WeChat.exe still not found" }
}

. (Join-Path $PSScriptRoot "lib\WeChat-Arch.ps1")
$machine = Get-PeMachineType $WeChatExe
if ($machine -eq 0x8664) {
    Write-Host ""
    Write-Host "ERROR: $WeChatExe is 64-bit. Tencent blocks 3.9.x 64-bit login (version too low)."
    Write-Host "       Run: powershell -File D:\GIT\scripts\fix_wechat_version_low.ps1"
    Write-Host "       Need 32-bit WeChat under Program Files (x86)\Tencent\WeChat"
    exit 3
}
if ($machine -ne 0x014c) {
    Write-Host "WARN: Unexpected PE type 0x$("{0:X}" -f $machine) for $WeChatExe"
}

$WxDir = Split-Path $WeChatExe -Parent
Copy-Item $StarterSrc (Join-Path $WxDir "wechat_starter.exe") -Force

$layers = "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
if (-not (Test-Path $layers)) { New-Item -Path $layers -Force | Out-Null }
Set-ItemProperty -Path $layers -Name $WeChatExe -Value "~ ARM64WOWONAMD64" -Type String -Force

$upd = "HKCU:\Software\Tencent\WeChat"
if (Test-Path $upd) {
    Set-ItemProperty -Path $upd -Name "NeedUpdateType" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
}

$Bat = Join-Path $WxDir "lima-wechat.bat"
Copy-Item (Join-Path $Root "scripts\launch_wechat_lima.bat") $Bat -Force
if (-not (Test-Path $Bat)) {
    @"
@echo off
cd /d "%~dp0"
set "__COMPAT_LAYER=~ ARM64WOWONAMD64"
start "" "%~dp0WeChat.exe"
"@ | Set-Content -Path $Bat -Encoding ASCII -Force
}

$desk = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desk "WeChat-LiMa.lnk"
$sh = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sh.TargetPath = $Bat
$sh.WorkingDirectory = $WxDir
$sh.Description = "WeChat 3.9 + compat (avoid version too low)"
$sh.Save()

Get-Process WeChat* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Start-Process (Join-Path $WxDir "wechat_starter.exe")

Write-Host ""
Write-Host "WeChat:" $WeChatExe
Write-Host "Version:" (Get-Item $WeChatExe).VersionInfo.FileVersion
Write-Host ""
$ver = (Get-Item $WeChatExe).VersionInfo.FileVersion
if ($ver -ne "3.9.12.51") {
    Write-Host "WARN: WeChat $ver installed; wcferry 39.5.2 expects 3.9.12.51 — hook may fail."
    Write-Host "      Install: D:\GIT\data\wechat_install\WeChatSetup-3.9.12.51.exe"
}
Write-Host "Use ONLY: desktop WeChat-LiMa.lnk  or  $Bat"
Write-Host "Do NOT use the normal green WeChat shortcut."
Write-Host "Then scan QR on phone to login."
