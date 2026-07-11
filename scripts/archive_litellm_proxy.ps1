# Archive and optionally remove ~/.whetstone/litellm-proxy (retired 2026-07-10).
# Kimi Code CLI now uses managed:kimi-code + newapi/100xlabs direct providers; Cursor uses Pro.
# Usage:
#   pwsh -File scripts/archive_litellm_proxy.ps1
#   pwsh -File scripts/archive_litellm_proxy.ps1 -RemoveAfterArchive

param(
    [switch]$RemoveAfterArchive
)

$ErrorActionPreference = "Stop"
$ProxyDir = Join-Path $env:USERPROFILE ".whetstone\litellm-proxy"
$ArchiveRoot = Join-Path $env:USERPROFILE ".whetstone"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ArchiveZip = Join-Path $ArchiveRoot "litellm-proxy-archive-$Stamp.zip"

if (-not (Test-Path $ProxyDir)) {
    Write-Host "SKIP: LiteLLM proxy not found at $ProxyDir" -ForegroundColor Yellow
    exit 0
}

$stopScript = Join-Path $ProxyDir "stop-proxy.ps1"
if (Test-Path $stopScript) {
    Write-Host "Stopping LiteLLM proxy..." -ForegroundColor Cyan
    & $stopScript
}

$unregister = Join-Path $ProxyDir "tools\unregister-health-monitor-task.ps1"
if (Test-Path $unregister) {
    Write-Host "Unregistering health-monitor scheduled task (if any)..." -ForegroundColor Cyan
    & $unregister 2>$null
}

Write-Host "Archiving $ProxyDir -> $ArchiveZip" -ForegroundColor Cyan
if (Test-Path $ArchiveZip) { Remove-Item -Force $ArchiveZip }
Compress-Archive -Path $ProxyDir -DestinationPath $ArchiveZip -CompressionLevel Optimal

$sizeMb = [math]::Round((Get-Item $ArchiveZip).Length / 1MB, 1)
Write-Host "Archive OK ($sizeMb MB): $ArchiveZip" -ForegroundColor Green

if ($RemoveAfterArchive) {
    Remove-Item -Recurse -Force $ProxyDir
    Write-Host "Removed: $ProxyDir" -ForegroundColor Green
} else {
    Write-Host "Source kept. Re-run with -RemoveAfterArchive to delete after verifying the zip." -ForegroundColor Yellow
}

Write-Host "Next: apply lean MCP tier if needed:" -ForegroundColor DarkGray
Write-Host "  pwsh -File scripts/cursor_mcp_tiers.ps1 -Tier lean"
