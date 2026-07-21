# LiMa / DLC 项目状态

> 更新日期：2026-07-21
> 生产版本：`dlc-drawing 0.4.0-p3`（`main` @ `e8a5ee2d`）
> 公网入口：`https://chat.donglicao.com` → Cloudflare → 京东云 `117.72.118.95`（nginx → `server_dlc` :8081）

> 与 [`docs/PROJECT_STATUS_CN.md`](docs/PROJECT_STATUS_CN.md) 同步。文档索引：[`docs/README.md`](docs/README.md)。

---

## 当前架构

```text
Internet → Cloudflare / cloudflared
        → 京东云 nginx (chat.donglicao.com)
        → server_dlc.py (:8081)
             → dlc_api/            /dlc/*
             → dlc_core/           绘图/写字
             → device_gateway/     Redis 队列 + 设备 WSS 投递
             → device_voice/       小程序语音 ASR
小智 MCP → dlc_mcp/（阿里云辅节点亦有）
小程序   → /device/v1/app/*、/v1/voice?ticket=
ESP32    → /device/v1/ws?ticket=（hello → drain → motion_task）
```

- **主生产**：京东云 `117.72.118.95`（Redis/MySQL/cloudflared + `dlc-drawing`）
- **辅节点**：阿里云 `47.112.162.80`（`dlc-drawing` + `dlc-mcp`）
- **已退役（代码与 VPS）**：`lima-router` :8080、多后端 chat、new-api、probe/监控栈、code-server、grok2api/flaresolverr 等旁路服务
- nginx 仅代理 DLC 路径；旧 chat/completions 等返回 **410**。模板：[`deploy/nginx/chat.donglicao.com.conf`](deploy/nginx/chat.donglicao.com.conf)

---

## 已完成（近期）

| 里程碑 | 状态 |
|--------|------|
| 小程序语音 M0–M2 + strict E2E | ✅ |
| jdcloud 默认部署 + 双机部署验证 | ✅ |
| GW-R3 运动安全 | ✅ |
| Status WS M2 进度/固件推送 | ✅ |
| 设备投递 M1+M2（WSS + reaper） | ✅ |
| 诚实投递状态 `sent` / `queued` / `queued_no_delivery` | ✅ |
| 工作区 profile（complete 收紧 + 校验） | ✅ |
| hello→register_device_profile + 三轴 workspace | ✅ |
| draw SVG stage 跟 workspace（optimize→validate） | ✅ |
| 生产禁止裸开 WS empty-token fallback | ✅ |
| 公网 502 修复：nginx 指向 :8081 | ✅ |
| nginx DLC-only + 退役路径 410 | ✅ |
| VPS 深度瘦身（双机仅 DLC 必要服务） | ✅ |
| 文档 archive 清理 + 状态同步 | ✅ |

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
# 含 nginx 模板同步：
python scripts/deploy_unified.py --target jdcloud --slice core --sync-nginx
```

- 语音 ticket TTL 30s；设备 WSS ticket 见 `device_ws_ticket.py`
- Host SIL ≠ 真机 HIL
- 运行时：[`docs/ops/JDCLOUD_RUNTIME_STATUS.md`](docs/ops/JDCLOUD_RUNTIME_STATUS.md) · [`docs/ops/ALIYUN_DLC_ENTRY.md`](docs/ops/ALIYUN_DLC_ENTRY.md)
