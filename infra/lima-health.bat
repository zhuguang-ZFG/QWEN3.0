@echo off
:: LiMa 健康监控 + 自动恢复脚本
:: 由 Task Scheduler 每 5 分钟执行一次
:: 检测服务存活，挂了自动重启

setlocal enabledelayedexpansion
set LOG=D:\ollama_server\health.log

:: 1. 检查 Ollama (port 11434)
curl -s --max-time 5 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: Ollama down, restarting... >> %LOG%
    start /min "" "C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama app.exe"
    timeout /t 5 /nobreak >nul
) else (
    echo [%date% %time%] OK: Ollama >> %LOG%
)

:: 2. 检查 DuckAI (port 4500)
curl -s --max-time 5 http://localhost:4500/v1/models >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: DuckAI down, restarting... >> %LOG%
    cd /d D:\DuckDuckGo-AI
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && bun run start > D:\ollama_server\duckai.log 2>&1"
    timeout /t 3 /nobreak >nul
) else (
    echo [%date% %time%] OK: DuckAI >> %LOG%
)

:: 3. 检查 TheOldLLM proxy (port 4502)
curl -s --max-time 5 http://localhost:4502/v1/models >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: TheOldLLM down, restarting... >> %LOG%
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && node D:\ollama_server\oldllm_proxy.js > D:\ollama_server\oldllm_proxy.log 2>&1"
    timeout /t 3 /nobreak >nul
) else (
    echo [%date% %time%] OK: TheOldLLM >> %LOG%
)

:: 4. 检查 Cloudflare Tunnel
sc query cloudflared | find "RUNNING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: Cloudflared down, restarting... >> %LOG%
    net start cloudflared >nul 2>&1
) else (
    echo [%date% %time%] OK: Cloudflared >> %LOG%
)

:: 5. 检查 g4f (port 4503)
curl -s --max-time 5 http://localhost:4503/v1/models >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: g4f down, restarting... >> %LOG%
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && set ALL_PROXY=http://127.0.0.1:7897 && python D:\ollama_server\g4f_server.py > D:\ollama_server\g4f.log 2>&1"
    timeout /t 5 /nobreak >nul
) else (
    echo [%date% %time%] OK: g4f >> %LOG%
)

:: 6. 检查代理 (port 7897)
curl -s --max-time 5 --proxy http://127.0.0.1:7897 https://www.google.com >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] CRIT: Proxy 7897 down! Cannot auto-fix. >> %LOG%
) else (
    echo [%date% %time%] OK: Proxy 7897 >> %LOG%
)

:: 7. 检查 FRP 隧道 (frpc.exe)
tasklist /FI "IMAGENAME eq frpc.exe" | find "frpc.exe" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: frpc down, restarting... >> %LOG%
    start /min "" "D:\GIT\frp\frpc.exe" -c "D:\GIT\frp\frpc.toml"
) else (
    echo [%date% %time%] OK: frpc >> %LOG%
)

:: 8. Healthchecks.io dead-man ping (INF-B, optional)
if /I "%LIMA_HEALTHCHECK_ENABLED%"=="1" (
    python D:\GIT\scripts\healthcheck_ping.py --env-key HEALTHCHECK_LIMA_WINDOWS_URL --check http://127.0.0.1:8080/health >> %LOG% 2>&1
    if errorlevel 1 (
        echo [%date% %time%] WARN: Healthchecks ping failed >> %LOG%
    ) else (
        echo [%date% %time%] OK: Healthchecks ping >> %LOG%
    )
)

endlocal
