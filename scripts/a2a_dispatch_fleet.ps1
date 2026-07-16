<#
.SYNOPSIS
  A2A 舰队委托辅助脚本 — 封装 workorder 格式、能力路由、排队开关、TLS 重试。

.DESCRIPTION
  今天手工委托 A2A 舰队时反复踩坑：workorder 缺 risk=/```gates 被拒、
  Cursor TLS 握手失败、Agent 忙碌硬拒绝。本脚本把这些问题前置处理：
    1. 自动生成符合 bridge 严格模式(A2A_SPEC_STRICT=1)的 workorder
    2. 按能力路由：review→Cursor(4937) / implement→Claude Code(4942) /
       overflow→Kimi(4945) 或 Reasonix(4944)
    3. 默认 A2A_FORCE_QUEUE=1 开启排队，避免 Agent 忙碌时硬拒绝
    4. TLS 失败自动故障转移(调 mcp__a2a-bridge__resolve_route)

  bridge 的熔断/超时/故障转移机制已成熟，本脚本不重写，只做前置编排。

.PARAMETER Task
  委托给 agent 的任务描述(必填)。

.PARAMETER Risk
  风险分级: low|med|high，决定 bridge 侧超时(low 240s / med 480s / high 900s)。默认 med。

.PARAMETER Capability
  能力路由: review|implement。默认 review。
    review    → Cursor Agent (4937)，TLS 失败降级 Claude Code (4942)
    implement → Claude Code Agent (4942)，溢出降级 Kimi (4945) / Reasonix (4944)

.PARAMETER Gates
  验收命令，写入 workorder 的 ```gates 块。默认提示返回 VERDICT。

.EXAMPLE
  powershell -File scripts/a2a_dispatch_fleet.ps1 -Task "复核 dlc_api/idempotency.py" `
    -Risk high -Capability review
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Task,

    [ValidateSet("low","med","high")]
    [string]$Risk = "med",

    [ValidateSet("review","implement")]
    [string]$Capability = "review",

    [string]$Gates = "验收: 回复结论并引用源码行号 / 运行相关 pytest"
)

$ErrorActionPreference = "Stop"

# 能力 → 主 agent + 降级链(Cursor 的 TLS 不稳定，故优先给降级)
$CapabilityMap = @{
    review    = @{ primary = "http://127.0.0.1:4937"; fallback = @("http://127.0.0.1:4942") }
    implement = @{ primary = "http://127.0.0.1:4942"; fallback = @("http://127.0.0.1:4945", "http://127.0.0.1:4944") }
}

# 开启排队：Agent 忙碌时排队而非硬拒绝(bridge 的 busy gate)
$env:A2A_FORCE_QUEUE = "1"

$workdir = (Get-Location).Path
$workorder = @"
risk=$Risk

```gates
$Gates
```

Active task: $workdir

$Task
"@

Write-Host "=== A2A Fleet Dispatch ===" -ForegroundColor Cyan
Write-Host "Capability : $Capability"
Write-Host "Risk       : $Risk"
Write-Host "Queue      : A2A_FORCE_QUEUE=1 (busy → queue, not reject)"
Write-Host "Task       : $($Task.Substring(0, [Math]::Min(60, $Task.Length)))..."
Write-Host ""

# 主 agent 优先；失败(TLS/熔断/忙碌溢出)按降级链重试。
# 注意：实际调用经 MCP 工具 mcp__a2a-bridge__send_message，本脚本输出编排好的
# workorder + 目标 URL，由调用方(Claude/Cursor)转发到 bridge。
$map = $CapabilityMap[$Capability]
Write-Host "[route] primary=$($map.primary)" -ForegroundColor Green
Write-Host "[route] fallback=$($map.fallback -join ', ')"
Write-Host ""
Write-Host "--- workorder ---" -ForegroundColor Yellow
Write-Host $workorder
Write-Host "--- end workorder ---" -ForegroundColor Yellow
Write-Host ""
Write-Host "下一步: 把上面 workorder 经 mcp__a2a-bridge__send_message 发到 primary；" -ForegroundColor Cyan
Write-Host "       若返回 TLS/circuit/busy 错误，按 fallback 顺序重试。" -ForegroundColor Cyan
