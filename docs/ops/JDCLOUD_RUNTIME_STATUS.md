# JDCloud 运行时状态

> 更新日期：2026-07-21
> 权威状态：[`STATUS.md`](../../STATUS.md) · 架构：[`ARCHITECTURE.md`](../ARCHITECTURE.md)

## 当前角色

| 项 | 值 |
|----|-----|
| 主机 | `117.72.118.95` |
| 公网 | `https://chat.donglicao.com` → Cloudflare/cloudflared → nginx → **`server_dlc` :8081** |
| 职责 | DLC 绘图/写字、设备 App API、设备 WSS 投递、小程序语音 ASR |
| 同机保留 | Redis、MySQL、cloudflared、`dlc-drawing` systemd、nginx |
| 已卸载 | `lima-router` :8080、new-api、probe/监控栈、code-server、旁路代理（grok2api/flaresolverr 等） |

**不是** 多后端 `lima-router` 聊天节点；对话/LLM 由小智官方云承担。

## nginx

- 模板：[`deploy/nginx/chat.donglicao.com.conf`](../../deploy/nginx/chat.donglicao.com.conf)
- 仅代理 DLC：`/health`、`/health/ready`、`/dlc/*`、`/device/v1/*`、`/v1/voice*` 等
- 退役 chat/completions 等路径：**HTTP 410**
- 同步：`python scripts/deploy_unified.py --target jdcloud --slice core --sync-nginx`

## 部署

```powershell
python scripts/deploy_unified.py --target jdcloud --slice core
```

- 远程：`/opt/dlc-drawing/`
- 备份：`/opt/dlc-drawing/backups/`
- systemd：`dlc-drawing`
- 约定：[`DEPLOY_AND_RELEASE_CONVENTION.md`](../DEPLOY_AND_RELEASE_CONVENTION.md)
- 本机脚本目录：`deploy/jdcloud/`

## 探针

```powershell
# 机内（可靠）
# ssh … curl -sf http://127.0.0.1:8081/health

# 语音 strict E2E（公网/凭证依赖）
$env:LIMA_VOICE_E2E_STRICT='1'
python scripts/run_voice_e2e_production.py
```

历史 lima-router / 分流拓扑 / new-api 运维文稿已删除（git history）。
