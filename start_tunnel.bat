@echo off
echo === red V1flash Tunnel Startup ===
echo.

REM 1. Start server in background
start "red-v1-server" /MIN D:\GIT\venv\Scripts\python.exe D:\GIT\server.py
echo [OK] Server starting on port 8080...

REM 2. Wait for server
timeout /t 3 /nobreak >/dev/null

REM 3. Start ngrok
echo [OK] Starting ngrok tunnel...
start "red-v1-ngrok" /MIN D:\Users\Administrator\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe http 8080

REM 4. Wait and show URL
timeout /t 3 /nobreak >/dev/null
echo.
echo === Fetching public URL... ===
curl -s http://localhost:4040/api/tunnels > %TEMP%\ngrok_url.json 2>/dev/null
python -c "import json; data=json.load(open('%TEMP%\ngrok_url.json')); [print(f'Public URL: {t[\"public_url\"]}') for t in data.get('tunnels',[])]" 2>/dev/null

echo.
echo === Copy this URL to cc-switch ===
echo Base URL: THE_URL_ABOVE/v1
echo Model: red-v1flash
echo.
pause
