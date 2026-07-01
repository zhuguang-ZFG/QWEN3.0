# 小程序语音控制绘图机/写字机 —— 执行级设计文档

- **日期**: 2026-07-02
- **状态**: 已完成（M0+M1+M2 全部实施、部署、上传）
- **执行结果**：后端端点已部署京东云主生产节点（公网冒烟 401/422 通过）；小程序 v3.8.0 已构建并上传微信平台；自检修复 4 个 bug（frameSize 单位/错误信息泄漏/意图一致性/死代码）。待办见 `2026-07-02-backlog-planning.md`。
- **未验证**：真机端到端（真实录音→ASR→派发物理设备）尚未验证（见 backlog P0-3）。
- **前置**: 系统瘦身已完成（`2026-07-02-system-slimdown-design.md`），基线已清理
- **范围**: 小程序端补齐语音交互，驱动绘图机（draw_generated）和写字机（write_text）
- **读者**: 实施 agent。本文档自包含，无需额外上下文。

---

## 一、需求

用户通过小程序，用**语音控制**让绘图机绘图、写字机写字：
- "画一只猫" → 绘图机 draw_generated
- "写你好世界" → 写字机 write_text
- "归零" → 设备 home

## 二、已确认决策

| 决策点 | 选择 |
|--------|------|
| 语音交互模式 | **两者都要**：按住说话（M1）+ 实时流（M2） |
| 意图路由 | **自动路由 + 可确认**：`resolve_voice_task` 解析后展示给用户确认 |
| 设备选择 | **确认对话框里改**：默认上次设备，可改 |
| 错误恢复 | **可编辑可重派**：识别后可编辑文本/改意图/改设备 |

## 三、现状基线（2026-07-02 核实，258 语音测试通过）

**后端已有（零改动复用）**：

| 能力 | 位置 | 签名 |
|------|------|------|
| ASR 转写 | `device_voice.get_asr_provider()` | 返回 `ASRProvider`，其 `async transcribe(audio_data: bytes, *, sample_rate=16000) -> str` |
| 意图解析 | `device_gateway.intent.resolve_voice_task` | `def resolve_voice_task(text: str) -> dict[str, Any]`（**同步**，非 async） |
| 任务创建+派发 | `device_gateway.task_creation.create_task_from_transcript_async` | `async def (device_id, text, request_id=None, *, source=None, entrypoint=None) -> dict` |
| 任务入口 | `POST /device/v1/app/devices/{id}/tasks` | 现有路由，capability: draw_generated/write_text/home 等 |
| 鉴权 | `device_logic.auth.authorize` | `def authorize(authorization: str) -> dict[str, Any] | JSONResponse` |
| WS ticket | `ws_ticket.issue()` / `ws_ticket.TTL_SECONDS=30` | 单次使用 |

**resolve_voice_task 返回结构**：
```python
{
    "capability": "draw_generated" | "write_text" | "home" | "move_abs" | ...,
    "params": {"prompt": "一只猫"} | {"text": "你好"} | {},
    "source": "voice",
    "explanation": "pattern matched: draw_generated"
}
```

**缺口（本 spec 新增）**：
- 后端无 REST 一次性转写端点（只有 WS `/v1/voice` 完整对话管道）
- 小程序无录音、无 ASR 调用、无语音指令 UI

---

## 四、架构

```
按住说话:  getRecorderManager → WAV → 上传 →
           POST /device/v1/app/voice/transcribe →
           {text, intent} → 确认对话框 → v2SubmitTask → Redis → 设备 WS

实时流:    /voice/ticket → connectSocket(/v1/voice) →
           边说边显 transcript → 松开 → 确认对话框 → v2SubmitTask
```

**后端新增 1 文件 2 端点，其余全部复用。**

---

## 五、M0 — 后端语音薄端点（TDD，1 天）

### 5.1 新增文件：`routes/device_app_voice.py`

```python
"""Device app voice routes — ASR transcription + intent resolution (slimdown-adjacent).

薄包装现有 device_voice.get_asr_provider() 和 device_gateway.intent.resolve_voice_task。
不创建任务（前端确认后才派发）。
"""
```

**prefix**：`/device/v1/app`（与其他 device_app 路由一致）

**端点 1**：`POST /device/v1/app/voice/transcribe`

