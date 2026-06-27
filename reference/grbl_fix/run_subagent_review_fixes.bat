@echo off
chcp 65001 >nul
setlocal
cd /d D:\QWEN3.0
echo Running subagent review fixes + build...
.\.venv310\Scripts\python.exe .\tmp\apply_review_fixes_subagent.py
set EC=%ERRORLEVEL%
if exist .\tmp\subagent_review_fix_report.txt type .\tmp\subagent_review_fix_report.txt
exit /b %EC%
