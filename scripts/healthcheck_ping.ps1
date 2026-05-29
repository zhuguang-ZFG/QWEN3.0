# Healthchecks.io ping wrapper (INF-B)
param(
    [string]$PingUrl = "",
    [string]$EnvKey = "HEALTHCHECK_LIMA_VPS_URL",
    [string]$Check = "",
    [switch]$Force,
    [switch]$DryRun
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Args = @("scripts/healthcheck_ping.py")
if ($PingUrl) { $Args += @("--ping-url", $PingUrl) }
if ($EnvKey) { $Args += @("--env-key", $EnvKey) }
if ($Check) { $Args += @("--check", $Check) }
if ($Force) { $Args += "--force" }
if ($DryRun) { $Args += "--dry-run" }

& python @Args
exit $LASTEXITCODE