- 鉴权：`authorize(authorization)` — 未通过返回 401
- 入参：`UploadFile`（字段名 `audio`，WAV 格式，≤30s）+ 可选 `device_id`（仅记录用）
- 逻辑：
  1. 读 `audio_data = await file.read()`
  2. 大小校验：> `MAX_AUDIO_BYTES`（建议 5MB，约 30s 16kHz 16bit）返回 413
  3. **WAV→PCM**：若以 RIFF header 开头，剥掉 44 字节 header 取 PCM；否则按 raw PCM 处理
     - ⚠️ 关键：`ASRProvider.transcribe` 期望 **raw PCM 16-bit signed LE mono**，不是 WAV。直接传 WAV 会乱码。
     - 实现参考：`device_voice.audio_stream.pcm_to_wav` 的逆操作，或简单判断 `data[:4] == b'RIFF'` 则 `data[44:]`
  4. `text = await get_asr_provider().transcribe(pcm_data, sample_rate=16000)`
  5. `intent = resolve_voice_task(text)` — 同步调用，无需 await
  6. 返回 `{"text": text, "intent": intent}`
- 错误处理（不静默降级，符合 AGENTS.md 硬规则）：
  - ASR 抛异常 → `logger.warning(...)` + 返回 503 `{"message": "ASR failed: ..."}`
  - 空音频 → 400
  - 未鉴权 → 401

**端点 2**：`POST /device/v1/app/voice/ticket`

- 鉴权：`authorize(authorization)`
- 逻辑：`ticket = ws_ticket.issue()`
- 返回：`{"ticket": ticket, "expires_in": ws_ticket.TTL_SECONDS}`
- 用途：小程序实时流连 `/v1/voice?ticket=…` WS

### 5.2 路由注册

**改 `routes/route_registry.py`**：在 `_DEVICE_APP_ROUTERS` 列表加：
```python
("routes.device_app_voice", "device_app_voice"),
```
位置：紧跟 `("routes.device_app_gallery", "device_app_gallery")` 之后。

### 5.3 TDD — 先写测试：`tests/test_device_app_voice.py`

用 `tests/device_app_helpers.py` 的 `client` fixture（已包含完整 device_app 路由 + 内存任务存储）。**注意**：该 helper 的 `client()` 目前**没有 include voice router**，需在其 import 块加：
```python
from routes.device_app_voice import router as voice_router
# ...并在 app.include_router 序列里加
app.include_router(voice_router)
```
（否则测试 client 不挂载新路由）

**mock ASR provider**（不依赖真实 ASR 服务）：
```python
@pytest.fixture
def mock_asr(monkeypatch):
    async def fake_transcribe(audio_data, *, sample_rate=16000):
        return "画一只猫"
    monkeypatch.setattr(device_app_voice, "get_asr_provider",
                        lambda: types.SimpleNamespace(transcribe=fake_transcribe))
```
（或在 `routes/device_app_voice.py` 里 import `get_asr_provider as _get_asr`，测试 patch 该模块级别名）

**测试用例清单**（每条一个 test 函数）：
1. `test_transcribe_draw_intent` — 上传 WAV（fake），mock ASR 返回"画一只猫" → 200，`intent.capability == "draw_generated"`
2. `test_transcribe_write_intent` — mock ASR 返回"写你好" → `intent.capability == "write_text"`
3. `test_transcribe_home_intent` — mock ASR 返回"归零" → `intent.capability == "home"`
4. `test_transcribe_unauthorized` — 无 Authorization header → 401
5. `test_transcribe_empty_audio` — 空文件 → 400
6. `test_transcribe_oversized_audio` — > MAX_AUDIO_BYTES → 413
7. `test_transcribe_asr_failure` — mock ASR 抛异常 → 503，且 response 含错误信息
8. `test_transcribe_strips_wav_header` — 上传带 RIFF header 的数据，验证传给 ASR 的是剥掉 header 的 PCM（可通过 fake_transcribe 捕获 audio_data 验证其不以 `b'RIFF'` 开头）
9. `test_voice_ticket_returns_ticket` — 200，`ticket` 非空，`expires_in == 30`
10. `test_voice_ticket_unauthorized` — 401

**WAV 测试数据生成**：构造 44 字节 fake header + 少量 PCM：
```python
def _fake_wav(payload: bytes = b"\x00\x00" * 160) -> bytes:
    return b"RIFF" + b"\x00" * 36 + b"data" + len(payload).to_bytes(4, "little") + payload
    # 简化：ASR 被 mock，header 字段值不影响
```

### 5.4 验收

- [ ] `pytest tests/test_device_app_voice.py -v` 10 测试全绿
- [ ] `ruff check routes/device_app_voice.py tests/test_device_app_voice.py`
- [ ] `routes/device_app_voice.py` ≤ 300 行（目标 ~100 行，是薄包装）
- [ ] `tests/device_app_helpers.py` 的 `client()` 已 include voice router
- [ ] `routes/route_registry.py` 已加注册

