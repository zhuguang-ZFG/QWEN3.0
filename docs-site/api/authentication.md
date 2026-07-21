# 认证方式

> 更新日期：2026-07-21

## DLC / 设备

| 场景 | 方式 |
|------|------|
| DLC HTTP（`/dlc/*`） | Bearer DLC API token（见部署环境变量） |
| 小程序 App API | 小程序登录 JWT / 设备绑定态 |
| 设备 WSS | `POST /device/v1/ws/ticket` 后 `?ticket=`（推荐）或 Header Bearer |
| 小程序语音 WS | `voice` ticket（30s TTL） |

## 已退役

公开「`lima-xxx` 调 `/v1/chat/completions`」多后端聊天密钥模型已退役。对话走小智官方云。

详情：仓库 `docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md`、`docs/DEPLOY_AND_RELEASE_CONVENTION.md`。
