@echo off
if not defined LIMA_API_KEY if not defined LIMA_CODE_API_KEY (
  echo LIMA_API_KEY or LIMA_CODE_API_KEY environment variable is required.
  exit /b 1
)
if not defined LIMA_API_KEY set "LIMA_API_KEY=%LIMA_CODE_API_KEY%"
if not defined LIMA_CODE_API_KEY set "LIMA_CODE_API_KEY=%LIMA_API_KEY%"
set "LIMA_CODE_SERVER_URL=https://chat.donglicao.com"
start "LiMa Code" cmd /k "cd /d D:\GIT && node D:\GIT\deepcode-cli\node_modules\tsx\dist\cli.mjs D:\GIT\deepcode-cli\src\cli.tsx"
