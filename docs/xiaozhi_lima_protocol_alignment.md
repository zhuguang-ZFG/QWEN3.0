# XiaoZhi API 与 LiMa 设备协议对齐报告

版本：v1.0
日期：2026-06-10
阶段：Phase 0 覆盖审计
范围：`docs/xiaozhi_api_openapi.yaml`、`routes/xiaozhi_v1_compat.py`、`routes/route_registry.py`、LiMa Device Gateway MQTT/WS/HTTP 协议

## 1. 总体结论

XiaoZhi 原始接口模型偏向 HTTP REST：账号、设备、任务、成员、声纹、转移、耗材、自检都通过 App/服务端 REST API 表达。LiMa 现有设备云模型是 MQTT + REST：账号和管理面继续走 REST，设备实时通信、任务下发、状态上报走 MQTT/WS，并保留 `/device/v1/events` 与 `/device/v1/tasks` 作为私有 HTTP 回退和测试入口。

当前 LiMa 的优势是设备热路径已经更适合 IoT：`hello`、`heartbeat`、`motion_event`、`device_info`、`self_check` 等上行帧可通过 MQTT/WS 进入 Device Gateway，任务可通过在线会话即时下发或进入 pending queue。缺口是 XiaoZhi REST 兼容层还没有覆盖 OpenAPI 的大部分管理接口，并且当前兼容 router 使用 `/api/v1` 前缀，与 OpenAPI 的 `/v1` server + `/auth/*` 路径结构不完全一致。

现状摘要：

| 项 | 结论 |
| --- | --- |
| OpenAPI 操作数 | 29 个操作：28 个业务操作 + 1 个 `/health` |
| 已实现兼容 REST | 9 个，位于 `routes/xiaozhi_v1_compat.py` |
| 兼容 router 前缀 | `/api/v1` |
| route_registry 注册状态 | 当前 `routes/route_registry.py` 未 include `xiaozhi_v1_compat` |
| MQTT topic 合约 | `lima/{device_id}/uplink`、`lima/{device_id}/downlink`、`lima/{device_id}/status`、`lima/broadcast` |
| 已激活能力族 | `motion` |
| 门控能力族 | `display`、`audio`、`speech`、`ocr`、`camera`、`perception` |

## 2. 协议边界：HTTP REST vs LiMa MQTT + REST

REST 应保留为“管理面”和“用户/家庭/资产状态”的接口层：

- Auth：登录、注册、短信验证码、当前用户、改密、注销。
- Device：注册、绑定、列表、详情、更新、解绑、手工添加。
- Task：创建任务、审批任务、拒绝任务、查询任务和待审批任务。
- Member：家庭成员创建与查询。
- Voiceprint：声纹登记、删除和后续样本管理。
- Transfer：设备转移申请、接受、取消、待处理列表。
- Supply：耗材状态查询和更新。
- SelfCheck：自检历史查询。

MQTT/WS 应作为“设备热路径”：

- 设备上线和协议协商：`hello`。
- 心跳和在线状态：`heartbeat` + status/LWT。
- 语音转文字或设备侧自然语言输入：`transcript`。
- 运动任务生命周期：`motion_task` downlink + `motion_event` uplink。
- 设备信息与自检：`device_info`、`self_check`。

REST 与 MQTT 的分工原则：

| 场景 | 建议入口 | 原因 |
| --- | --- | --- |
| App 登录、绑定设备、管理成员 | REST | 需要账号鉴权、数据库事务和同步响应 |
| App 提交写字/绘图任务 | REST -> Device Gateway | REST 创建任务，Gateway 负责下发/排队 |
| 设备在线握手、心跳、任务执行进度 | MQTT/WS | 长连接更适合 IoT 实时性和断线恢复 |
| 设备离线后的任务保存 | REST/内部队列 | 任务先持久化，设备恢复后通过下行触发 |
| 设备自检和耗材自动上报 | MQTT uplink，REST 查询 | 设备上报事实，App 用 REST 读状态 |

## 3. OpenAPI 覆盖矩阵

说明：

