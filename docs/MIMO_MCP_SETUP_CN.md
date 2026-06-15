# MiMo MCP（全局 + Agent 模式）

> 更新：2026-06-16 v0.2
> **任意 git 仓库**可用；通过 MiMo compose skills（review / verify / plan / tdd）发挥 Agent 架构优势。

## 架构

```
Cursor Agent
    → lima-mimo-mcp (stdio MCP)
        → mimo run --dir <workspace> --trust -f review-brief.md
        → compose skill 提示（review / verify / plan / security / tdd）
        → MiMo 自带 MCP（CodeGraph、agentkey 等）在 MiMo 进程内使用
    → .omc/artifacts/mimo-mcp/findings.json
```

与旧版区别：

| 项 | v0.1（仓库内） | v0.2（全局） |
|----|----------------|--------------|
| 工作区 | 固定 `D:\QWEN3.0` | `MIMO_MCP_WORKSPACE` / `${workspaceFolder}` / git root |
| brief/merge | 依赖 `.claude/skills/lima-multi-cli` | 内置 `lima_mcp_stdio/multi_cli/` |
| MiMo 调用 | 纯文本 prompt | **模式化 prompt** + `-f` 附件 + `--trust` |
| 安装 | 项目 `.mcp.json` | `pip install -e .` + 用户 `~/.cursor/mcp.json` |

## 一键全局安装（Windows）

```powershell
cd D:\QWEN3.0
pwsh -File scripts/install_mimo_mcp_global.ps1
```

然后 **Cursor → Reload Window**。

手动安装：

```powershell
python -m pip install -e D:\QWEN3.0
# 或仅依赖：python -m pip install -r requirements_mcp_stdio.txt
```

将 [`mcp.json.example`](../mcp.json.example) 合并到 `%USERPROFILE%\.cursor\mcp.json`：

```json
"lima-mimo": {
  "command": "lima-mimo-mcp",
  "args": [],
  "env": {
    "MIMO_MCP_WORKSPACE": "${workspaceFolder}",
    "LIMA_TIMEOUT": "180"
  }
}
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `MIMO_MCP_WORKSPACE` | 工作区根（Cursor 用 `${workspaceFolder}`） |
| `MIMO_MCP_ARTIFACT_DIR` | 产物目录（默认 `<workspace>/.omc/artifacts/mimo-mcp`） |
| `MIMO_MCP_AGENT` | 覆盖 `mimo run --agent`（如 `build`） |
| `MIMO_MCP_MODEL` | 覆盖 `mimo run -m provider/model` |
| `MIMO_MCP_SKIP_PERMISSIONS` | `1` 时加 `--dangerously-skip-permissions`（仅本机信任环境） |
| `LIMA_TIMEOUT` / `MIMO_MCP_TIMEOUT` | 超时秒数，默认 180 |

## MCP 工具

| 工具 | 阻塞 | 用途 |
|------|------|------|
| **`lima_mimo_review_async`** | 否 | **推荐**：后台审查，返回 `job_id` |
| **`lima_mimo_job_status`** | 否 | 轮询任务（`job_id` 空=最新） |
| `lima_mimo_poll` | 否 | last_done + findings + 最新 job |
| `lima_mimo_status` | 否 | CLI / workspace / modes |
| `lima_mimo_agents` | 否 | 模式列表 |
| `lima_mimo_review` | 是 | 同步审查（仅当必须等待） |
| `lima_mimo_verify` | 是 | 修复后 delta |
| `lima_mimo_plan` | 是 | 只读计划 |
| `lima_mimo_run` | 是 | 通用入口 |

## 并行工作流（Agent 自动）

规则：`.cursor/rules/mimo-async-review.mdc`

1. 改完热路径 → `lima_mimo_review_async`
2. 继续实现 / pytest
3. closeout 前 → `lima_mimo_job_status`
4. 产物：`.omc/artifacts/mimo-mcp/jobs/<job_id>/status.json`

## 发挥 MiMo Agent 优势的建议

1. **在 MiMo 内配置 MCP**（`mimo mcp list`）：CodeGraph、agentkey 等 — MCP 调 MiMo，MiMo 再调自己的工具链。
2. **审查用 `review`，修完用 `verify`** — 对应 compose verify skill 工作流。
3. **大改用 `plan` 再实现** — Cursor 主改，MiMo 只出计划与测试清单。
4. **设 `MIMO_MCP_AGENT=build`** 若你使用 MiMo 主 agent 配置。

## 测试

```powershell
python -m pytest tests/test_mimo_mcp_runner.py tests/test_mimo_mcp_jobs.py -q
```

## 相关

- 包入口：`pyproject.toml` → console script `lima-mimo-mcp`
- 实现：`lima_mcp_stdio/`
- LiMa 批处理仍可用：`.claude/skills/lima-multi-cli/driver.py`
