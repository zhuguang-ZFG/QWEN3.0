# Move low-ROI global Cursor rules (impeccable language packs) to rules-archive.
# Keeps ponytail + QWEN3.0 stack (Python/FastAPI, Vue/TS for 小程序).
# Usage: powershell -File scripts/cursor_archive_global_rules.ps1

$ErrorActionPreference = "Stop"

$RulesRoot = Join-Path $env:USERPROFILE ".cursor\rules"
$ArchiveRoot = Join-Path $env:USERPROFILE ".cursor\rules-archive"
$BackupStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Manifest = Join-Path $ArchiveRoot "KEEP_MANIFEST.txt"

$Keep = @(
    "ponytail.mdc",
    "ecc-workflow.mdc",
    "karpathy-guidelines.mdc",
    "orchestrator.mdc",
    "interactive-feedback-mcp.mdc",
    "memory-persistence\claude-mem-context.mdc",
    "common-git-workflow.mdc",
    "python-coding-style.mdc",
    "python-fastapi.mdc",
    "python-hooks.mdc",
    "python-patterns.mdc",
    "python-security.mdc",
    "python-testing.mdc",
    "vue-coding-style.mdc",
    "vue-hooks.mdc",
    "vue-patterns.mdc",
    "vue-security.mdc",
    "vue-testing.mdc",
    "typescript-coding-style.mdc",
    "typescript-hooks.mdc",
    "typescript-patterns.mdc",
    "typescript-security.mdc",
    "typescript-testing.mdc"
)

New-Item -ItemType Directory -Force -Path $ArchiveRoot, $RulesRoot | Out-Null
$Keep | Set-Content -Encoding UTF8 $Manifest

$moved = @()
$kept = @()
foreach ($f in Get-ChildItem $RulesRoot -Filter "*.mdc" -Recurse) {
    $rel = $f.FullName.Substring($RulesRoot.Length).TrimStart('\', '/')
    if ($Keep -contains $rel) {
        $kept += $rel
        continue
    }
    $dest = Join-Path $ArchiveRoot $rel
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
    if (Test-Path $dest) { Remove-Item -Force $dest }
    Move-Item -Force $f.FullName $dest
    $moved += $rel
}

Write-Host "=== Global Cursor rules archive ===" -ForegroundColor Cyan
Write-Host "Kept ($($kept.Count)):" -ForegroundColor Green
$kept | ForEach-Object { Write-Host "  $_" }
Write-Host "Archived ($($moved.Count)) -> $ArchiveRoot" -ForegroundColor Yellow
Write-Host "Manifest: $Manifest"
Write-Host "Restore: Move-Item `$env:USERPROFILE\.cursor\rules-archive\<name> `$env:USERPROFILE\.cursor\rules\"
