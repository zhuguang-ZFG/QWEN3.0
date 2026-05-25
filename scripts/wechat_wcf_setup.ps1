# Windows 真机微信 -> LiMa (WeChatFerry path)
# Run in PowerShell from D:\GIT

$ErrorActionPreference = "Stop"
$Vps = if ($env:LIMA_VPS_HOST) { $env:LIMA_VPS_HOST } else { "47.112.162.80" }
$Key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }

Write-Host "=== 1. Install wcferry ==="
pip install wcferry -q

Write-Host "=== 2. Fetch VPS sidecar token (masked) ==="
$tok = ssh -i $Key root@$Vps "grep '^LIMA_WECHAT_SIDECAR_TOKEN=' /opt/lima-router/.env | cut -d= -f2-"
if (-not $tok) { throw "missing LIMA_WECHAT_SIDECAR_TOKEN on VPS" }
$env:LIMA_WECHAT_SIDECAR_TOKEN = $tok.Trim()
$env:LIMA_CHANNEL_BASE_URL = "http://127.0.0.1:8080"
Write-Host "sidecar token loaded (len=$($tok.Length))"

Write-Host @"

=== 3. 你需要手动完成（一次性）===
  a) 安装匹配版微信 PC 客户端（wcferry 文档要求，常见 3.9.11.x）
     https://github.com/lich0821/WeChatFerry/releases
  b) 登录微信（建议小号）
  c) 另开终端保持 SSH 隧道:
     ssh -N -L 8080:127.0.0.1:8080 -i $Key root@$Vps

=== 4. 启动桥接（本窗口）===
"@

Set-Location $PSScriptRoot\..
python -m wechat_bridge.wcf_lima_bridge
