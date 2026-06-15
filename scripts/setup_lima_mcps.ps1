# Install high-ROI MCP servers for LiMa (sourced from ModelScope MCP Plaza developer-tools).
# Prerequisite: Node.js (npx), uv (uvx), optional gh CLI for GitHub token.
# Usage: pwsh -File scripts/setup_lima_mcps.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataDir = Join-Path $RepoRoot "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

function Merge-McpServers {
    param(
        [string]$Path,
        [hashtable]$Servers
    )
    if (-not (Test-Path $Path)) { return "skip-missing" }
    $raw = Get-Content -Raw -Encoding UTF8 $Path
    $json = $raw | ConvertFrom-Json
    if (-not $json.mcpServers) {
        $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    foreach ($name in $Servers.Keys) {
        $json.mcpServers | Add-Member -NotePropertyName $name -NotePropertyValue $Servers[$name] -Force
    }
    $text = $json | ConvertTo-Json -Depth 12
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $text, $utf8NoBom)
    return "ok"
}

$sessionDb = (Join-Path $DataDir "lima_sessions.db") -replace "\\", "/"
$outcomeDb = (Join-Path $DataDir "outcome_ledger.db") -replace "\\", "/"

$servers = [ordered]@{
  # Context7: FastAPI/httpx/pytest/redis docs — use "use context7" in prompts
  context7 = [pscustomobject]@{
    command = "npx"
    args    = @("-y", "@upstash/context7-mcp@latest")
  }
  # Official fetch: lightweight URL → markdown (complements agentkey for docs/API pages)
  fetch = [pscustomobject]@{
    command = "uvx"
    args    = @("mcp-server-fetch")
  }
  # SQLite: session_memory / outcome_ledger local debugging
  "sqlite-sessions" = [pscustomobject]@{
    command = "uvx"
    args    = @("mcp-server-sqlite", "--db-path", $sessionDb)
  }
  "sqlite-outcomes" = [pscustomobject]@{
    command = "uvx"
    args    = @("mcp-server-sqlite", "--db-path", $outcomeDb)
  }
  # Redis: device task queue inspection (docker compose / VPS FRP tunnel)
  "redis-lima" = [pscustomobject]@{
    command = "npx"
    args    = @("-y", "@modelcontextprotocol/server-redis", "redis://127.0.0.1:6379/0")
  }
}

if (Get-Command gh -ErrorAction SilentlyContinue) {
    $ghToken = (& gh auth token 2>$null)
    if ($ghToken) {
        $servers["github"] = [pscustomobject]@{
            command = "npx"
            args    = @("-y", "@modelcontextprotocol/server-github")
            env     = [pscustomobject]@{ GITHUB_PERSONAL_ACCESS_TOKEN = $ghToken.Trim() }
        }
    }
}

if ($env:MODELSCOPE_API_TOKEN) {
    $servers["modelscope"] = [pscustomobject]@{
        command = "uvx"
        args    = @("modelscope-mcp-server")
        env     = [pscustomobject]@{ MODELSCOPE_API_TOKEN = $env:MODELSCOPE_API_TOKEN }
    }
}

Write-Host "=== LiMa MCP setup (ModelScope Plaza picks) ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Installing: $($servers.Keys -join ', ')"

$cursorPath = Join-Path $env:USERPROFILE ".cursor\mcp.json"
$projectPath = Join-Path $RepoRoot ".mcp.json"

$r1 = Merge-McpServers -Path $cursorPath -Servers $servers
Write-Host ("cursor global  {0,-40} {1}" -f $cursorPath, $r1)

# Project .mcp.json: subset without secrets (codegraph + fetch + context7)
$projectSubset = [ordered]@{}
$projectSubset["codegraph"] = [pscustomobject]@{
    command = "codegraph"
    args    = @("serve", "--mcp")
}
foreach ($k in @("context7", "fetch")) {
    if ($servers.Contains($k)) { $projectSubset[$k] = $servers[$k] }
}
$r2 = Merge-McpServers -Path $projectPath -Servers $projectSubset
Write-Host ("project .mcp  {0,-40} {1}" -f $projectPath, $r2)

Write-Host ""
Write-Host "Warm-up (first run may download packages):" -ForegroundColor Yellow
$warmups = @(
    @{ c = "uvx"; a = @("mcp-server-fetch", "--help") },
    @{ c = "npx"; a = @("-y", "@upstash/context7-mcp@latest", "--version") }
)
foreach ($cmd in $warmups) {
    $exe = $cmd.c
    $args = $cmd.a
    try {
        $null = & $exe @args 2>&1
    } catch {
        # uvx/npx may write download progress to stderr; ignore warm-up noise
    }
    Write-Host ("  warmed {0} {1}" -f $exe, ($args -join " "))
}

Write-Host ""
Write-Host "Manual follow-up:" -ForegroundColor Green
if (-not $servers.Contains("github")) {
    Write-Host "  github: run 'gh auth login' then re-run this script"
}
if (-not $servers.Contains("modelscope")) {
    Write-Host "  modelscope: set MODELSCOPE_API_TOKEN (https://modelscope.cn/docs/accounts/token) then re-run"
}
Write-Host "  redis-lima: needs Redis on 127.0.0.1:6379 (docker compose / LIMA_DEVICE_REDIS_URL)"
Write-Host "  sqlite-*: DB files created on first server use; session_memory uses data/lima_sessions.db"
Write-Host "  Cursor: reload MCP (Settings -> MCP -> refresh) after this script"
