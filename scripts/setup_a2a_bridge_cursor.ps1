# Wire local A2A bridge (GongRzhe/A2A-MCP-Server fork) into Cursor MCP.
# Prerequisite: ~/.kimi-code/mcp-a2a-bridge with start-a2a-bridge.ps1
# Upstream: https://github.com/GongRzhe/A2A-MCP-Server
# Usage: powershell -File scripts/setup_a2a_bridge_cursor.ps1

$ErrorActionPreference = "Stop"

$BridgeDir = Join-Path $env:USERPROFILE ".kimi-code\mcp-a2a-bridge"
$StartScript = Join-Path $BridgeDir "start-a2a-bridge.ps1"
$CursorMcp = Join-Path $env:USERPROFILE ".cursor\mcp.json"
$McpUrl = "http://127.0.0.1:41242/mcp"

if (-not (Test-Path $StartScript)) {
    Write-Error "A2A bridge not found. Clone/install to $BridgeDir first (see GongRzhe/A2A-MCP-Server)."
}

Write-Host "=== A2A Bridge -> Cursor ===" -ForegroundColor Cyan

# 1. Ensure daemon + streamable-http MCP are up
& powershell -NoProfile -ExecutionPolicy Bypass -File $StartScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2. Merge Cursor MCP entry (streamable-http -> persistent local server)
if (-not (Test-Path $CursorMcp)) {
    $json = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
} else {
    $json = Get-Content -Raw -Encoding UTF8 $CursorMcp | ConvertFrom-Json
}
if (-not $json.mcpServers) {
    $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
}

$entry = [pscustomobject]@{ type = "streamable-http"; url = $McpUrl }
$json.mcpServers | Add-Member -NotePropertyName "a2a-bridge" -NotePropertyValue $entry -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($CursorMcp, ($json | ConvertTo-Json -Depth 12), $utf8NoBom)
Write-Host "Cursor MCP: a2a-bridge -> $McpUrl" -ForegroundColor Green

Write-Host ""
Write-Host "Registered local agents (A2A):" -ForegroundColor Yellow
Write-Host "  :4937 Cursor Agent   :4938 CodeBuddy   :4939 MiMo   :4940 AtomCode"
Write-Host "Key tool: delegate_task — auto-routes to best agent with fallback"
Write-Host "Reload Cursor MCP (Settings -> MCP -> refresh)"
