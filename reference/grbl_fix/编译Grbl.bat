@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d D:\Users\Grbl_Esp32
set PLATFORMIO_BUILD_FLAGS=-DMACHINE_FILENAME=test_drive.h

echo === Grbl_Esp32 build ===
echo PLATFORMIO_BUILD_FLAGS=%PLATFORMIO_BUILD_FLAGS%
echo.

REM 1) PlatformIO Core 自带虚拟环境（VS Code 扩展 / 独立安装）
set PIO_CORE=%USERPROFILE%\.platformio\penv\Scripts\pio.exe
if exist "%PIO_CORE%" (
  echo [OK] Using PlatformIO Core: %PIO_CORE%
  "%PIO_CORE%" --version
  "%PIO_CORE%" run -v
  set EC=!ERRORLEVEL!
  goto :finish
)

REM 2) 用 Core 自带 python 模块方式
set PY_CORE=%USERPROFILE%\.platformio\penv\Scripts\python.exe
if exist "%PY_CORE%" (
  echo [OK] Using: %PY_CORE% -m platformio
  "%PY_CORE%" -m platformio --version
  "%PY_CORE%" -m platformio run -v
  set EC=!ERRORLEVEL!
  goto :finish
)

REM 3) 当前 py launcher 安装 platformio（Python 3.14）
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [TRY] py -m pip install -U platformio
  py -m pip install -U platformio
  if !ERRORLEVEL!==0 (
    echo [OK] py -m platformio run
    py -m platformio run -v
    set EC=!ERRORLEVEL!
    goto :finish
  )
)

echo.
echo [FAIL] 未找到可用的 PlatformIO。
echo.
echo 你的 PATH 里 pio 指向已删除的 Python 3.12，需要修复工具链：
echo   方案 A - 安装 PlatformIO Core（推荐）:
echo     https://platformio.org/install/cli
echo   方案 B - 给当前 Python 安装 platformio:
echo     py -m pip install -U platformio
echo     py -m platformio run -v
echo   方案 C - 若已装 VS Code PlatformIO 扩展，先打开一次 VS Code 让 .platformio 初始化
echo.
set EC=1

:finish
echo.
echo BUILD exit_code=!EC!
exit /b !EC!