---

## 六、M1 — 小程序按住说话（1.5 天）

小程序根目录：`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`

### 6.1 新增/改动文件

| 文件 | 动作 | 内容 |
|------|------|------|
| `src/api/voice/voice.ts` | 新增 | `transcribeAudio(filePath)` + `requestVoiceTicket()` |
| `src/composables/useVoiceCommand.ts` | 新增 | 录音管理 + 转写 + 状态机 |
| `src/pages/v2/device-detail/components/voice-command.vue` | 新增 | 语音按钮 + 确认对话框组件 |
| `src/pages/v2/device-detail/index.vue` | 改 | 挂载 voice-command 组件（与现有 write-draw-panel 并列） |
| `src/i18n/zh_CN.ts`（+ 其他 locale） | 改 | 加 `voice.*` 键 |

### 6.2 API 封装：`src/api/voice/voice.ts`

```typescript
import http from '@/http/request/alova'

export interface VoiceIntent {
  capability: 'draw_generated' | 'write_text' | 'home' | string
  params: Record<string, unknown>
  source: string
  explanation: string
}

export interface TranscribeResult {
  text: string
  intent: VoiceIntent
}

// 按住说话：上传录音文件 → 转写 + 意图
export function transcribeAudio(filePath: string): Promise<TranscribeResult> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${getEnvBaseUrl()}/device/v1/app/voice/transcribe`,
      filePath,
      name: 'audio',
      header: { Authorization: getBearerToken() },
      success: (res) => {
        const data = JSON.parse(res.data).data
        resolve(data)
      },
      fail: reject,
    })
  })
}

// 实时流：换取 WS ticket
export function requestVoiceTicket(): Promise<{ ticket: string; expires_in: number }> {
  return http.Post('/device/v1/app/voice/ticket')
}
```

**注意 auth**：`transcribeAudio` 用 `uni.uploadFile` 绕过 alova，需手动带 `Authorization: getBearerToken()`（参考 `src/hooks/useUpload.ts` 的做法，`src/utils/uploadFile.ts` 不带 header）。`getBearerToken` 在 `src/utils/index.ts:48`，`getEnvBaseUrl` 在 `src/utils/index.ts:167`。

### 6.3 Composable：`src/composables/useVoiceCommand.ts`

状态机：`idle → recording → transcribing → confirming → dispatching → idle`

```typescript
import { ref } from 'vue'
import { transcribeAudio, type TranscribeResult } from '@/api/voice/voice'

