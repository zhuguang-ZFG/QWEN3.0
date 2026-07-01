# 小程序语音控制绘图机/写字机 设计文档

- **日期**: 2026-07-02
- **状态**: 待审批
- **前置**: 系统瘦身已完成（见 `2026-07-02-system-slimdown-design.md`），基线已清理
- **范围**: 小程序端补齐语音交互能力，驱动绘图机（draw_generated）和写字机（write_text）

---

## 一、需求与现状

### 1.1 用户需求

用户通过小程序，用**语音控制**让绘图机绘图、写字机写字。例如：
- "画一只猫" → 绘图机 draw_generated
- "写你好世界" → 写字机 write_text
- "归零" → 设备 home

### 1.2 现状结论（已核实）

**后端基础设施约 80% 已存在**（2026-07-02 核实，258 个语音/intent 测试通过）：

| 能力 | 模块 | 状态 |
|------|------|------|
| ASR 转写 | `device_voice.get_asr_provider()` → FunASR/Aliyun/Doubao/DashScope/Whisper | ✅ 已有 |
| 意图解析 | `device_gateway.intent.resolve_voice_task(text)` → `{capability, params, source, explanation}` | ✅ 已有（同步纯函数） |
| 任务创建+派发 | `create_task_from_transcript_async(device_id, text, entrypoint=…)` → Redis 队列 → 设备 WS | ✅ 已有 |
| 任务入口 | `POST /device/v1/app/devices/{id}/tasks`（capability: draw_generated/write_text 等） | ✅ 已有 |
| 实时语音 WS | `WS /v1/voice`（VAD→ASR→LLM→TTS）+ `/v1/voice/ticket` | ⚠️ 有但是完整对话管道，不返回结构化意图 |
| **REST 一次性转写** | — | ❌ **不存在，需新增** |

**小程序端唯一真空白**：
- 无 `uni.getRecorderManager`（无录音）
- 无 ASR 调用
- 无语音指令 UI

**小程序端已有可复用**：
- `v2SubmitTask(deviceId, capability, params)` — 任务派发
- 设备状态 WS、alova + JWT 鉴权、麦克风权限脚手架（`scope.record` 已声明）

### 1.3 为什么是现在做

瘦身已完成（手机号鉴权清理、文档去重、固件 WiFi 关闭），基线更干净。在清理过的基线上加功能，认知负担更小。

---

## 二、已确认的设计决策（与用户协商）

| 决策点 | 选择 |
|--------|------|
| 语音交互模式 | **两者都要**：按住说话（MVP）+ 实时流（迭代） |
| 意图路由 | **自动路由 + 可确认**：`resolve_voice_task` 解析后展示给用户确认 |
| 设备选择 | **确认对话框里改**：默认上次设备，可改 |
| 错误恢复 | **可编辑可重派**：识别后可编辑文本/改意图/改设备 |

---

## 三、架构（复用优先，最小新增）

```
小程序 (manager-mobile)
  ├─ 按住说话: uni.getRecorderManager → 录 WAV → 上传 →
  │    POST /device/v1/app/voice/transcribe →
  │    返回 {text, intent:{capability,params,explanation}} →
  │    确认对话框（可编辑文本/改设备/改意图）→
  │    v2SubmitTask → 现有 Redis 队列 → 设备 WS
  │
  └─ 实时流: uni.connectSocket → 边说边显示转写 →
       松开发派 → 同一确认对话框

后端 (D:\QWEN3.0) — 2 个新薄端点
  ├─ POST /device/v1/app/voice/transcribe  [新]
  │     薄包装: get_asr_provider().transcribe(bytes) + resolve_voice_task(text)
  │     鉴权: device-app JWT (device_logic.auth.authorize)
  │     入参: 音频文件 (multipart) 或 base64
  │     返回: {text, intent:{capability,params,source,explanation}}
  │
  └─ POST /device/v1/app/voice/ticket      [新]
        薄包装: 复用 ws_ticket 机制，给小程序实时流用
        鉴权: device-app JWT
        返回: {ticket, expires_in:30}

(现有复用，零改动)
  - device_voice.get_asr_provider()        → ASR 转写
  - device_gateway.intent.resolve_voice_task(text)  → 意图解析
  - v2SubmitTask → create_task_from_transcript_async → Redis 队列 → 设备 WS
  - /v1/voice WS（实时流，已存在，复用 ticket 机制）
```

---

## 四、里程碑

### M0 — 后端语音薄端点（1 天，TDD）

**新增文件**：`routes/device_app_voice.py`（prefix `/device/v1/app`）

**端点 1**：`POST /device/v1/app/voice/transcribe`
- 鉴权：`authorize(authorization)`（device-app JWT，复用现有）
- 入参：`UploadFile`（WAV/PCM 音频，≤30s）+ 可选 `device_id`
- 逻辑：
  1. 读取音频 bytes
  2. `text = await get_asr_provider().transcribe(audio_bytes, sample_rate=16000)`
  3. `intent = resolve_voice_task(text)` （同步纯函数，零成本）
  4. 返回 `{text, intent}`，**不创建任务**（前端确认后才派发）
- 错误处理：ASR 失败返回明确错误（不静默降级，符合硬规则）；音频过大/格式错误返回 400

**端点 2**：`POST /device/v1/app/voice/ticket`
- 鉴权：`authorize(authorization)`
- 逻辑：复用 `ws_ticket.issue()`
- 返回：`{ticket, expires_in: 30}`
- 用途：小程序实时流模式连 `/v1/voice` WS 时用