- “已实现”表示 `routes/xiaozhi_v1_compat.py` 有直接 REST 入口，但路径可能与 OpenAPI 不完全一致。
- “LiMa Gateway”表示已有设备侧能力或私有入口可承接，但还缺少 XiaoZhi REST 外观。
- “缺失”表示当前没有发现对应 REST 兼容实现。
- 当前兼容层路径均以 `/api/v1` 为前缀；OpenAPI 业务路径不含 `/api`，server 示例为 `/v1`。

| 域 | Method | OpenAPI path | LiMa 当前承接点 | 覆盖状态 | 优先级 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| Auth | POST | `/auth/login` | `POST /api/v1/login` | 部分 | P0 | 已有手机号 + code 登录/自动注册；路径与 OpenAPI 不一致。 |
| Auth | POST | `/auth/register` | `POST /api/v1/login` 可间接自动注册 | 部分 | P0 | 缺少显式 register 语义、校验和响应契约。 |
| Auth | POST | `/auth/sms-verification` | 无 | 缺失 | P0 | 可先实现为受限 mock/固定验证码，再接短信服务。 |
| Auth | GET | `/auth/captcha` | 无 | 缺失 | P1 | 短信风控依赖；Phase 0 可返回占位 captcha 或关闭强依赖。 |
| Auth | GET | `/auth/me` | JWT `_authorize()` 可查账号 | 缺失 | P0 | 已有认证基础，补 REST 包装即可。 |
| Auth | PUT | `/auth/change-password` | 无 | 缺失 | P2 | 当前登录是短信码模型，密码体系需明确是否保留。 |
| Auth | POST | `/auth/account/delete` | 无 | 缺失 | P1 | 需要软删账号、解绑设备、匿名化成员/声纹。 |
| Device | POST | `/devices/register` | 无 | 缺失 | P0 | OpenAPI 要生成激活码；当前 bind 可接受预设激活码。 |
| Device | POST | `/devices/bind` | `POST /api/v1/devices/bind` | 已实现 | P0 | 已写入 `v2_device` 与 `v2_device_binding`。 |
| Device | GET | `/devices` | 无 | 缺失 | P0 | 数据表已有绑定关系，需补列表接口。 |
| Device | GET | `/devices/{deviceId}` | 无 | 缺失 | P0 | 可从 `v2_device` + binding 权限查询。 |
| Device | PUT | `/devices/{deviceId}` | 无 | 缺失 | P1 | 可更新 nickname、firmwareVer 等字段。 |
| Device | POST | `/devices/{deviceId}/unbind` | 无 | 缺失 | P0 | 需要将 binding 置 inactive 并记录 unbound_at。 |
| Device | POST | `/devices/manual-add` | 无 | 缺失 | P2 | 管理员入口，不能暴露给普通用户。 |
| Task | POST | `/devices/{deviceId}/tasks` | `POST /api/v1/devices/{device_id}/tasks` | 已实现 | P0 | 已接入参数校验、策略、模拟、审批、下发/排队。 |
| Task | GET | `/devices/{deviceId}/tasks` | 无 | 缺失 | P0 | `v2_task` 已有数据，需补查询和分页。 |
| Task | GET | `/tasks/{taskId}` | 无 | 缺失 | P0 | 任务详情是 App 和调试必需接口。 |
| Task | POST | `/tasks/{taskId}/approve` | `POST /api/v1/tasks/{task_id}/approve` | 已实现 | P1 | 可推进 workflow 并下发任务。 |
| Task | POST | `/tasks/{taskId}/reject` | `POST /api/v1/tasks/{task_id}/reject` | 已实现 | P1 | 已记录 rejected motion event。 |
| Task | GET | `/devices/{deviceId}/tasks/pending` | `GET /api/v1/devices/{device_id}/tasks/pending` | 已实现 | P1 | 查询待审批语音任务。 |
| Member | POST | `/members` | `POST /api/v1/members` | 已实现 | P1 | 已创建 `v2_member`。 |
| Member | GET | `/devices/{deviceId}/members` | `GET /api/v1/devices/{device_id}/members` | 已实现 | P1 | 已按 device 查询 active 成员。 |
| Voiceprint | POST | `/voiceprints/enroll` | `POST /api/v1/voiceprints/enroll` | 已实现 | P1 | 只启动登记记录；音频样本链路仍需 MQTT/WS 或上传接口。 |
| Voiceprint | DELETE | `/voiceprints/{voiceprintId}` | 无 | 缺失 | P1 | 需软删除声纹并解除 member.voiceprint_id。 |
| Transfer | POST | `/devices/{deviceId}/transfer` | 无 | 缺失 | P1 | 需 transfer 表、过期时间和接收方账号解析。 |
| Transfer | GET | `/transfers/pending` | 无 | 缺失 | P1 | 接收方待处理列表。 |
| Transfer | POST | `/transfers/{transferId}/accept` | 无 | 缺失 | P1 | 需事务切换 owner binding。 |
| Transfer | POST | `/transfers/{transferId}/cancel` | 无 | 缺失 | P1 | 需发起方/管理员权限校验。 |
| Supply | PUT | `/devices/{deviceId}/supplies` | MQTT `device_info`/未来 supply uplink 可承接事实 | 缺失 | P2 | REST 更新和设备上报需要统一模型。 |
| Supply | GET | `/devices/{deviceId}/supplies` | 无 | 缺失 | P2 | App 查询耗材状态。 |
| SelfCheck | GET | `/devices/{deviceId}/self-checks` | MQTT/HTTP uplink `self_check` 已更新 shadow | 部分 | P2 | 缺少持久化历史查询 REST。 |
| Health | GET | `/health` | `/health` 与 `GET /device/v1/health` | 部分 | P0 | 系统已有健康检查；OpenAPI `/v1/health` 外观需确认。 |