export function useVoiceCommand() {
  const status = ref<'idle' | 'recording' | 'transcribing' | 'confirming' | 'dispatching'>('idle')
  const result = ref<TranscribeResult | null>(null)
  const errorMsg = ref('')
  const recorder = uni.getRecorderManager()

  function startRecording() {
    // 权限检查：调用 requestMicrophonePermission（privacy-permissions.vue:112 的模式）
    recorder.start({ format: 'wav', sampleRate: 16000, numberOfChannels: 1, frameSize: 0 })
    status.value = 'recording'
  }

  async function stopRecording() {
    status.value = 'transcribing'
    recorder.stop()  // 触发 onStop
  }

  recorder.onStop(async (res) => {
    try {
      result.value = await transcribeAudio(res.tempFilePath)
      status.value = 'confirming'
    } catch (e) {
      errorMsg.value = '转写失败，请重试'
      status.value = 'idle'
    }
  })

  // 确认对话框的"确认派发"调用现有 v2SubmitTask
  async function confirm(deviceId: string) {
    status.value = 'dispatching'
    const { intent } = result.value!
    await v2SubmitTask(deviceId, intent.capability, intent.params)
    status.value = 'idle'
  }

  return { status, result, errorMsg, startRecording, stopRecording, confirm }
}
```

**权限处理**：录音前检查 `scope.record`（参考 `src/pages/settings/privacy-permissions.vue:112` 的 `requestMicrophonePermission`）。被拒则引导到设置页。

### 6.4 确认对话框组件

`src/pages/v2/device-detail/components/voice-command.vue`（核心安全设计）：

UI 结构（用 wot-design-uni + CSS 变量，深色主题）：
- **识别文本**：`<wd-input>` 可编辑（用户可纠正 ASR 错误）
- **解析意图**：显示"绘图机 · 画：一只猫"或"写字机 · 写：你好"，带说明
- **目标设备**：`<wd-picker>` 选设备（默认当前设备，可改）
- **一键切换**：按钮在 draw_generated ↔ write_text 间切换（修正误判）
- **操作**：确认派发 / 重新录音 / 取消

**派发**：用户编辑文本后，若改了文本需重新解析意图（可选：调一个轻量 `/voice/parse` 或前端简单规则）。MVP：编辑文本不重新解析，直接用原 intent.capability + 新文本作为 params。

**挂载**：在 `device-detail/index.vue` 加一个语音按钮区，点击弹确认对话框；或常驻一个"按住说话"按钮。

### 6.5 验收

- [ ] 按住按钮说话 → 松开 → 转写显示 → 确认 → 绘图机执行
- [ ] 同上 → 写字机执行
- [ ] 确认对话框可编辑文本、改设备、切绘图机↔写字机
- [ ] 麦克风权限被拒有友好引导
- [ ] `npx vue-tsc --noEmit` 0 errors

---

## 七、M2 — 小程序实时流（1.5 天）

### 7.1 复用 `/v1/voice` WS（已存在）

`/v1/voice` 是完整对话管道（VAD→ASR→**LLM→TTS**）。实时流模式**只用 ASR 阶段**，忽略 LLM/TTS 输出帧。

### 7.2 实现要点

- `requestVoiceTicket()` → 拿 ticket
- `uni.connectSocket({ url: getEnvBaseUrl().replace('https','wss') + '/v1/voice?ticket=…' })`
- 录音分块：`recorder.start({ format: 'pcm', sampleRate: 16000, frameSize: 1280 })` + `onFrameRecorded` 回调推送 PCM 帧
- 接收 WS 消息：`{type: "transcript"}` 帧 → 更新实时显示文本
- 松开 → 用最终 transcript 走 M1 的确认对话框

### 7.3 复杂点

- **小程序录音分块**：`getRecorderManager.onFrameRecorded` 需设 `frameSize`，格式选 `pcm`
- **WS 生命周期**：重连、心跳、错误处理 —— 复用 `src/pages/v2/device-detail/composables/useDeviceWebSocket.ts` 的模式
- **忽略无关帧**：`/v1/voice` 会返回 `reply`（TTS）等帧，实时流模式只取 `transcript`

### 7.4 验收

- [ ] 实时流 → 边说边显 → 松开 → 确认对话框 → 派发
- [ ] 复用 M1 确认对话框
- [ ] WS 断线有重连

---

## 八、安全边界（不可删除）

- device-app JWT 鉴权（`authorize`）— 两端点都要
- 确认对话框是**强制人工关卡**（不可跳过）—— 避免误识别驱动物理机器
- 复用 `DANGEROUS_CAPABILITIES` 黑名单（`device_gateway/intent.py:38`，spindle_on/laser_on 等永远不会被 `resolve_voice_task` 返回）
- 意图→派发仍走现有 `create_task_from_transcript_async`，所有 safety/path 校验照常
- 音频大小限制（≤5MB / ~30s）
- 不静默降级（ASR 失败明确报错）

## 九、遵循的工作流（ECC）

- **先计划**（本文档）→ 用户批准
- **TDD**：M0 先写 10 个测试 → 实现 → GREEN
- **提交前**：focused test → full test → `ruff check .` → `pyright`（改动的 .py）→ `scripts/check_code_size.py` → 文档同步
- **conventional commits**：`feat(voice): ...`、`feat(miniprogram): ...`
- **仅暂存相关文件**

## 十、风险

| 风险 | 缓解 |
|------|------|
| ASR provider 生产未配置（FunASR 需模型） | M0 测试全 mock；部署前确认 `LIMA_VOICE_ASR_PROVIDER` |
| 小程序录音权限被拒 | 友好引导到设置页（复用 privacy-permissions 模式） |
| `/v1/voice` 实时流管道过重 | M2 只取 ASR；若慢，后续考虑专用轻量 WS |
| 意图误识别 | 确认对话框强制人工确认（不可跳过） |
| WAV/PCM 格式混淆导致乱码 | M0 必须剥 WAV header（见 5.1 步骤 3），测试用例 8 验证 |

## 十一、环境变量

新增端点无新环境变量。依赖现有：
- `LIMA_VOICE_ASR_PROVIDER`（默认 funasr）— 决定 ASR 后端
- `LIMA_JWT_SECRET` — JWT 签名（鉴权用）
- ASR provider 各自的配置（见 `device_voice/providers/`）

## 十二、验收总表

**M0**：10 测试全绿；ruff；文件 ≤300 行；路由注册；helper include
**M1**：按住说话→绘图机/写字机端到端；确认对话框可编辑/改设备/切换；type-check 0 error
**M2**：实时流→边说边显→松开→派发；复用 M1 对话框；WS 重连
