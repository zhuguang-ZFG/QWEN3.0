# Fix "version too low": must use 32-bit WeChat 3.9.12.x + __COMPAT_LAYER on 64-bit Windows.
# 64-bit WeChat 3.9.x (in Program Files) is blocked by Tencent — compat starter cannot fix that.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Dir = Join-Path $Root "data\wechat_install"
. (Join-Path $PSScriptRoot "lib\WeChat-Arch.ps1")

function Get-ExeMachine($path) {
    $b = [IO.File]::ReadAllBytes($path)
    $pe = [BitConverter]::ToInt32($b, 0x3c)
    return [BitConverter]::ToUInt16($b, $pe + 4)
}

function Test-WeChat32($path) {
    (Get-ExeMachine $path) -eq 0x014c
}

$paths = @(
    "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
    "${env:ProgramFiles}\Tencent\WeChat\WeChat.exe"
)
foreach ($p in $paths) {
    if (-not (Test-Path $p)) { continue }
    $m = Get-ExeMachine $p
    $label = if ($m -eq 0x014c) { "OK 32-bit" } else { "BAD 64-bit (causes version-too-low)" }
    Write-Host "$label : $p"
    if ($m -eq 0x8664) {
        Write-Host ""
        Write-Host ">>> Uninstall this 64-bit WeChat 3.9 from Settings, or delete the folder after quit."
        Write-Host ">>> Then install 32-bit package (see below)."
    }
}

$target86 = "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe"
if ((Test-Path $target86) -and (Test-WeChat32 $target86)) {
    Write-Host ""
    Write-Host "32-bit WeChat already at $target86 — running fix_wechat_login.ps1"
    & (Join-Path $PSScriptRoot "fix_wechat_login.ps1")
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== Install 32-bit WeChat (official x86; WCF .51 installer may lay down 64-bit exe on Win11) ==="
$setup = Join-Path $Dir "WeChatSetup_x86.exe"
if (-not (Test-Path $setup) -or ((Get-Item $setup).Length -lt 50MB)) {
    Write-Host "Downloading WeChatSetup_x86.exe..."
    curl.exe -L --retry 3 -o $setup "https://dldir1v6.qq.com/weixin/Windows/WeChatSetup_x86.exe"
}
$wcfSetup = Join-Path $Dir "WeChatSetup-3.9.12.51.exe"
if (Test-Path $wcfSetup) {
    $instPe = Get-PeMachineType $wcfSetup
    Write-Host "WCF package installer PE: 0x$("{0:X}" -f $instPe) (installed WeChat.exe must still be 32-bit)"
}

Get-Process WeChat*, Weixin* -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 2

Write-Host "Opening 32-bit installer. Choose path: Program Files (x86)\Tencent\WeChat if asked."
Write-Host "After install, run: powershell -File D:\GIT\scripts\fix_wechat_login.ps1"
Start-Process $setup -Wait

if (-not (Test-Path $target86)) {
    throw "32-bit WeChat not found at $target86 after install"
}
if (-not (Test-WeChat32 $target86)) {
    throw "Installed WeChat is still 64-bit. Uninstall and retry 32-bit setup only."
}

& (Join-Path $PSScriptRoot "fix_wechat_login.ps1")
