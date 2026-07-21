# LiMa / DLC 项目状态

> 更新日期：2026-07-21
> 生产版本：`dlc-drawing 0.4.0-p3`（`main` @ `ac230614`+）
> 公网：`https://chat.donglicao.com` → 京东云 `117.72.118.95`（:8081）

> 与根目录 [`STATUS.md`](../STATUS.md) 同步。索引：[`README.md`](README.md)。

---

## 架构

```text
server_dlc → dlc_api / dlc_core / device_gateway（队列+WSS）/ device_voice
小智 MCP → dlc_mcp；小程序 → /device/v1/app/*；ESP32 → /device/v1/ws?ticket=
```

## 已完成

语音 M0–M2、jdcloud 部署、GW-R3、Status WS M2、投递 M1+M2、工作区 profile、hello→registry、draw workspace、文档精简。

## 待办

| ID | 项 |
|----|-----|
| P0-3 | 真机 E2E（清单 `DEVICE_E2E_CHECKLIST_CN.md`） |
| P0-4 | 微信提审 |
| P0-2 | U8 设备语音 |
| E-2 / G3 | draw 真机 / HIL |
| 固件 token | 关 empty-token fallback |

## 命令

```powershell
$env:LIMA_VOICE_E2E_STRICT='1'; python scripts/run_voice_e2e_production.py
python scripts/deploy_unified.py --target jdcloud --slice core
```
