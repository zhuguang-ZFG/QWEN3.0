# Qwen2API 环境变量配置
# 使用方法: . .\set_qwen_env.ps1

$env:OPENAI_API_KEY = "sk-qwen-local-2026"
$env:OPENAI_BASE_URL = "http://localhost:7862/v1"

Write-Host "Qwen2API environment configured:" -ForegroundColor Green
Write-Host "  Base URL: $env:OPENAI_BASE_URL"
$keyPreview = if ($env:OPENAI_API_KEY.Length -gt 20) { $env:OPENAI_API_KEY.Substring(0,20) } else { $env:OPENAI_API_KEY }
Write-Host "  API Key: $keyPreview..."
Write-Host ""
Write-Host "Now you can run: mimo" -ForegroundColor Yellow
