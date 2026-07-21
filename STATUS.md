# LiMa / DLC 项目状态

> 更新日期：2026-07-21
> 生产版本：`dlc-drawing 0.4.0-p3`（`main` @ `ac230614`+）
> 公网入口：`https://chat.donglicao.com` → 京东云 `117.72.118.95`（`server_dlc` :8081）

> 与 [`docs/PROJECT_STATUS_CN.md`](docs/PROJECT_STATUS_CN.md) 同步。文档索引：[`docs/README.md`](docs/README.md)。

---

## 当前架构

```text
server_dlc.py (:8081)
  → dlc_api/            /dlc/*
  → dlc_core/           绘图/写字
  → device_gateway/     Redis 队列 + 设备 WSS 投递
  → device_voice/       小程序语音 ASR
小智 MCP → dlc_mcp/
小程序   → /device/v1/app/*、/v1/voice?ticket=
ESP32    → /device/v1/ws?ticket=（hello → drain → motion_task）
```

已退役代码：`routing_engine*`、旧 `server.py` 聊天栈、`context_pipeline` 主路径。过期文档已删，查 git history。

---

## 已完成（近期）

| 里程碑 | 状态 |
|--------|------|
| 小程序语音 M0–M2 + strict E2E | ✅ |
| jdcloud 默认部署 | ✅ |
| GW-R3 运动安全 | ✅ |
| Status WS M2 进度/固件推送 | ✅ |
| 设备投递 M1+M2（WSS + reaper） | ✅ |
| 工作区 profile（complete 收紧 + 校验） | ✅ |
| hello→register_device_profile | ✅ |
| draw SVG 目标跟 workspace | ✅ |
| 生产禁止裸开 WS empty-token fallback | ✅ |
| 文档 archive 清理 + 深度精简 | ✅ |

---

## 待办（阻塞上线）

| ID | 项 | 阻塞 |
|----|-----|------|
| P0-3 | 真机 E2E（语音→运动 + WSS 投递） | 真机；清单 `docs/DEVICE_E2E_CHECKLIST_CN.md` |
| P0-4 | 微信提审 | 运营 |
| P0-2 | U8 OPUS/PCM 设备语音 | 产品 |
| E-2 / G3 | draw 真机 / HIL 纸路 | 真机 |
| 固件 token | 写入 NVS 后关闭 `LIMA_WS_REGISTERED_DEVICE_FALLBACK` | 固件 |

详见 [`docs/superpowers/specs/2026-07-02-backlog-planning.md`](docs/superpowers/specs/2026-07-02-backlog-planning.md)。

---

## 语音 / 仿真 / 部署

```powershell
$env:LIMA_VOICE_E2E_STRICT='1'; python scripts/run_voice_e2e_production.py
$env:FZ_ROOT='D:\Users\zhugu\fz'; python $env:FZ_ROOT\scripts\agent_gate.py --profile firmware
python scripts/deploy_unified.py --target jdcloud --slice core
```

- 语音 ticket TTL 30s；设备 WSS ticket 见 `device_ws_ticket.py`
- Host SIL ≠ 真机 HIL
