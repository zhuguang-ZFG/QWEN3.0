# Register LiMa FRP tunnel as a Windows Scheduled Task (TG-GH-1).
# Run once as Administrator:
#   powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\install_frpc_service.ps1

param(
    [string]$TaskName = "LiMa-FRP-Tunnel",
    [string]$FrpcExe = "D:\GIT\frp\frpc.exe",
    [string]$FrpcConfig = "D:\GIT\frp\frpc.toml",
    [string]$LogDir = "D:\ollama_server"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $FrpcExe)) {
    Write-Error "frpc not found: $FrpcExe"
}
if (-not (Test-Path $FrpcConfig)) {
    Write-Error "frpc config not found: $FrpcConfig"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Runner = Join-Path $PSScriptRoot "run_frpc_tunnel.ps1"
@'
param(
    [string]$FrpcExe = "D:\GIT\frp\frpc.exe",
    [string]$FrpcConfig = "D:\GIT\frp\frpc.toml",
    [string]$Log = "D:\ollama_server\frpc.log"
)
$running = Get-Process -Name frpc -ErrorAction SilentlyContinue
if ($running) { exit 0 }
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $Log -Value "[$ts] starting frpc"
Start-Process -FilePath $FrpcExe -ArgumentList @("-c", $FrpcConfig) -WindowStyle Minimized
'@ | Set-Content -Path $Runner -Encoding UTF8

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$TriggerBoot = New-ScheduledTaskTrigger -AtStartup
$TriggerBoot.Delay = "PT1M"
$TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration ([TimeSpan]::MaxValue)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerBoot, $TriggerRepeat) `
    -Settings $Settings -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Runner: $Runner"
Write-Host "Test: Start-ScheduledTask -TaskName $TaskName"
