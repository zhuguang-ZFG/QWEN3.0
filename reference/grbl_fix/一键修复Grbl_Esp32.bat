@echo off
chcp 65001 >nul
title Grbl_Esp32 代码审查修复
echo Applying fixes to D:\Users\Grbl_Esp32 ...
python "%~dp0apply_grbl_fixes.py"
if exist "%~dp0tmp\grbl_fix_report.txt" (
  echo.
  echo ===== REPORT =====
  type "%~dp0tmp\grbl_fix_report.txt"
)
echo.
pause
