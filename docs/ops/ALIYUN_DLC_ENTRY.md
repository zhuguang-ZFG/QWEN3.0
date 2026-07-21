# 阿里云 DLC 运行时状态

> 更新日期：2026-07-21
> 权威状态：[`STATUS.md`](../../STATUS.md) · 京东云主生产：[`JDCLOUD_RUNTIME_STATUS.md`](JDCLOUD_RUNTIME_STATUS.md)

## 当前角色

| 项 | 值 |
|----|-----|
| 主机 | `47.112.162.80` |
| 角色 | **DLC + MCP 辅节点**（非公网主入口） |
| 公网主入口 | 仍为京东云 `chat.donglicao.com` → `117.72.118.95` |
| 运行服务 | `dlc-drawing`（`server_dlc` :8081）、`dlc-mcp` |
| 已卸载 | `lima-router` / pilot、new-api、probe/监控、code-server、旁路代理 |

## 拓扑（实际）

```text
Internet → Cloudflare → 京东云 nginx → server_dlc :8081   （主）
                       阿里云 dlc-drawing / dlc-mcp       （辅 / MCP）
```

## 部署

```powershell
python scripts/deploy_unified.py --target aliyun --slice core
```

- 远程目录与 systemd 以实际 `/opt/dlc-drawing`（或部署脚本目标）为准
- 约定：[`DEPLOY_AND_RELEASE_CONVENTION.md`](../DEPLOY_AND_RELEASE_CONVENTION.md)

## 验证

```bash
# 机内 loopback
ssh root@47.112.162.80 'curl -sf http://127.0.0.1:8081/health'
```

历史「设计阶段 / lima-router-pilot 公网入口」方案已废弃；本文件记录**当前已落地**的辅节点事实。
