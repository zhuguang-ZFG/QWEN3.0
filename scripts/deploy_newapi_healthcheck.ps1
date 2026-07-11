# Deploy NewAPI lightweight healthcheck cron to JDCloud (no Claude chat).
# Optional: $env:NEWAPI_HC_PING_UUID = "<healthchecks.io uuid>"
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python scripts/deploy_newapi_healthcheck.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
