# 小智服务器替代审计

日期：2026-06-18

## 结论

**主链路已闭环，小智服务器可默认退役；仍保留可选兼容层和真机回归边界。**

LiMa 已经接管设备直连、设备管理、任务、OTA、固件默认连接和 manager-mobile 默认入口。`xiaozhi` `/api/v1/*` 兼容层不再默认挂载，仅作为 `LIMA_XIAOZHI_COMPAT_ENABLED=1` 的迁移兜底保留。

## 已由 LiMa 原生替代

- 设备直连链路：`/device/v1/ws`、`/device/v1/tasks`、`/device/v1/events`
- 移动端管理链路：`/device/v1/app/auth/*`、`/device/v1/app/devices*`、`/device/v1/app/tasks*`、members、voiceprints、transfers、supplies、self-checks
- 任务分发与回传：`hello` -> `motion_task` -> `motion_event`
- OTA 发布、灰度、升级计划、安装结果：`routes/device_ota.py`
- 固件端已改为 LiMa 协议默认连接：`esp32S_XYZ/firmware/u8-xiaozhi/main/protocols/websocket_protocol.cc`
- manager-mobile 默认 `https://chat.donglicao.com`、v2 入口、`/device/v1/app` API，设置页使用 `/health` 验证服务地址
- 兼容层默认关闭：`routes/route_registry.py`

## 仅可选兼容层保留

- 账号：`/api/v1/login`、`/api/v1/auth/register`、`/api/v1/auth/me`、`/api/v1/auth/account/delete`
- 设备管理：`/api/v1/devices/register`、`/api/v1/devices/bind`、`/api/v1/devices`、`/api/v1/devices/{id}`、`/api/v1/devices/{id}/unbind`
- 任务管理：`/api/v1/devices/{id}/tasks`、`/api/v1/tasks/{id}`、`approve/reject/pending`
- 成员/声纹：`/api/v1/members`、`/api/v1/voiceprints/enroll`、`DELETE /api/v1/voiceprints/{id}`
- 转移/耗材/自检：`transfer`、`supplies`、`self-checks`

## 仍需实机确认的点

- 真机刷写新固件后，需要确认 `hello` -> `hello_ack` -> `task_dispatch` -> `motion_event` 在真实硬件上闭环。
- 已新增 `scripts/firmware_hardware_gate.py`，可先跑静态固件契约；`--build` 缺少可用 ESP-IDF 源码树时会明确阻塞，`--hardware-smoke` 缺少真实设备凭据时会明确阻塞。
- manager-mobile 已通过 type-check/build，但尚未在真实手机 App 包中做手工登录、绑定、任务审批回归。
- 数据表仍沿用 `v2_*` 命名，这是迁移期数据库事实；外部 API 已切到 `/device/v1/app`。

## 证据

- 兼容层路由：`routes/xiaozhi_v1_compat.py`
- 账号路由：`routes/xiaozhi_compat/user_routes.py`
- 设备路由：`routes/xiaozhi_compat/device_routes.py`
- 任务路由：`routes/xiaozhi_compat/task_routes.py`
- 成员/声纹：`routes/xiaozhi_compat/member_routes.py`
- 其他兼容能力：`routes/xiaozhi_compat/misc_routes.py`
- 原生设备网关：`routes/device_gateway.py`
- 原生 OTA：`routes/device_ota.py`
- 原生 App 测试：`tests/test_device_app_auth.py`、`tests/test_device_app_devices.py`、`tests/test_device_app_tasks.py`、`tests/test_device_app_members_misc.py`
- 移动端静态测试：`tests/test_manager_mobile_lima_native.py`
- 设备闭环测试：`tests/test_fake_u1_cloud_loop.py`
- 兼容层测试：`tests/test_xiaozhi_v1_compat_p0.py`、`tests/test_xiaozhi_v1_compat_p1.py`
- manager-mobile 验证：`corepack pnpm type-check`、`corepack pnpm build:h5`
- 固件/真机门禁：`scripts/firmware_hardware_gate.py`、`tests/test_firmware_hardware_gate.py`、`docs/testing/firmware_hardware_gate.tdd.md`

## 下一批优先级

1. 安装/加载 ESP-IDF 后运行 `scripts/firmware_hardware_gate.py --build --flash --hardware-smoke`，刷写 U8 固件并跑完整设备任务闭环。
2. manager-mobile 真机 App 包登录、绑定、任务审批、OTA 检查回归。
3. 观察一轮生产日志后删除或长期冻结小智 `/api/v1/*` 兼容文档入口。
