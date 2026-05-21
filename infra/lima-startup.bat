@echo off
:: LiMa 本地服务自启动脚本
:: 放入 Windows 启动目录: shell:startup
:: 管理的服务: Ollama, DuckAI, TheOldLLM proxy

echo [%date% %time%] LiMa services starting... >> D:\ollama_server\startup.log

:: 等待网络就绪
timeout /t 10 /nobreak > nul

:: 1. Ollama (如果没在运行)
tasklist /FI "IMAGENAME eq ollama.exe" | find "ollama.exe" > nul
if errorlevel 1 (
    start /min "" "C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama app.exe"
    echo [%date% %time%] Ollama started >> D:\ollama_server\startup.log
) else (
    echo [%date% %time%] Ollama already running >> D:\ollama_server\startup.log
)

:: 等待 Ollama 就绪
timeout /t 5 /nobreak > nul

:: 2. DuckAI (bun, port 4500)
tasklist /FI "IMAGENAME eq bun.exe" | find "bun.exe" > nul
if errorlevel 1 (
    cd /d D:\DuckDuckGo-AI
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && bun run start > D:\ollama_server\duckai.log 2>&1"
    echo [%date% %time%] DuckAI started >> D:\ollama_server\startup.log
) else (
    echo [%date% %time%] DuckAI already running >> D:\ollama_server\startup.log
)

:: 3. TheOldLLM proxy (node, port 4502)
netstat -ano | find "4502" | find "LISTENING" > nul
if errorlevel 1 (
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && node D:\ollama_server\oldllm_proxy.js > D:\ollama_server\oldllm_proxy.log 2>&1"
    echo [%date% %time%] TheOldLLM proxy started >> D:\ollama_server\startup.log
) else (
    echo [%date% %time%] TheOldLLM proxy already running >> D:\ollama_server\startup.log
)

:: 4. g4f API server (python, port 4503)
netstat -ano | find "4503" | find "LISTENING" > nul
if errorlevel 1 (
    start /min "" cmd /c "set HTTP_PROXY=http://127.0.0.1:7897 && set HTTPS_PROXY=http://127.0.0.1:7897 && set ALL_PROXY=http://127.0.0.1:7897 && python D:\ollama_server\g4f_server.py > D:\ollama_server\g4f.log 2>&1"
    echo [%date% %time%] g4f started >> D:\ollama_server\startup.log
) else (
    echo [%date% %time%] g4f already running >> D:\ollama_server\startup.log
)

echo [%date% %time%] All services started. >> D:\ollama_server\startup.log
