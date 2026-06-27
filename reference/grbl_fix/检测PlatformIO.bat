@echo off
chcp 65001 >nul
echo === PlatformIO 环境检测 ===
echo.

set P=%USERPROFILE%\.platformio\penv\Scripts\pio.exe
if exist "%P%" (
  echo [FOUND] %P%
  "%P%" --version
) else (
  echo [MISS]  %P%
)

set P=%USERPROFILE%\.platformio\penv\Scripts\python.exe
if exist "%P%" (
  echo [FOUND] %P%
  "%P%" --version
) else (
  echo [MISS]  %P%
)

echo.
echo --- where pio ---
where pio 2>nul
echo.
echo --- pio --version (可能因 Python312 已删而失败) ---
pio --version 2>&1
echo.
echo --- py -0p ---
py -0p 2>nul
echo.
echo --- py -m pip show platformio ---
py -m pip show platformio 2>&1
echo.
pause
