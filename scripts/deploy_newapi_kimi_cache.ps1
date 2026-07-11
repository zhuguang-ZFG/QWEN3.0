# Push Kimi-cache tune assets to JDCloud and run tune_newapi_kimi_cache.sh
# Usage: pwsh -File scripts/deploy_newapi_kimi_cache.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

$Host_ = $env:LIMA_JDCLOUD_SERVER
if (-not $Host_) { $Host_ = "117.72.118.95" }
$Key = $env:LIMA_DEPLOY_KEY_PATH
if (-not $Key) { $Key = "$env:USERPROFILE\.ssh\id_ed25519" }

$sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=20")
if (Test-Path $Key) { $sshArgs += @("-i", $Key) }

$files = @(
    "deploy\jdcloud\tune_newapi_kimi_cache.sh",
    "deploy\jdcloud\docker-compose.newapi-claude.yml"
)

Write-Host "=== Deploy NewAPI Kimi cache tune -> $Host_ ===" -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Repo $rel
    $remote = "/tmp/$(Split-Path $rel -Leaf)"
    scp @sshArgs $local "root@${Host_}:${remote}"
}

ssh @sshArgs "root@$Host_" "chmod +x /tmp/tune_newapi_kimi_cache.sh && bash /tmp/tune_newapi_kimi_cache.sh"
Write-Host "=== Done. Verify: python scripts/check_newapi_cache_health.py ===" -ForegroundColor Green
