# Local OpenClaw light validation (Windows). VPS 1.8GB may OOM; use this to verify config first.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$State = Join-Path $env:USERPROFILE ".openclaw-lima-light"
$CfgDir = Join-Path $Root "deploy\openclaw"
New-Item -ItemType Directory -Force -Path $State | Out-Null
Copy-Item (Join-Path $CfgDir "openclaw.light.json5") (Join-Path $State "openclaw.json") -Force
$env:OPENCLAW_STATE_DIR = $State
$env:OPENCLAW_CONFIG_PATH = Join-Path $State "openclaw.json"
if (-not $env:LIMA_API_KEY) { Write-Warning "Set LIMA_API_KEY before start" }
if (-not $env:OPENCLAW_GATEWAY_TOKEN) { $env:OPENCLAW_GATEWAY_TOKEN = "local-dev-token" }
Write-Host "State: $State"
Write-Host "Install plugin once: npx -y openclaw@2026.5.22 plugins install @tencent-weixin/openclaw-weixin"
Write-Host "WeChat login: openclaw channels login --channel openclaw-weixin"
npx -y openclaw@2026.5.22 gateway run --bind loopback --port 18789