按 OpenAPI 统计，29 个操作中当前 REST 兼容层直接覆盖 9 个；如果把 `register` 视为 `login` 的自动注册副作用，则 Auth 覆盖仍只能算“部分”，不应算作完整接口兼容。

## 4. MQTT 消息对齐

### 4.1 Topic 合约

LiMa 当前标准 topic：

| Topic | 方向 | 用途 |
| --- | --- | --- |
| `lima/{device_id}/uplink` | Device -> Server | 设备上报 JSON 帧 |
| `lima/{device_id}/downlink` | Server -> Device | 服务端下发 JSON 帧 |
| `lima/{device_id}/status` | Device/Broker -> Server | LWT/在线状态 |
| `lima/broadcast` | Server -> Devices | 广播消息 |

代码中的 `device_gateway/mqtt_topics.py` 使用上述四类 topic；旧文档中出现过 `lima/devices/{device_id}/...`，需要统一为当前代码合约 `lima/{device_id}/...`，否则固件订阅和云端发布会错位。

### 4.2 LiMa 6 类 uplink

| Uplink type | 设备含义 | 对应 REST/API 关系 | 当前状态 |
| --- | --- | --- | --- |
| `hello` | 设备上线、协议版本、能力列表、硬件/固件信息 | Device register/detail 的设备事实来源 | MQTT client/WS 支持 |
| `heartbeat` | 心跳、uptime、在线状态刷新 | Device list/detail 的 online/offline 状态来源 | MQTT client/WS 支持 |
| `transcript` | 设备侧语音/文本输入 | 可触发 task 创建，相当于 voice source | WS/Device Gateway 支持 |
| `motion_event` | 运动任务 accepted/running/progress/done/failed 等生命周期 | Task detail/list 的状态事实来源 | HTTP/WS/MQTT 支持 |
| `device_info` | model、hw_rev、fw_rev、workspace 等设备信息 | Device detail/update 的设备侧事实来源 | HTTP/WS 支持，MQTT client 可扩展 |
| `self_check` | 启动/周期/手动自检结果 | SelfCheck history 的事实来源 | HTTP/WS 支持，当前更偏 shadow |

### 4.3 LiMa 4 类 downlink

| Downlink type | 云端含义 | 对应 REST/API 关系 | 当前状态 |
| --- | --- | --- | --- |
| `hello_ack` | 上线确认、server_time、shadow delta | 设备接入握手 | 已有 |
| `heartbeat_ack` | 心跳确认、server_time | 在线状态维持 | MQTT client 已构造 |
| `motion_task` | 运动/绘图/写字任务下发 | REST `POST /devices/{deviceId}/tasks` 的执行层 | 已有任务对象；WS 直接发送 |
| `task_available`/pending drain | 通知设备有待领取任务或由会话 drain 下发 | 离线任务恢复 | Redis/local notifier 已有；需要明确 MQTT 下行帧命名 |

