# Bridge dlc_mcp/server.py to XiaoZhi official/self-hosted MCP WebSocket endpoint.
# Prerequisites (set in shell or .env, never commit tokens):
#   $env:MCP_ENDPOINT = 'wss://api.xiaozhi.me/mcp/?token=...'
#   $env:DLC_API_URL = 'http://127.0.0.1:8081'
#   $env:DLC_API_TOKEN = '<device bearer token>'

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not $env:MCP_ENDPOINT) {
    Write-Error "MCP_ENDPOINT is required (xiaozhi.me console -> MCP endpoint URL)"
}

$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$env:PYTHONPATH" } else { $Root }
$py = Join-Path $Root ".venv310\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Bridging dlc_mcp -> $env:MCP_ENDPOINT" -ForegroundColor Cyan
& $py (Join-Path $Root "dlc_mcp\mcp_pipe.py") @args
