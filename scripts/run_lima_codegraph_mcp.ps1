# Run lima-codegraph MCP with repo root on PYTHONPATH (project .cursor/mcp.json)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root
& python (Join-Path $Root "lima_mcp_stdio\lima_codegraph_mcp.py") @args
