@echo off
title LiMa Local Router + FRP
cd /d D:\GIT

echo [%date% %time%] Starting LiMa Local Router...
start /b "" "D:\GIT\venv\Scripts\python.exe" "D:\GIT\local_router.py"

timeout /t 10 /nobreak >nul

echo [%date% %time%] Starting FRP tunnel...
start /b "" "D:\GIT\frp\frpc.exe" -c "D:\GIT\frp\frpc.toml"

echo [%date% %time%] All services started.
echo   Local Router: http://localhost:8090/health
echo   FRP tunnel: local:8090 -^> cloud:9090
pause
