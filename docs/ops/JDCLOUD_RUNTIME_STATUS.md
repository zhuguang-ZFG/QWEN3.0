# JDCloud 运行时状态

> 更新日期：2026-07-21
> 权威状态：[`STATUS.md`](../../STATUS.md) · 架构：[`ARCHITECTURE.md`](../ARCHITECTURE.md)

## 当前角色

| 项 | 值 |
|----|-----|
| 主机 | `117.72.118.95` |
| 公网 | `https://chat.donglicao.com` → nginx → **`server_dlc` :8081** |
| 职责 | DLC 绘图/写字、设备 App API、设备 WSS 投递、小程序语音 ASR |
| 同机可选 | Redis/MySQL、new-api（`api.donglicao.com`）、probe/监控 |

**不是** 多后端 `lima-router` 聊天节点；对话/LLM 由小智官方云承担。

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
$env:LIMA_VOICE_E2E_STRICT='1'
python scripts/run_voice_e2e_production.py
```

历史 lima-router / 分流拓扑文稿已删除（git history）。