注意：`device_gateway.protocol.run_path_dispatch_frame()` 构造的是 `task_dispatch` 类型，而 `device_gateway.tasks` 里任务对象类型是 `motion_task`。固件、MQTT 下行和 REST 任务创建应在 Phase 0 收敛到一个兼容策略：要么设备同时接受 `motion_task` 和 `task_dispatch`，要么云端统一输出一个主类型并保留旧类型适配。

## 5. 能力族与 motion 映射

LiMa 当前定义 7 个协议能力族：

| 能力族 | 状态 | 能力示例 | 对齐建议 |
| --- | --- | --- | --- |
| `motion` | 已激活 | `run_path`、`write_text`、`draw_generated`、`home`、`pause`、`resume`、`stop`、`get_device_info` | Phase 0 主线；只允许安全、可模拟、可审计的任务。 |
| `display` | 门控 | `show_image`、`show_text`、`clear_screen` | 等 motion 稳定后再开放 companion screen。 |
| `audio` | 门控 | `play_audio`、`stop_audio`、`set_volume` | 需音频资源鉴权和设备音量安全策略。 |
| `speech` | 门控 | `tts_speak`、`voice_clone` | voice_clone 必须隐私和授权门控。 |
| `ocr` | 门控 | `capture_text`、`read_display` | 涉及图像隐私，需要单独审计。 |
| `camera` | 门控 | `capture_frame`、`stream_start`、`stream_stop` | 涉及实时视频和隐私，不能并入 motion。 |
| `perception` | 门控 | `wifi_csi_sample`、`presence_detect` | 只能作为感知事件，不得直接触发硬件运动。 |

OpenAPI 中 `TaskSubmitRequest.capability` 当前枚举是 `run_path`、`draw_image`、`home`、`calibrate`。`xiaozhi_v1_compat.py` 的映射关系：

| OpenAPI capability | LiMa Gateway capability | 当前处理 |
| --- | --- | --- |
| `run_path` | `run_path` | 直接映射，保留 `source_capability=run_path`。 |
| `draw_image` | `draw_generated` → `run_path` | App 提交自然语言 prompt 时经 `handle_device_draw` 生图矢量化；若仅提供 `imageUrl` 而无 `prompt`，行为取决于参数映射（见 `routes/device_app_tasks.py`）。 |
| `home` | `home` | 直接控制类任务。 |
| `calibrate` | `home` | 临时映射到 `home`，保留 `source_capability=calibrate`。 |

motion 族需要补齐 6 个动作的 REST/设备一致性：`run_path`、`write_text`、`draw_generated/draw_image`、`home`、`pause/resume/stop`、`get_device_info`。其中 OpenAPI 已暴露的是前四类，暂停/恢复/停止和设备信息目前更多存在于 LiMa 内部能力模型，后续应决定是否进入 XiaoZhi 兼容 REST。

## 6. 数据模型差异

XiaoZhi OpenAPI 的核心对象是 Account、Device、Task、Member、Voiceprint、Transfer、Supply、SelfCheck。LiMa 当前兼容层已经落到 `v2_account`、`v2_device`、`v2_device_binding`、`v2_task`、`v2_member`、`v2_voiceprint` 等 SQLite 表，并把设备热路径状态交给 Device Gateway task store、session registry、shadow store 和 workflow。

主要差异：

