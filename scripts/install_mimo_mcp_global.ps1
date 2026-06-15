#Requires -Version 5.1
<#
.SYNOPSIS
  Install lima-mimo-mcp globally and register in Cursor user MCP config.

.DESCRIPTION
  - pip install -e from repo root (or pip install lima-mimo-mcp when published)
  - Merges "lima-mimo" into %USERPROFILE%\.cursor\mcp.json
  - Does NOT overwrite other servers; backs up existing mcp.json

.EXAMPLE
  pwsh -File scripts/install_mimo_mcp_global.ps1
#>
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$CursorMcp = (Join-Path $env:USERPROFILE ".cursor\mcp.json"),
    [switch]$SkipPip
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

if (-not $SkipPip) {
    Write-Step "pip install -e $RepoRoot"
    python -m pip install -e $RepoRoot
}

$which = Get-Command lima-mimo-mcp -ErrorAction SilentlyContinue
if (-not $which) {
    throw "lima-mimo-mcp not on PATH after install. Re-open shell or check pip Scripts path."
}

Write-Step "Register Cursor MCP at $CursorMcp"
$dir = Split-Path $CursorMcp -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

$entry = @{
    command = "python"
    args    = @("-m", "lima_mcp_stdio")
    env     = @{
        MIMO_MCP_WORKSPACE        = '${workspaceFolder}'
        LIMA_TIMEOUT              = "300"
        MIMO_MCP_SKIP_PERMISSIONS = "1"
    }
}

if (Test-Path $CursorMcp) {
    $backup = "$CursorMcp.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $CursorMcp $backup
    Write-Step "Backup: $backup"
    $json = Get-Content $CursorMcp -Raw | ConvertFrom-Json
} else {
    $json = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
}

if (-not $json.mcpServers) {
    $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}

$servers = @{}
if ($json.mcpServers -is [pscustomobject]) {
    $json.mcpServers.PSObject.Properties | ForEach-Object { $servers[$_.Name] = $_.Value }
}
$servers["lima-mimo"] = $entry
$out = [ordered]@{ mcpServers = $servers }
($out | ConvertTo-Json -Depth 6) | Set-Content -Path $CursorMcp -Encoding UTF8

Write-Step "Done. Reload Cursor window. Tools: lima_mimo_status, lima_mimo_review, lima_mimo_verify, lima_mimo_plan, lima_mimo_run"
Write-Host "Optional: MIMO_MCP_AGENT=build  MIMO_MCP_SKIP_PERMISSIONS=1 (dangerous)" -ForegroundColor Yellow
