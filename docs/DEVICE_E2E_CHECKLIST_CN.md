# 真机 E2E 清单（P0-3）

> 更新日期：2026-07-21
> 目标：录音/任务 → 确认 → 设备 WSS 收 `motion_task` → 纸上运动。
> Host SIL / pytest **不能**替代本清单。

## 0. 云端就绪（可自动化）

```powershell
# 生产 env 审计：fallback 不得裸开
python scripts/check_device_delivery_readiness.py --base-url https://chat.donglicao.com
# 本地
python scripts/check_device_delivery_readiness.py --base-url http://127.0.0.1:8081
```

检查项：

- [ ] `GET /health` → ok（若期望 Redis 则 backend=redis）
- [ ] VPS 上 **`LIMA_RUNTIME_ENV=production`**（未设则 B1 生产门不生效）
- [ ] `LIMA_WS_REGISTERED_DEVICE_FALLBACK` 在 production 为 0，或已显式 `LIMA_WS_FALLBACK_ALLOW_PRODUCTION=1`（临时）
- [ ] `LIMA_DEVICE_TOKENS` 含该 device_id（推荐，避免空 token）
- [ ] `POST /device/v1/ws/ticket` 用 Bearer 设备 token 可取 ticket

## 1. 固件

- [ ] 固件连 `wss://chat.donglicao.com/device/v1/ws?ticket=…`（或内网等价）
- [ ] 连接后发送 `hello`（含 `device_id`；可选 `workspace_mm` / `profile_id` / `fw_rev`）
- [ ] 收到 `hello_ack` 后保持连接；周期 `heartbeat`
- [ ] 实现 token 写入 NVS 后：**关闭** `LIMA_WS_REGISTERED_DEVICE_FALLBACK`

## 2. 业务路径

| 路径 | 步骤 | 期望 |
|------|------|------|
| A 小程序 | 语音转写 → 确认 → 创建任务 | 设备在线时 `dispatchStatus=sent`；离线 `queued_no_delivery` |
| B DLC API | `POST /dlc/tasks/dispatch` | 同上 |
| C 仅投递 | 设备离线入队 → 上线 hello | drain 推送 `motion_task`，机台运动 |

## 3. 证据归档

记录到 `progress.md` / 发布模板：

- 时间、device_id、固件版本、云端 commit
- 任务 task_id、dispatchStatus
- 串口/纸面照片或视频
- 若用 fallback：注明临时开关与下线计划

## 4. 失败排查

| 现象 | 排查 |
|------|------|
| 一直 `queued_no_delivery` | 设备未 hello；ticket 错；nginx 未透传 WSS |
| 401 on ticket | `LIMA_DEVICE_TOKENS` 不匹配 |
| 启动失败 fallback | 生产 env 开了 fallback 未 allow |
| 路径偏小/偏大 | hello 是否带 `workspace_mm`；查 registry profile |