| 对象 | XiaoZhi/OpenAPI 期望 | LiMa 当前状态 | 风险 |
| --- | --- | --- | --- |
| Account | 显式注册、登录、me、改密、软删 | 只有 login/自动注册和 JWT | App 侧账号页面无法完整迁移。 |
| Device | 注册码、绑定、列表、详情、更新、解绑、手工添加 | 只有 bind；设备事实散落在 device 表和 shadow | 绑定后 App 缺少管理闭环。 |
| Task | 创建、列表、详情、审批、拒绝、待审批 | 创建/审批/拒绝/待审批已实现；列表/详情缺失 | App 无法可靠追踪历史和状态。 |
| Member | 创建、按设备列表 | 已实现 | 需要补更新/删除时再扩展。 |
| Voiceprint | 登记、删除、样本状态 | 登记记录已实现，删除缺失 | 隐私删除不完整。 |
| Transfer | 申请、待处理、接受、取消 | 缺失 | 多账号设备流转无法迁移。 |
| Supply | 查询、更新 | 缺失 | 耗材状态只能后续补。 |
| SelfCheck | 历史查询 | uplink/shadow 有基础，历史 REST 缺失 | App 诊断页无法迁移。 |

建议把“设备事实”和“App 查询模型”分开：MQTT/WS 上行先写 shadow + history 表，REST 只从持久化模型读，不让 App 直接依赖内存 session。

## 7. 差距清单与优先级

### P0：Phase 0 必须补齐

1. 在 `routes/route_registry.py` 注册 `routes.xiaozhi_v1_compat.router`，否则 9 个兼容接口不会挂到 app。
2. 明确兼容路径策略：保留 `/api/v1/*` 还是补 `/v1/*` + OpenAPI 原路径。建议新增 OpenAPI 对齐外观，同时保留旧 `/api/v1` 作为兼容别名。
3. 补 Auth：`POST /auth/register`、`POST /auth/sms-verification`、`GET /auth/me`。
4. 补 Device：`POST /devices/register`、`GET /devices`、`GET /devices/{deviceId}`、`POST /devices/{deviceId}/unbind`。
5. 补 Task：`GET /devices/{deviceId}/tasks`、`GET /tasks/{taskId}`。
6. 统一任务下行帧：明确 `motion_task` 与 `task_dispatch` 的兼容关系，并写入协议文档/固件适配。
7. 为已实现 REST 兼容接口补集成测试，覆盖 login -> bind -> submit task -> pending/approve/reject。

### P1：迁移闭环

1. 补 `POST /auth/account/delete`，包括设备解绑、成员匿名化和声纹软删。
2. 补 Voiceprint 删除：`DELETE /voiceprints/{voiceprintId}`。
3. 补 Transfer 全套接口：申请、待处理、接受、取消。
4. 补 Device update：`PUT /devices/{deviceId}`。
5. 将 `self_check` 从 shadow 扩展为历史记录，补 `GET /devices/{deviceId}/self-checks`。
6. 对 `voiceprints/enroll` 明确音频样本上传或 MQTT/WS 采样协议。

### P2：运营和高级设备能力

1. 补 Supply 查询/更新，并定义设备上报耗材状态的 uplink schema。
2. 补 `GET /auth/captcha` 和 `PUT /auth/change-password`，前提是确认产品仍保留密码登录。
3. 补 `/devices/manual-add` 管理员接口和审计日志。
4. 建立 display/audio/speech/ocr/camera/perception 的独立审批门，不与 motion 共享放行条件。

## 8. 建议实施顺序

最小可交付切片：

1. 注册 `xiaozhi_v1_compat` router，并用测试确认 `/api/v1/login` 可访问。
2. 新增 OpenAPI 路径别名层，先覆盖已实现 9 个接口的标准路径。
3. 补 P0 读接口：`/auth/me`、`/devices`、`/devices/{deviceId}`、`/devices/{deviceId}/tasks`、`/tasks/{taskId}`。
4. 补 P0 绑定闭环：`/devices/register` 生成激活码，`/devices/{deviceId}/unbind` 解除绑定。
5. 更新 OpenAPI 或实现，使路径前缀、返回字段、错误码三者一致。
6. 增加 focused pytest：OpenAPI P0 route availability、JWT auth、device binding、task query、route_registry include。

验收标准：

- OpenAPI 29 个操作均有明确状态：已实现、兼容别名、Gateway 承接或显式未实现。
- P0 REST 接口在本地 FastAPI app 中全部可路由。
- motion 任务可从 REST 创建，经 Device Gateway 下发/排队，并由 `motion_event` 更新状态。
- `route_registry.py` 启动路径明确加载兼容 router。
- MQTT topic 文档、代码和固件订阅一致使用 `lima/{device_id}/...`。
