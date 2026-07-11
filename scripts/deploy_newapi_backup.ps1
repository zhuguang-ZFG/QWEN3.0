# Deploy NewAPI SQLite daily backup to JDCloud and install cron.
# Usage: pwsh -File scripts/deploy_newapi_backup.ps1
# Password: LIMA_JDCLOUD_SSH_PASS or D:\Downloads\VPS.txt

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$py = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "=== Deploy NewAPI backup ===" -ForegroundColor Cyan
& $py (Join-Path $Repo "scripts\deploy_newapi_backup.py")
if ($LASTEXITCODE -ne 0) { throw "deploy backup failed: $LASTEXITCODE" }
Write-Host "=== Backup cron installed (03:13 daily, keep 14d) ===" -ForegroundColor Green
