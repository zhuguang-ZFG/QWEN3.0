# 小程序分册：登录 / 配网 / 写画交互 / 状态页

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，小程序保持现有 `/device/v1/app/*` 契约不变，仅内部路径生成收敛到 `dlc_core`。**
> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联总设计：`docs/xiaozhi-cloud/lima-slimdown-design.md`
> 关联分册：`01-architecture.md`、`02-service-refactor.md`、`03-firmware-refactor.md`
> 目标阶段：主要在 P2 落地，配网/防呆提示与 P1/P3 交叉

---

## 1. 本分册目的

明确小程序端在本次瘦身重构中的**改动边界**与**保持不变的部分**，避免固件/服务端接口变化时小程序被反复返工。

核心结论（Ponytail 原则）：

- 小程序端点路径与鉴权链**保持不变**（`/device/v1/app/*` + JWT + 设备所有权校验）。
- 只把服务端内部路径生成逻辑替换为 `dlc_core`，小程序无感知。
- 配网、状态页、写画入口已有实现，本次以**冻结与对齐**为主，不推倒重写。

---

## 2. 小程序真实结构（已核对）

工作区：`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`

技术栈：uni-app + Vue 3 + TypeScript + alova（编译目标 mp-weixin）。

关键目录（`src/pages/`）：

| 目录 | 职责 | 本次状态 |
|------|------|----------|
| `login/` | 用户协议/隐私政策（中英） | 保持 |
| `device-config/` | 配网：BluFi(BLE) + SoftAP + 超声波/AFSK 回退 | 冻结对齐 |
| `v2/device-list/` | 设备列表 | 保持 |
| `v2/device-detail/` | 设备详情：写画面板、语音指令、事件流、耗材、分享、转移 | 冻结对齐 |
| `v2/login/` | v2 登录 | 保持 |
| `create/ai-draw.vue` | AI 绘图入口（可 `allow_dashscope=True`） | 保持 |
| `create/image-draw.vue` | 图库/图片绘图入口 | 保持 |
| `chat/`、`chat-history/` | 对话（P4 视瘦身范围决定去留） | 待定 |

API 层：`src/api/v2/index.ts`，统一前缀 `const appPrefix = '/device/v1/app'`。

---

## 3. 保持不变的契约

### 3.1 API 前缀

小程序继续走 `/device/v1/app/*`，**不迁移到 `/dlc/*`**。`/dlc/*` 仅面向固件 MCP 工具内部调用（见 `02-service-refactor.md` §3 鉴权矩阵）。

### 3.2 关键端点

| 端点 | 用途 | 鉴权 |
|------|------|------|
| `POST /device/v1/app/auth/login` | 微信一键登录（bypass alova，直接 `uni.request`，30s 超时 + 重试 1 次） | 无（换 token） |
| `POST /device/v1/app/devices/{id}/tasks` | 写字/绘图/图库绘图任务下发 | JWT + `require_device_control` |
| `GET /device/v1/app/devices/{id}/status` | 设备状态 | JWT + `require_device_access` |
| `WS /device/v1/app/devices/{id}/status/ws` | 实时状态推送 | JWT |
| `POST /device/v1/app/devices/provision` / `/provision/confirm` | 配网账户绑定 | JWT |
| `POST /device/v1/app/gallery` 等 | 图库上传/列表/删除/下载 | JWT |

### 3.3 服务端内部映射（小程序无感知）

`POST /devices/{id}/tasks` 内部改为：

```text
device_app_tasks.py:create_task
  → dlc_core.task_model.intent_to_motion_task
  → dlc_core.write.handle_write / draw.handle_draw / draw.handle_draw_from_image
  → dlc_core.dispatch.dispatch_task
```

小程序请求体、响应体、鉴权链均不变。

---

## 4. 配网（device-config）

### 4.1 现有配网契约（已核对）

来源：`src/pages/device-config/provisioning-contract.ts`

```text
primaryChannel  : ble_blufi          # 主通道：BLE BluFi
fallbackChannel : softap_http        # 回退：SoftAP HTTP
blufiDeviceName : DLC-Blufi          # (legacy: BLUFI_DEVICE)
softApBaseUrl   : http://192.168.4.1
softApScanPath  : /scan
softApSubmitPath: /submit
softApExitPath  : /exit
submitPayloadFields: ssid, password, server_host, device_secret
```

配网组件：

- `components/blufi-config.vue` — BLE BluFi 主通道
- `components/wifi-config.vue` / `wifi-selector.vue` — Wi-Fi 选择/输入
- `components/ultrasonic-config.vue` + `composables/afskAudio.ts` / `useUltrasonicAudio.ts` — 超声波/AFSK 声波配网回退

### 4.2 本次约束

