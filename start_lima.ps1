Write-Host 'LiMa Code Launcher' -ForegroundColor Cyan
Write-Host ''

if (-not $env:LIMA_API_KEY -and -not $env:LIMA_CODE_API_KEY) {
    throw 'LIMA_API_KEY or LIMA_CODE_API_KEY environment variable is required'
}
if (-not $env:LIMA_API_KEY) {
    $env:LIMA_API_KEY = $env:LIMA_CODE_API_KEY
}
if (-not $env:LIMA_CODE_API_KEY) {
    $env:LIMA_CODE_API_KEY = $env:LIMA_API_KEY
}
$env:LIMA_CODE_SERVER_URL = 'https://chat.donglicao.com'
$env:LIMA_FORCE_TTY = '1'

# Set console window size
$prompt = $Host.UI.RawUI
$size = $prompt.WindowSize
$size.Width = 140
$size.Height = 60
$prompt.WindowSize = $size

Set-Location 'D:\GIT'
Write-Host 'CWD:' (Get-Location) -ForegroundColor Green
Write-Host 'Terminal: 140x60' -ForegroundColor Green
Write-Host ''

$tsxPath = 'D:\GIT\deepcode-cli\node_modules\tsx\dist\cli.mjs'
$cliPath = 'D:\GIT\deepcode-cli\src\cli.tsx'
& node $tsxPath $cliPath

Write-Host ''
Write-Host 'Press any key to close...'
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
