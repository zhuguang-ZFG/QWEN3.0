# Install flupkede/codesearch for PE-B-1 (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install_codesearch_local.ps1

$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\codesearch"
$ZipPath = Join-Path $env:TEMP "codesearch-windows-x86_64.zip"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host "fetching latest release..."
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/flupkede/codesearch/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -eq "codesearch-windows-x86_64.zip" } | Select-Object -First 1
    $downloadUrl = $asset.browser_download_url
} catch {
    Write-Host "api fallback: using pinned release v1.0.97"
    $downloadUrl = "https://github.com/flupkede/codesearch/releases/download/v1.0.97/codesearch-windows-x86_64.zip"
}
if (-not $downloadUrl) { throw "codesearch-windows-x86_64.zip download URL not resolved" }

Invoke-WebRequest -Uri $downloadUrl -OutFile $ZipPath
Expand-Archive -Path $ZipPath -DestinationPath $InstallDir -Force
Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue

$exe = Get-ChildItem -Path $InstallDir -Recurse -Filter "codesearch.exe" | Select-Object -First 1
if (-not $exe) { throw "codesearch.exe not found after extract" }

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$dir = $exe.DirectoryName
if ($userPath -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    $env:Path = "$env:Path;$dir"
}

Write-Host "installed=$($exe.FullName)"
& $exe.FullName --version 2>&1
Write-Host "next: codesearch index add D:\GIT --alias lima-git"
