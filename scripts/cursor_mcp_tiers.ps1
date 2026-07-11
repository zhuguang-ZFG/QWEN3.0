# Cursor MCP tier profiles — fewer servers = smaller tool schema = better cache stability + lower tokens.
# Usage:
#   powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean
#   powershell -File scripts/cursor_mcp_tiers.ps1 -Tier default
#   powershell -File scripts/cursor_mcp_tiers.ps1 -Tier full
# Then: Cursor Settings -> MCP -> Refresh

param(
    [ValidateSet("lean", "default", "full")]
    [string]$Tier = "lean"
)

$ErrorActionPreference = "Stop"
$McpPath = Join-Path $env:USERPROFILE ".cursor\mcp.json"
$BackupDir = Join-Path $env:USERPROFILE ".cursor\backups"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path $McpPath)) { Write-Error "Missing $McpPath" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
Copy-Item -Force $McpPath (Join-Path $BackupDir "mcp.json.$Stamp.bak")

$json = Get-Content -Raw -Encoding UTF8 $McpPath | ConvertFrom-Json
$all = @($json.mcpServers.PSObject.Properties.Name)

# lean: daily DLC work — global servers only (project .cursor/mcp.json adds lima-codegraph)
$lean = @(
    "filesystem",
    "context7",
    "agentkey",
    "github"
)

# Moved to project .cursor/mcp.json (repo root): lima-codegraph, platformio (optional, see mcp.json.example)
# agentmemory: enable manually in default/full or add back for cross-session memory

# default: lean + delegation + browser + ops
$default = $lean + @(
    "playwright",
    "a2a-bridge",
    "fetch-mcp",
    "lima-ops",
    "limaguard",
    "headroom",
    "prompt-compress"
)

$enabled = switch ($Tier) {
    "lean" { $lean }
    "default" { $default }
    "full" { $all }
}

$removed = @()
foreach ($name in $all) {
    if ($enabled -contains $name) { continue }
    $json.mcpServers.PSObject.Properties.Remove($name)
    $removed += $name
}

$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($McpPath, ($json | ConvertTo-Json -Depth 12), $utf8)

Write-Host "=== Cursor MCP tier: $Tier ===" -ForegroundColor Cyan
Write-Host "Enabled ($($enabled.Count)): $($enabled -join ', ')"
if ($removed.Count) {
    Write-Host "Removed ($($removed.Count)): $($removed -join ', ')" -ForegroundColor Yellow
}
Write-Host "Backup: $BackupDir\mcp.json.$Stamp.bak"
Write-Host "Reload Cursor MCP (Settings -> MCP -> refresh)"
