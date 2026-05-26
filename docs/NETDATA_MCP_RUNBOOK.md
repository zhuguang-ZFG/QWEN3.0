# Netdata MCP Runbook (PE-C-1)

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** LiMa VPS (`47.112.162.80`) — **只读**运维诊断；**不改** LiMa 路由。

## 目标

在 VPS 安装 Netdata Agent（v2.6+），启用本地 MCP endpoint，供 Operator / LiMa Code 通过 MCP 查询 CPU、内存、磁盘、网络等指标。

## 架构

```text
Cursor / Claude Code (本地)
  → MCP (HTTP/SSE 或 mcp-remote bridge)
  → VPS 127.0.0.1:19999/mcp
  → Netdata Agent（本机指标）

LiMa smoke / deploy 脚本
  → SSH → curl 127.0.0.1:19999/api/v1/info（无需 MCP key）
```

**默认关：** 不暴露 19999 到公网；MCP key 仅 VPS `/var/lib/netdata/` 与 Operator `.env`。

### Loopback 绑定（PE-C-1 残余）

Netdata v2.10.3 **不接受** `bind to = loopback`（会 `getaddrinfo('loopback')` 失败）。应使用：

```ini
[web]
    bind to = 127.0.0.1
```

一键脚本：

```powershell
python scripts/bind_netdata_loopback_vps.py
python scripts/smoke_netdata_mcp_vps.py
```

若 restart 后卡在 `activating`（stale PID）：

```powershell
python scripts/recover_netdata_vps.py
```

## 安装

```powershell
python scripts/install_netdata_vps.py
python scripts/smoke_netdata_mcp_vps.py
```

安装脚本使用官方 kickstart（`--non-interactive --stable-channel`）。  
回滚：`systemctl stop netdata && systemctl disable netdata`（必要时 `apt/yum remove netdata`）。

## MCP 认证

Agent 本地 MCP key（安装后）：

```bash
sudo cat /var/lib/netdata/mcp_dev_preview_api_key
# 或
sudo cat /opt/netdata/var/lib/netdata/mcp_dev_preview_api_key
```

写入 VPS `/opt/lima-router/.env`（可选，供 LiMa smoke）：

```env
NETDATA_MCP_ENABLED=0
NETDATA_MCP_URL=http://127.0.0.1:19999/mcp
NETDATA_MCP_API_KEY=...
```

## Cursor / Claude Code 接入（本地 Operator）

**Netdata v2.7.2+（推荐 HTTP）：**

```bash
claude mcp add --transport http netdata-vps \
  http://127.0.0.1:19999/mcp \
  --header "Authorization: Bearer YOUR_MCP_API_KEY"
```

经 SSH 隧道访问 VPS（不在公网开端口）：

```bash
ssh -N -L 19999:127.0.0.1:19999 root@47.112.162.80
```

然后本地 MCP URL 仍为 `http://127.0.0.1:19999/mcp`。

**stdio 客户端（任意 v2.6+）：**

```bash
npx mcp-remote@latest --http http://127.0.0.1:19999/mcp \
  --allow-http \
  --header "Authorization: Bearer YOUR_MCP_API_KEY"
```

## 只读查询示例（API smoke）

```bash
curl -s http://127.0.0.1:19999/api/v1/info | head
curl -s 'http://127.0.0.1:19999/api/v1/data?chart=system.cpu&after=-60&points=1'
```

## 与 LiMa 现有能力边界

| 能力 | Netdata MCP | LiMa 已有 |
|------|-------------|-----------|
| VPS 指标 | ✅ 时序 CPU/mem/disk | Telegram `/health` 摘要 |
| 日志/trace | ❌ 本阶段不做 | journalctl / OpenObserve（计划 PE-C-2） |
| 路由/backend | ❌ **禁止改动** | `router_v3` |

## 验收

- [x] `systemctl is-active netdata` → `active`
- [x] `/api/v1/info` 返回 `version` ≥ 2.6
- [x] `scripts/smoke_netdata_mcp_vps.py` → `smoke_ok`
- [x] 19999 **未**监听公网（`ss -tlnp` 仅 127.0.0.1）

## 参考

- [Netdata MCP README](https://github.com/netdata/netdata/blob/master/docs/netdata-ai/mcp/README.md)
- [Learn Netdata MCP](https://learn.netdata.cloud/docs/netdata-ai/mcp)
