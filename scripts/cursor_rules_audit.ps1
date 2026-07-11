# Audit Cursor rules token budget + alwaysApply count (GitHub/nedcodes style).
# Usage: powershell -File scripts/cursor_rules_audit.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$ProjectRules = Join-Path $RepoRoot ".cursor\rules"
$GlobalRules = Join-Path $env:USERPROFILE ".cursor\rules"
$ProjectMcp = Join-Path $RepoRoot ".cursor\mcp.json"
$GlobalMcp = Join-Path $env:USERPROFILE ".cursor\mcp.json"

function Measure-Rules($dir, $label) {
    if (-not (Test-Path $dir)) {
        Write-Host "[$label] (missing) $dir" -ForegroundColor Yellow
        return
    }
    $files = Get-ChildItem $dir -Filter "*.mdc" -ErrorAction SilentlyContinue
    $always = @()
    $totalLines = 0
    foreach ($f in $files) {
        $lines = (Get-Content $f.FullName).Count
        $totalLines += $lines
        $raw = Get-Content $f.FullName -Raw
        if ($raw -match 'alwaysApply:\s*true') {
            $always += [PSCustomObject]@{ Name = $f.Name; Lines = $lines }
        }
    }
    $alwaysLines = ($always | Measure-Object -Property Lines -Sum).Sum
    if (-not $alwaysLines) { $alwaysLines = 0 }
    $estAlwaysTokens = [int]($alwaysLines * 4)
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    Write-Host "Rules: $($files.Count) files, $totalLines lines total"
    Write-Host "alwaysApply: $($always.Count) files, $alwaysLines lines (~$estAlwaysTokens tokens @ 4/line)"
    foreach ($a in $always) {
        Write-Host "  - $($a.Name) ($($a.Lines) lines)" -ForegroundColor $(if ($a.Lines -gt 80) { "Yellow" } else { "Green" })
    }
    if ($estAlwaysTokens -gt 2000) {
        Write-Host "WARN: alwaysApply budget > 2000 tokens (nedcodes / Morph guideline)" -ForegroundColor Red
    }
    $broad = $files | Where-Object {
        $c = Get-Content $_.FullName -Raw
        $c -match 'QWEN3\.0\\\*\\\*' -or ($c -match 'globs:.*\*\*/\*' -and $c -notmatch 'alwaysApply:\s*false')
    }
    if ($broad) {
        Write-Host "WARN: broad globs (may over-inject):" -ForegroundColor Yellow
        $broad | ForEach-Object { Write-Host "  - $($_.Name)" }
    }
}

function Count-Mcp($path, $label) {
    if (-not (Test-Path $path)) {
        Write-Host "[$label] (missing)" -ForegroundColor Yellow
        return 0
    }
    $j = Get-Content $path -Raw | ConvertFrom-Json
    $n = @($j.mcpServers.PSObject.Properties.Name).Count
    Write-Host "$label MCP servers: $n ($($j.mcpServers.PSObject.Properties.Name -join ', '))"
    return $n
}

Measure-Rules (Resolve-Path $ProjectRules) "Project ($ProjectRules)"
Measure-Rules $GlobalRules "Global (~/.cursor/rules)"

$pg = Count-Mcp (Resolve-Path $GlobalMcp) "Global"
$pp = Count-Mcp (Resolve-Path $ProjectMcp) "Project"
$total = $pg + $pp
Write-Host "`nCombined MCP (global+project): $total" -ForegroundColor $(if ($total -le 8) { "Green" } else { "Yellow" })
if ($total -gt 8) {
    Write-Host "TIP: lean target <= 8; use cursor_mcp_tiers.ps1 -Tier lean" -ForegroundColor Yellow
}

Write-Host "`nRefs: docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md §7"