- **不推倒重写配网**。BluFi + SoftAP 双通道已实现，保持。
- 配网提交字段 `device_secret` 与固件 per-device token 对齐（见 `02-service-refactor.md` S7、`03-firmware-refactor.md`）。
- 一键配网 UX 目标：用户最少步骤完成 Wi-Fi 凭据 + 账户绑定，凭据经 SoftAP/BluFi 写入设备 NVS。
- 配网绑定端点统一为 `device_app_provision.py`；`device_app_discovery.py` 若重复，P3 删除（见 `02-service-refactor.md`）。

### 4.3 待决项（引用 `08-open-questions.md`）

- **Q-09 小程序一键配网**：BluFi 与 SoftAP 的默认优先级、失败回退顺序、超声波是否保留，在 P2 落地时最终确定。

---

## 5. 写画交互（v2/device-detail）

### 5.1 现有组件（已核对）

`src/pages/v2/device-detail/`：

| 组件/composable | 职责 |
|-----------------|------|
| `components/write-draw-panel.vue` | 写字/绘图面板（一键写字、画图入口） |
| `components/voice-command.vue` + `composables/useVoiceCommand.ts` | 语音指令 |
| `composables/useVoiceStream.ts` | 语音流 |
| `composables/useDeviceEvents.ts` | 设备事件流（任务状态/失败通知） |
| `components/supplies-panel.vue` | 耗材 |
| `components/share-panel.vue` / `transfer-panel.vue` | 分享/转移设备 |
| `components/voice-approval.vue` | 语音审批 |

绘图入口：`src/pages/create/ai-draw.vue`（AI 生图）、`image-draw.vue`（图库/图片绘图）。

### 5.2 本次约束

- 写画面板继续调用 `POST /devices/{id}/tasks`，`capability` 取 `write_text` / `draw_generated` / `draw_from_image`。
- `ai-draw.vue` 走 `allow_dashscope=True`（用户明确点击 AI 绘图，付费/延迟可接受）；语音路径与固件 MCP 强制 `allow_dashscope=False`（见 `02-service-refactor.md` §3.4）。
- 图库绘图：先 `GET /gallery/{id}/download` 拿 Telegram 临时 URL，再作为 `image_url` 提交 `draw_from_image`（服务端立即下载到本地临时文件，见 `02-service-refactor.md`）。

### 5.3 防呆提示（设备忙）

对齐 `03-firmware-refactor.md` §防呆 与 `06-failure-and-safety.md`：

- 当 `/devices/{id}/tasks` 返回 `status=rejected, reason=device_busy` 时，写画面板应提示“绘图机正在执行上一个任务，请稍等”，**不自动重试**。
- `useDeviceEvents.ts` 收到 `task_failed` 时展示失败原因与重试记录。

---

## 6. 状态页（对齐 dlc_core.device_status）

- 设备详情页状态来自 `GET /devices/{id}/status`，服务端内部聚合改为 `dlc_core.device_status.get_device_status`（registry + active_tasks_for_device + shadow_store）。
- 实时推送 `status/ws` 保持轮询 + transition 推送模型。
- 小程序显示字段不变：`online` / `working` / `activeTaskId` / `firmwareVersion` / `lastSeenAt`。

---

## 7. 本分册冻结项（P2 实现前必须锁定）

1. 小程序 API 前缀保持 `/device/v1/app/*`，不改 `/dlc/*`。
2. 写画 capability 三态：`write_text` / `draw_generated` / `draw_from_image`。
3. `allow_dashscope`：小程序 AI 绘图 `True`，语音/固件路径 `False`。
4. 配网双通道 BluFi + SoftAP 保持，`device_secret` 与固件 per-device token 对齐。
5. `device_busy` 时提示不重试。
6. 状态字段与来源不变，仅服务端内部聚合切到 `dlc_core`。

---

## 8. 与其它分册的关系

| 关注点 | 本分册 | 交给谁 |
|--------|--------|--------|
| 端点内部落到 dlc_core | 映射说明 | `02-service-refactor.md` §3.5 |
| 固件 tool / 防呆 | 引用 | `03-firmware-refactor.md` |
| 失败通知/重试/死信 | 引用 | `06-failure-and-safety.md` |
| 配网/绘图路线待决 | 引用 | `08-open-questions.md` Q-09/Q-02/Q-03 |
| 上传流程（编译/版本 bump） | 不重复 | 根 `AGENTS.md`「小程序一键上传」 |

---

## 9. 小结

小程序端本次以**冻结与对齐**为主：

- 契约不变、鉴权不变、页面不推倒。
- 只在服务端内部把路径生成切到 `dlc_core`。
- 配网、写画、状态页均已存在真实实现，本分册负责把它们与新服务端/固件接口对齐并锁定边界。

这是最小改动、最低返工风险的推进方式，符合 Ponytail 第一原则。
