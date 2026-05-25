# Single-instance LiMa Weixin bridge: stop duplicates, SSH tunnel, background bridge + log.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$vpsHost = if ($env:LIMA_VPS_HOST) { $env:LIMA_VPS_HOST } else { "47.112.162.80" }
$key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }
$PidFile = Join-Path $Root "data\weixin_lima_bridge.pid"
$LogFile = Join-Path $Root "data\weixin_lima_bridge.log"
$BridgePy = Join-Path $Root "scripts\hermes_weixin_lima_bridge.py"

New-Item -ItemType Directory -Force -Path (Split-Path $PidFile) | Out-Null

function Get-BridgeProcs {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*hermes_weixin_lima_bridge*" }
}

function Stop-AllBridges {
    Get-Process -Name hermes* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-BridgeProcs | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
}

function Test-Port8080 {
    try {
        return (Test-NetConnection -ComputerName 127.0.0.1 -Port 8080 -WarningAction SilentlyContinue).TcpTestSucceeded
    } catch { return $false }
}

Write-Host "=== LiMa Weixin bridge (single instance) ==="

# 1) Clean stale / duplicate bridges
$existing = @(Get-BridgeProcs)
if ($existing.Count -gt 0) {
    Write-Host "Stopping $($existing.Count) existing bridge process(es)..."
    Stop-AllBridges
    Start-Sleep 2
}

# 2) SSH tunnel to VPS channel (8080)
if (-not (Test-Port8080)) {
    Write-Host "Starting SSH tunnel 127.0.0.1:8080 -> ${vpsHost}..."
    Start-Process ssh -ArgumentList @("-N", "-L", "8080:127.0.0.1:8080", "-i", $key, "root@$vpsHost") -WindowStyle Hidden
    Start-Sleep 4
    if (-not (Test-Port8080)) {
        throw "Tunnel 8080 not listening. Check SSH key and VPS."
    }
}
Write-Host "Tunnel OK (127.0.0.1:8080)"

# 3) Start one bridge in background
$env:LIMA_CHANNEL_BASE_URL = "http://127.0.0.1:8080"
$proc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", "python `"$BridgePy`" >> `"$LogFile`" 2>&1") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru
$proc.Id | Set-Content -Path $PidFile -Encoding ASCII
Start-Sleep 3

if ($proc.HasExited) {
    Write-Host "Bridge exited. Log:"
    Get-Content $LogFile -Tail 20 -ErrorAction SilentlyContinue
    throw "Bridge failed to start"
}

$again = @(Get-BridgeProcs)
Write-Host "Bridge running PID=$($proc.Id) (python processes: $($again.Count))"
Write-Host "Log: $LogFile"
Write-Host "Send WeChat DM: 你好  or  /help"
Write-Host "Stop: Stop-Process -Id $($proc.Id); Remove-Item '$PidFile'"
