@echo off
chcp 65001 >nul
echo Phase 3: WebSettings + paper_system + security + build
python D:\QWEN3.0\apply_grbl_phase3_ordered.py
echo.
echo Report: D:\QWEN3.0\tmp\grbl_phase3_report.txt
pause
