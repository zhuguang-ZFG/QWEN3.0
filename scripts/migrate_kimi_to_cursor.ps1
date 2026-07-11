# Migrate useful Kimi Code CLI config (MCP + skills + hooks) into Cursor.
# Idempotent: skips entries/skills that already exist.
# Usage: pwsh -File scripts/migrate_kimi_to_cursor.ps1

$ErrorActionPreference = "Stop"

$KimiRoot = Join-Path $env:USERPROFILE ".kimi-code"
$CursorRoot = Join-Path $env:USERPROFILE ".cursor"
$CursorMcp = Join-Path $CursorRoot "mcp.json"
$CursorHooks = Join-Path $CursorRoot "hooks.json"
$CursorSkills = Join-Path $CursorRoot "skills"
$BackupDir = Join-Path $CursorRoot "backups"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path $KimiRoot)) {
    Write-Error "Kimi config not found: $KimiRoot"
}

New-Item -ItemType Directory -Force -Path $BackupDir, $CursorSkills | Out-Null

function Backup-File([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $name = Split-Path $Path -Leaf
    Copy-Item -Force $Path (Join-Path $BackupDir "$name.$Stamp.bak")
}

function Copy-SkillDir([string]$Source, [string]$DestName) {
    if (-not (Test-Path $Source)) {
        Write-Host "  skip skill (missing): $DestName" -ForegroundColor DarkYellow
        return
    }
    $dest = Join-Path $CursorSkills $DestName
    if (Test-Path $dest) {
        Write-Host "  skip skill (exists): $DestName" -ForegroundColor DarkGray
        return
    }
    Copy-Item -Recurse -Force $Source $dest
    Write-Host "  + skill: $DestName" -ForegroundColor Green
}

function Strip-McpEntry([object]$Entry) {
    $allowed = @("command", "args", "env", "type", "url", "headers")
    $out = [ordered]@{}
    foreach ($key in $allowed) {
        if ($null -ne $Entry.PSObject.Properties[$key]) {
            $out[$key] = $Entry.$key
        }
    }
  # Cursor uses type=http for remote MCP; Kimi uses transport=sse
    if ($Entry.transport -eq "sse" -and $Entry.url) {
        $out["url"] = $Entry.url
    }
    return [pscustomobject]$out
}

Write-Host "=== Kimi -> Cursor migration ($Stamp) ===" -ForegroundColor Cyan

# --- MCP ---
$kimiMcpPath = Join-Path $KimiRoot "mcp.json"
if (-not (Test-Path $kimiMcpPath)) {
    Write-Error "Missing $kimiMcpPath"
}

$toMerge = @(
    "platformio",      # ESP32 / PlatformIO
    "headroom",        # context headroom
    "code-rag",        # local semantic code RAG
    "kimi-mneme",      # session memory (complements agentmemory)
    "context-mode",    # context compression / KB
    "agent-inspect",   # subagent session inspection
    "linux-do",        # LINUX DO community search
    "a2a-bridge"       # A2A subagent delegation (SSE daemon on :41242)
)

$skipMcp = @{
    "catpaw-subagent"    = "disabled local proxy; superseded by a2a-bridge"
    "codegraph"        = "use lima-codegraph / project CodeGraph instead"
    "esp-idf-tools"      = "disabled until IDF mcp feature installed"
    "stackoverflow"      = "disabled in Kimi; use agentkey WebSearch"
    "fetch"              = "Cursor already has fetch-mcp"
    "filesystem"         = "Cursor filesystem scoped to project (safer)"
    "orchestrator"       = "retired with LiteLLM proxy; use Cursor subagents / a2a-bridge sparingly"
    "kimi-code"          = "optional; needs kimi CLI login; high token in Cursor — enable only for 256K deep dives"
    "gitnexus"           = "forbidden in DLC repo; use lima-codegraph"
}

Backup-File $CursorMcp
$kimiJson = Get-Content -Raw -Encoding UTF8 $kimiMcpPath | ConvertFrom-Json
$cursorJson = if (Test-Path $CursorMcp) {
    Get-Content -Raw -Encoding UTF8 $CursorMcp | ConvertFrom-Json
} else {
    [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
}
if (-not $cursorJson.mcpServers) {
    $cursorJson | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
}

Write-Host "`n[MCP merge]" -ForegroundColor Yellow
foreach ($name in $toMerge) {
    if ($cursorJson.mcpServers.PSObject.Properties.Name -contains $name) {
        Write-Host "  skip mcp (exists): $name" -ForegroundColor DarkGray
        continue
    }
    if (-not $kimiJson.mcpServers.PSObject.Properties.Name -contains $name) {
        Write-Host "  skip mcp (not in Kimi): $name" -ForegroundColor DarkYellow
        continue
    }
    $entry = $kimiJson.mcpServers.$name
    if ($entry.enabled -eq $false) {
        Write-Host "  skip mcp (disabled in Kimi): $name" -ForegroundColor DarkYellow
        continue
    }
    $cursorJson.mcpServers | Add-Member -NotePropertyName $name -NotePropertyValue (Strip-McpEntry $entry) -Force
    Write-Host "  + mcp: $name" -ForegroundColor Green
}

foreach ($name in $skipMcp.Keys) {
    if ($kimiJson.mcpServers.PSObject.Properties.Name -contains $name) {
        Write-Host "  ~ skip by design: $name — $($skipMcp[$name])" -ForegroundColor DarkGray
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($CursorMcp, ($cursorJson | ConvertTo-Json -Depth 12), $utf8NoBom)

# --- Skills ---
Write-Host "`n[Skills copy]" -ForegroundColor Yellow

# Universal Embedded Workbench (12 skills) — high ROI for ESP32/固件
$uewSkills = Join-Path $KimiRoot "plugins\universal-embedded-workbench\skills"
if (Test-Path $uewSkills) {
    Get-ChildItem $uewSkills -Directory | ForEach-Object {
        Copy-SkillDir $_.FullName $_.Name
    }
}

# Kimi user skills
@(
    "ultrawork",
    "clarify-first",
    "delegated-coding",
    "requirements-elicitation",
    "review",
    "insights"
) | ForEach-Object {
    Copy-SkillDir (Join-Path $KimiRoot "skills\$_") $_
}

# taste-skill bundle (flatten main design skills)
$tasteRoot = Join-Path $KimiRoot "skills\taste-skill\skills"
if (Test-Path $tasteRoot) {
    Get-ChildItem $tasteRoot -Directory | ForEach-Object {
        Copy-SkillDir $_.FullName $_.Name
    }
}

# OMK skills — instruction-only in Cursor (hooks not portable)
@("omk-navigation", "omk-ralph", "omk-review") | ForEach-Object {
    Copy-SkillDir (Join-Path $KimiRoot "skills\$_") $_
}

# --- Hooks: block dangerous shell ---
Write-Host "`n[Hooks]" -ForegroundColor Yellow
$blockHook = Join-Path $KimiRoot "hooks\block-dangerous-bash.mjs"
if (Test-Path $blockHook) {
    Backup-File $CursorHooks
    $hooks = if (Test-Path $CursorHooks) {
        Get-Content -Raw -Encoding UTF8 $CursorHooks | ConvertFrom-Json
    } else {
        [pscustomobject]@{ version = 1; hooks = [pscustomobject]@{} }
    }
    if (-not $hooks.hooks) {
        $hooks | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    if (-not $hooks.hooks.preToolUse) {
        $hooks.hooks | Add-Member -NotePropertyName preToolUse -NotePropertyValue @() -Force
    }
    $hookCmd = "node `"$($blockHook -replace '\\','\\')`""
    $already = $hooks.hooks.preToolUse | Where-Object { $_.command -like "*block-dangerous-bash*" }
    if ($already) {
        Write-Host "  skip hook (exists): block-dangerous-bash" -ForegroundColor DarkGray
    } else {
        $hooks.hooks.preToolUse = @(
            [pscustomobject]@{ command = $hookCmd; matcher = "Shell" }
        ) + @($hooks.hooks.preToolUse)
        [System.IO.File]::WriteAllText($CursorHooks, ($hooks | ConvertTo-Json -Depth 12), $utf8NoBom)
        Write-Host "  + hook: block-dangerous-bash (preToolUse/Shell)" -ForegroundColor Green
    }
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host "Backups: $BackupDir\*.$Stamp.bak"
Write-Host "Reload Cursor MCP: Settings -> MCP -> refresh (or restart Cursor)"
Write-Host "Tip: run scripts/cursor_mcp_tiers.ps1 -Tier lean after merge"
Write-Host "Note: LiteLLM proxy retired — archive with scripts/archive_litellm_proxy.ps1 if still on disk"
Write-Host "Note: omk-* skills need oh-my-kimicli hooks — partial in Cursor (instructions only)"
