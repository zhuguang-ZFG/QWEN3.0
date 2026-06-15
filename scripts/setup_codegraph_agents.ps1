# Install CodeGraph MCP across local AI agents (Windows).
# Prerequisite: codegraph on PATH (codegraph --version)
# Usage: pwsh -File scripts/setup_codegraph_agents.ps1

$ErrorActionPreference = "Stop"

function Add-CodegraphMcpJson {
    param([string]$Path, [hashtable]$Server)
    if (-not (Test-Path $Path)) { return "skip-missing" }
    $raw = Get-Content -Raw -Encoding UTF8 $Path
    $json = $raw | ConvertFrom-Json
    if ($json.mcpServers) {
        $json.mcpServers | Add-Member -NotePropertyName codegraph -NotePropertyValue $Server -Force
    } elseif ($json.servers) {
        $json.servers | Add-Member -NotePropertyName codegraph -NotePropertyValue $Server -Force
    } elseif ($json.mcp) {
        $json.mcp | Add-Member -NotePropertyName codegraph -NotePropertyValue @{
            type    = "local"
            command = @("codegraph", "serve", "--mcp")
            enabled = $true
        } -Force
    } else {
        return "skip-unknown-schema"
    }
    $json | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $Path
    return "ok"
}

$stdioCursor = @{
    type    = "stdio"
    command = "codegraph"
    args    = @("serve", "--mcp", "--path", '${workspaceFolder}')
}
$stdioPlain = @{
    command = "codegraph"
    args    = @("serve", "--mcp")
}

$targets = @(
    @{ Name = "cursor"; Path = "$env:USERPROFILE\.cursor\mcp.json"; Server = $stdioCursor },
    @{ Name = "vscode-kilo"; Path = "$env:APPDATA\Code\User\mcp.json"; Server = $stdioCursor },
    @{ Name = "kimi-code"; Path = "$env:APPDATA\kimi-desktop\daimon-share\daimon\runtime\kimi-code\home\mcp.json"; Server = $stdioPlain },
    @{ Name = "qoder"; Path = "$env:APPDATA\Qoder\SharedClientCache\mcp.json"; Server = $stdioPlain },
    @{ Name = "qodercn"; Path = "$env:APPDATA\QoderCN\SharedClientCache\mcp.json"; Server = $stdioPlain },
    @{ Name = "qoderworkcn"; Path = "$env:USERPROFILE\.qoderworkcn\mcp.json"; Server = $stdioPlain }
)

Write-Host "=== CodeGraph agent MCP setup ===" -ForegroundColor Cyan
if (-not (Get-Command codegraph -ErrorAction SilentlyContinue)) {
    Write-Error "codegraph not on PATH. Install from https://github.com/clauxel/codegraph-context-mcp or your package manager."
}

Write-Host "Running: codegraph install -y --location global --target auto" -ForegroundColor Yellow
& codegraph install -y --location global --target auto

foreach ($t in $targets) {
    $r = Add-CodegraphMcpJson -Path $t.Path -Server $t.Server
    Write-Host ("{0,-14} {1,-12} {2}" -f $t.Name, $t.Path, $r)
}

Write-Host ""
Write-Host "Manual / already configured:" -ForegroundColor Green
Write-Host "  claude  -> ~/.claude.json (codegraph) — use: codegraph install --print-config claude"
Write-Host "  codex   -> ~/.codex/config.toml — [mcp_servers.codegraph]"
Write-Host "  mimo    -> inherits ~/.claude.json — run: mimo mcp list (approve codegraph in UI)"
Write-Host "  kilo    -> VS Code User mcp.json (Kilo Code extension)"
Write-Host "  zcode   -> not on PATH; if using Qoder/QoderCN, see AppData/Qoder*/SharedClientCache/mcp.json"
Write-Host ""
Write-Host "Per-project index:" -ForegroundColor Green
Write-Host "  cd D:\QWEN3.0 && codegraph index ."
Write-Host "  codegraph sync .   # after file changes"
