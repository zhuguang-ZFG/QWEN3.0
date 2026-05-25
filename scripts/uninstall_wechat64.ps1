# Remove wrong 64-bit WeChat 3.9 under Program Files (keeps Weixin 4.x).
$ErrorActionPreference = "Stop"
$bad = "C:\Program Files\Tencent\WeChat"
. (Join-Path $PSScriptRoot "lib\WeChat-Arch.ps1")
Get-Process WeChat* -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 2
if (-not (Test-Path "$bad\WeChat.exe")) {
    Write-Host "No $bad\WeChat.exe — run: powershell -File D:\GIT\scripts\fix_wechat_version_low.ps1"
    exit 0
}
$m = Get-PeMachineType "$bad\WeChat.exe"
if ($m -eq 0x8664) {
    Write-Host "Removing 64-bit WeChat at $bad"
    Remove-Item $bad -Recurse -Force
    Write-Host "Done. Now run: powershell -File D:\GIT\scripts\fix_wechat_version_low.ps1"
} else {
    Write-Host "WeChat.exe is already 32-bit; no removal needed."
}
