$Root = Split-Path $PSScriptRoot -Parent
$PidFile = Join-Path $Root "data\weixin_lima_bridge.pid"
Get-Process -Name hermes* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*hermes_weixin_lima_bridge*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
Write-Host "LiMa Weixin bridge stopped."