**TDD**：
- 先写测试：`tests/test_device_app_voice.py`
- 测：正常转写 + 意图解析、ASR 失败错误、未鉴权 401、音频过大 400、空音频 400
- mock `get_asr_provider`（不依赖真实 ASR 服务）

**注册**：在 `routes/route_registry.py` 的 `_DEVICE_APP_ROUTERS` 加 `("routes.device_app_voice", "device_app_voice")`

**验收**：`pytest tests/test_device_app_voice.py` 全绿；`ruff check`；文件 ≤300 行

### M1 — 小程序按住说话模式（1.5 天）

**新增**：
- `src/api/voice/voice.ts` — `transcribeAudio(filePath)` → POST `/device/v1/app/voice/transcribe`
- `src/composables/useVoiceCommand.ts` — 录音管理（`uni.getRecorderManager`）+ 调用转写 + 状态管理
- `src/pages/voice-command/index.vue` 或集成进现有 `device-detail` 页 — 语音按钮 + 确认对话框

**确认对话框**（核心安全设计，你选的"可编辑可重派"+"确认对话框里改设备"）：
- 显示：识别文本（可编辑）、解析意图（如"绘图机 · 画：一只猫"）、目标设备（可改）
- 操作：一键切换绘图机↔写字机、确认派发、重新录音、取消
- 派发：调用现有 `v2SubmitTask(deviceId, intent.capability, intent.params)`

**权限处理**：复用 `privacy-permissions.vue` 的 `requestMicrophonePermission`；首次录音前检查 `scope.record`

**复用**：
- 鉴权：alova 自动带 JWT
- 任务派发：`v2SubmitTask`（现有）
- 设备选择：复用现有设备列表逻辑
- UI：wot-design-uni 组件 + 现有 CSS 变量主题

**验收**：按住说话 → 转写 → 确认 → 派发 绘图机/写字机 端到端；type-check 通过

### M2 — 小程序实时流模式（1.5 天）

**新增**：
- 实时流逻辑加入 `useVoiceCommand`（模式切换：按住说话 / 实时流）
- `requestVoiceTicket()` → POST `/device/v1/app/voice/ticket` → 拿 ticket
- `uni.connectSocket` 连 `/v1/voice?ticket=…`，推送 PCM 帧
- 边说边显示转写（接收 WS 的 transcript 帧）
- 松开 → 用最终转写文本走 M1 的同一确认对话框

**复杂点**：
- 小程序录音分块：`getRecorderManager` 的 `onFrameRecorded` 回调（需 `frameSize` 设置）
- WS 维护：重连、心跳、错误处理（复用 `useDeviceWebSocket` 的模式）
- `/v1/voice` 是完整对话管道（VAD→ASR→LLM→TTS），实时流模式只用其 ASR 阶段，忽略 LLM/TTS 输出

**验收**：实时流 → 边说边显 → 松开发派 → 确认 → 派发 端到端

---

## 五、关键技术决策

1. **音频格式**：
   - 按住说话：WAV（小程序 `getRecorderManager` 默认支持，含 header，各 ASR provider 都接受）
   - 实时流：PCM 16kHz/16bit/mono（`/v1/voice` 现有约定）

2. **意图解析端到端**：`/transcribe` 不只返回文字，还返回已解析的 `intent`。前端零解析逻辑，只做展示+编辑。

3. **安全边界**（不可删除）：
   - device-app JWT 鉴权（`authorize`）
   - 音频大小限制（按住说话 ≤30s，实时流靠 VAD）
   - 复用现有 `DANGEROUS_CAPABILITIES` 黑名单（intent.py 已内置）
   - 意图→派发走现有 `create_task_from_transcript_async`，safety/path 校验照常
   - 确认对话框是最后一道人工关卡（你选的"可确认"）

4. **遵循 ECC 工作流**：TDD（M0 先写测试）→ focused → full test → ruff + pyright + check_code_size → 文档同步 → conventional commit。

---

## 六、与现有系统的关系

- **不改动**：`device_voice/`、`device_gateway/intent.py`、`task_creation.py`、Redis 队列、设备 WS、现有任务端点
- **新增**：1 个后端路由文件（2 端点）+ 小程序若干文件
- **与瘦身的衔接**：瘦身清掉了手机号鉴权（P2-16），语音端点用微信 JWT 鉴权，不受影响

---

## 七、风险

| 风险 | 缓解 |
|------|------|
| ASR provider 在生产未配置（FunASR 需要模型） | M0 测试 mock；部署前确认 `LIMA_VOICE_ASR_PROVIDER` 配置 |
| 小程序录音权限被拒 | 友好引导到设置页（复用 privacy-permissions） |
| `/v1/voice` 实时流管道过重（跑 LLM/TTS） | M2 只取 ASR 阶段；若性能问题，后续考虑专用轻量 WS |
| 意图误识别直接驱动物理机器 | 确认对话框强制人工确认（不可跳过） |

---

## 八、验收标准

**M0 完成**：
- [ ] `POST /device/v1/app/voice/transcribe` 返回 `{text, intent}`
- [ ] `POST /device/v1/app/voice/ticket` 返回 `{ticket, expires_in}`
- [ ] `pytest tests/test_device_app_voice.py` 全绿
- [ ] `ruff check`；文件 ≤300 行

**M1 完成**：
- [ ] 按住说话 → 转写 → 确认对话框 → 派发 绘图机 端到端
- [ ] 按住说话 → 转写 → 确认对话框 → 派发 写字机 端到端
- [ ] 确认对话框可编辑文本、改设备、切绘图机↔写字机
- [ ] type-check 通过

**M2 完成**：
- [ ] 实时流 → 边说边显 → 松开发派 → 确认 → 派发 端到端
- [ ] 复用 M1 确认对话框
