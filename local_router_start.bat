@echo off
title LiMa API Router + FRP
cd /d D:\GIT

set LOG=D:\ollama_server\local_router.log
set PYTHON=D:\GIT\venv\Scripts\python.exe
set APP=D:\GIT\server.py

if not defined LIMA_API_KEY if not defined LIMA_API_KEYS (
    set LIMA_API_KEY=lima-local
    set LIMA_API_KEYS=lima-local
)
if defined LIMA_API_KEY if not defined LIMA_API_KEYS set LIMA_API_KEYS=%LIMA_API_KEY%

echo [%date% %time%] Starting LiMa API Router... >> %LOG%
netstat -ano | find "8080" | find "LISTENING" >nul
if errorlevel 1 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\ollama_server\start-lima-api.ps1"
) else (
    echo [%date% %time%] LiMa API Router already listening on 8080. >> %LOG%
)

ping 127.0.0.1 -n 11 >nul

echo [%date% %time%] Starting FRP tunnel... >> %LOG%
tasklist /FI "IMAGENAME eq frpc.exe" | find "frpc.exe" >nul
if errorlevel 1 (
    start /min "" "D:\GIT\frp\frpc.exe" -c "D:\GIT\frp\frpc.toml"
) else (
    echo [%date% %time%] FRP already running. >> %LOG%
)

echo [%date% %time%] All services checked. >> %LOG%
echo   Local API: http://localhost:8080/health
echo   FRP tunnel: local:8080 -^> cloud:8088
