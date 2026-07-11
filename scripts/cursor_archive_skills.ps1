# Move low-ROI Cursor skills to skills-archive to shrink the agent skill list (token savings).
# Idempotent: only moves dirs that exist under ~/.cursor/skills.
# Usage: powershell -File scripts/cursor_archive_skills.ps1

$ErrorActionPreference = "Stop"

$SkillsRoot = Join-Path $env:USERPROFILE ".cursor\skills"
$ArchiveRoot = Join-Path $env:USERPROFILE ".cursor\skills-archive"
$Manifest = Join-Path $ArchiveRoot "KEEP_MANIFEST.txt"

$Keep = @(
    # ponytail
    "ponytail", "ponytail-audit", "ponytail-debt", "ponytail-gain", "ponytail-help", "ponytail-review",
    # embedded / ESP32
    "esp-idf-handling", "esp-pio-handling", "esp32-test-harness",
    "fsd-writer", "signal-generator", "test-designer",
    "workbench-ble", "workbench-debug", "workbench-integration", "workbench-logging",
    "workbench-mqtt", "workbench-test-handling", "workbench-wifi",
    # workflow
    "debugging", "review", "ultrawork", "tdd-workflow", "verification-loop"
)

New-Item -ItemType Directory -Force -Path $ArchiveRoot, $SkillsRoot | Out-Null
$Keep | Set-Content -Encoding UTF8 $Manifest

$moved = @()
$skipped = @()
foreach ($dir in Get-ChildItem $SkillsRoot -Directory) {
    if ($Keep -contains $dir.Name) {
        $skipped += $dir.Name
        continue
    }
    $dest = Join-Path $ArchiveRoot $dir.Name
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Move-Item -Force $dir.FullName $dest
    $moved += $dir.Name
}

Write-Host "=== Cursor skills archive ===" -ForegroundColor Cyan
Write-Host "Kept ($($skipped.Count)): $($skipped -join ', ')"
Write-Host "Archived ($($moved.Count)) -> $ArchiveRoot"
if ($moved.Count -gt 0) {
    Write-Host ($moved -join ", ") -ForegroundColor Yellow
}
Write-Host "Manifest: $Manifest"
