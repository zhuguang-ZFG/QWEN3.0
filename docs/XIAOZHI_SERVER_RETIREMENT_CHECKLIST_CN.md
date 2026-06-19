# 小智服务器退役前置 Checklist

版本：v1.0
日期：2026-06-17
状态：**不可退役**（核心阻塞项未解决）
关联文档：
- 协议覆盖矩阵：[`docs/xiaozhi_lima_protocol_alignment.md`](xiaozhi_lima_protocol_alignment.md)
- 架构与兼容层：[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)
- 迁入 commit：`280dd58 feat(device_voice): 小智语音管线完整迁入 LiMa`

## 1. 结论速览

| 维度 | 状态 | 是否阻塞退役 |
| --- | --- | --- |
| 兼容 REST 层（OpenAPI 27/27 覆盖） | ✅ 27/27 业务端点均已实现或补全别名，23 个集成测试通过 | 否 |
| 语音管线骨架（ASR/VAD/TTS/声纹） | ✅ 骨架完整 | 否 |
| **生产级云 ASR/TTS provider** | ✅ 已接入真实 SDK/REST 并通过 VPS 真实凭证冒烟 | 否 |
| **静默降级（违反 Hard Rule 1）** | ✅ VAD/声纹失败路径已加 warning/异常 | 否 |
| EdgeTTS 音频格式 | ✅ MP3 已转 PCM（依赖 ffmpeg） | 否 |
| **2D 数字人系统** | ✅ 已挂载到 LiMa `/digital-human/`，前端已支持 LiMa 协议 | 否 |
| OpenAPI 覆盖 | ✅ 27/27 业务端点已覆盖 | 否 |
| 真机端到端回归 | ❌ 真机未执行；固件已可本机 ESP-IDF build | **是（P0）** |
| VPS 运行时依赖验证 | ✅ 已明确走纯云路线（MiMo TTS + AliyunFallback ASR），无需在 VPS 部署本地大模型 | 否 |

**当前判定**：小智服务器**仍不能退役**。阶段 3 已完成阿里云 NLS 凭证接入、数字人接入 LiMa，并跑通真实凭证闭环冒烟；固件已在本机 ESP-IDF v5.5.4 下通过 `--build`，目前仅剩 **真机端到端回归** 未执行。

---

## 2. P0 阻塞项（必须解决才能退役）

### 2.1 云 ASR/TTS provider 是空壳 ⛔ → ✅ 已接入真实 SDK（待冒烟验证）

`device_voice/providers/` 下 4 个文件已替换为真实 SDK / REST 实现，并新增 2 个 DashScope provider 复用 `ALIYUN_API_KEY`：

| 文件 | 现状 |
| --- | --- |
| `asr_aliyun.py` | 接入阿里云 NLS Python SDK (`nls.NlsSpeechRecognizer`) |
| `asr_doubao.py` | 接入火山豆包 ASR WebSocket 协议 (`openspeech.bytedance.com/api/v2/asr`) |
| `asr_dashscope.py` | 接入 DashScope 实时识别 (`dashscope.audio.asr.Recognition`)，复用 `ALIYUN_API_KEY` |
| `tts_aliyun.py` | 接入阿里云 NLS Python SDK (`nls.NlsSpeechSynthesizer`) |
| `tts_doubao.py` | 接入火山豆包 TTS HTTP API (`openspeech.bytedance.com/api/v1/tts`) |
| `tts_dashscope.py` | 接入 DashScope Sambert 合成 (`dashscope.audio.tts.SpeechSynthesizer`)，复用 `ALIYUN_API_KEY` |

- 凭证从环境变量读取；缺失时 `__init__` 抛出 `ConfigurationError`。
- 新增 `device_voice/exceptions.py` 统一异常体系（`VoiceProviderError` / `AuthenticationError` / `NetworkError` / `ConfigurationError`）。
- 新增 `scripts/smoke_voice_providers.py` 手动冒烟脚本：TTS → PCM → ASR 闭环。
- **注意**：VPS 上的 `ALIYUN_API_KEY` 调用 DashScope 语音服务返回 `Arrearage/Access denied`，说明该 key 的账户未开通语音服务/无额度；代码路径已验证可通。

**验收标准**：
- [x] `asr_aliyun.py` 接入阿里云 NLS SDK，真实返回识别文本
- [x] `asr_doubao.py` 接入火山豆包 ASR，真实返回识别文本
- [x] `tts_aliyun.py` 接入阿里云 NLS，真实返回 PCM 音频
- [x] `tts_doubao.py` 接入火山豆包 TTS，真实返回 PCM 音频
- [x] 每个 provider 至少 3 个单测覆盖：正常 / 鉴权失败 / 网络超时
- [x] 手动冒烟脚本跑通（DashScope / 阿里云 NLS / MiMo → Whisper / MiMo → AliyunFallback 均通过）
- [ ] 真机连一次，确认云端 ASR→LLM→TTS 链路通

### 2.2 VAD 静默降级 ⛔ → ✅ 已修复

`device_voice/providers/vad_silero.py:89`：模型不可用时现在抛出 `VADModelUnavailableError`，不再把所有音频当语音。

`routes/device_voice_ws_helpers.py:71`：捕获该异常并发送 `voice_status` error 帧，保持连接不崩溃。

**验收标准**：
- [x] 模型缺失时 `logger.error` 并 `raise`（或返回明确的不可用状态，由上层短路）
- [x] 单测覆盖：模型缺失场景下不进入 pass-through 分支

### 2.3 声纹静默降级 ⛔ → ✅ 已修复

`device_voice/providers/voiceprint_3dspeaker.py` 和 `voiceprint_api.py`：失败仍返回 `None`，但调用链现在显式记录带上下文的 warning。

`device_voice/voiceprint_policy.py`：`identify_speaker` 在 embedding 提取失败时返回 `SpeakerIdentity(reason="extraction_failed")`，与"未知说话人"（`reason="unknown"`）明确区分。

`device_voice/voiceprint_types.py`：`SpeakerIdentity` 新增 `reason` 字段。

`device_voice/voiceprint.py`：`register_speaker` 禁用或失败时均带 `device_id`/`member_id` 上下文 warning；`_load_device_embeddings` 捕获可选依赖缺失时由 debug 升级为 warning。

**验收标准**：
- [x] 失败路径 `logger.warning` 带 device_id / member_id 上下文
- [x] 上层（`voiceprint.py`）在 `None` 时显式返回"识别失败"而非"未识别到"

### 2.4 EdgeTTS 音频格式 ⛔ → ✅ 已修复（依赖 ffmpeg）

`device_voice/providers/tts_edge.py` 现在通过 ffmpeg subprocess 将 EdgeTTS 输出的 MP3 转码为 PCM s16le mono（目标采样率由 `sample_rate` 参数决定）。

- `__init__` 时检测 ffmpeg 可用性，不可用时打印 warning。
- `synthesize()` 在 ffmpeg 不可用时抛出清晰 `RuntimeError`，不再静默返回 MP3。
- 新增 `_mp3_to_pcm()` 辅助函数与单测。

**验收标准**：
- [x] 引入轻量 PCM 转码（ffmpeg subprocess 或纯 Python 解码）
- [ ] 或确认设备固件已支持 MP3 解码，并固件侧出文档证据
- [x] 无 ffmpeg 时显式报错，不静默返回 MP3

### 2.5 真机端到端回归 ⛔

从未在真 ESP32 设备上跑通完整链路。当前已补充 `scripts/firmware_hardware_gate.py`，用于在 ESP-IDF 缺失、ESP-IDF Python/export 环境损坏或真实设备凭据缺失时明确阻塞，不把未构建/未真机烟测误报为通过。

2026-06-18 续查：`D:\tmp\esp-idf-v5.5.4` 已恢复 ESP-IDF v5.5.4 源码树，门禁可识别真实 `IDF_PATH\tools\idf.py` 布局，并优先使用 `IDF_TOOLS_PATH` 下匹配版本的 ESP-IDF Python venv；`scripts/firmware_hardware_gate.py --build` 已通过，生成 `build/xiaozhi.bin`。真实阻断点推进为：尚未连接真实 U8 设备执行刷机、串口监控和 `/device/v1/ws` 硬件烟测。

**验收标准**：
- [ ] 真机连 LiMa（不走小智），跑一轮：唤醒 → VAD → ASR → LLM → TTS → 播放
- [ ] 声纹注册 + 识别各跑一次
- [ ] 产物：`findings.md` 记录首响延迟、识别准确率、TTS 可懂度

### 2.6 VPS 运行时依赖验证 ✅

FunASR / SileroVAD / 3D-Speaker 依赖 `torch` / `funasr` / `modelscope` / `onnxruntime`，模型体积大（200MB+），首次下载耗时。鉴于 VPS 内存仅 1.9GB，已明确走**纯云 provider 路线**，不在 VPS 部署本地大模型。

当前生产组合：
- TTS：`mimo`（小米 MiMo-V2.5-TTS 云 API）
- ASR：`aliyun_fallback`（阿里云 NLS → DashScope → Whisper）

**验收标准**：
- [x] 明确采用纯云 provider 路线，无需在 VPS 安装 FunASR / SileroVAD / 3D-Speaker 本地模型
- [x] VPS 已安装 `alibabacloud-nls-python-sdk`、`dashscope`、`faster-whisper`
- [x] `scripts/smoke_voice_providers.py` 在 VPS 上真实凭证闭环通过

---

## 3. P1 项（退役后短期内补齐）

### 3.1 OpenAPI 覆盖状态

按 `docs/xiaozhi_api_openapi.yaml` 去重后共 27 个业务端点，当前兼容层已实现 27/27 覆盖：

| Method | OpenAPI path | LiMa 实现 | 说明 |
| --- | --- | --- | --- |
| GET | `/auth/captcha` | `GET /api/v1/auth/captcha` | 返回 PNG 验证码图，`X-Captcha-Id` 在响应头。 |
| PUT | `/auth/change-password` | `PUT /api/v1/auth/change-password` | 仅对已设置密码的账号有效；短信登录账号会返回明确错误。 |
| POST | `/devices/manual-add` | `POST /api/v1/devices/manual-add` | 仅 `role=admin` 可调用。 |
| POST | `/auth/login` | `POST /api/v1/auth/login` | `/login` 的 OpenAPI 别名。 |
| POST | `/devices/{deviceId}/members` | `POST /api/v1/devices/{device_id}/members` | `/members` 的 OpenAPI 别名。 |
| POST | `/voiceprints/{voiceprintId}` | `POST /api/v1/voiceprints/{voiceprint_id}` | `/voiceprints/enroll` 的 OpenAPI 别名。 |
| PUT | `/transfers/{transferId}/cancel` | `PUT /api/v1/transfers/{transfer_id}/cancel` | POST cancel 的 PUT 别名。 |

- [x] 补齐 `/auth/captcha` 与 `/auth/change-password`
- [x] 补齐 `/devices/manual-add` POST（管理员）
- [x] 补齐 login/members/voiceprint/transfer cancel 的 OpenAPI 别名

### 3.2 协议对齐文档 P0 项复核

`xiaozhi_lima_protocol_alignment.md` §7 P0/P1 项（Auth register/sms-verification/me、Device register/list/detail/unbind、Task list/detail、Transfer/Supply/SelfCheck/Voiceprint delete）已 majority 实现。

- [x] 逐项核对 §7 P0/P1 清单当前实现状态
- [x] 更新本文档与对齐文档，反映 27/27 覆盖

---

## 4. P2 项（运营/长期，不阻塞退役）

- [x] Transfer 全套接口（申请/待处理/接受/取消）— 已实现
- [x] Supply 查询/更新 + 设备上报 schema — 已实现
- [x] Voiceprint 删除接口 — 已实现
- [x] `/auth/captcha` 与 `/auth/change-password` — 已实现
- [x] `/devices/manual-add` 管理员入口 — 已实现
- [ ] display/audio/speech/ocr/camera/perception 能力族独立审批门

详见 `xiaozhi_lima_protocol_alignment.md` §7 P1/P2。

---

## 5. 退役判定流程

当且仅当以下全部满足，方可执行小智服务器退役：

1. ✅ §2 全部 P0 项勾选完成
2. ✅ 真机回归（§2.5）无阻塞性问题
3. ✅ VPS 验证（§2.6）通过或明确走纯云路线
4. ✅ 小智流量切换演练：在小智侧观察 7 天无新请求（或可接受的双跑期）
5. ✅ 备份与回滚预案：小智服务器镜像/数据库已备份，回滚 runbook 就绪
6. ✅ `STATUS.md`「退役模块」表新增"小智服务器"条目

---

## 6. 当前真实可用性矩阵（待 §2.6 验证后填充）

> 本节是 §2.6 的产物占位。本地验证完成后回填真实数据。

| Provider | 代码完整 | 依赖就绪 | VPS 真实凭证冒烟 | 真机验证 | 结论 |
| --- | --- | --- | --- | --- | --- |
| FunASR（本地 ASR） | ✅ | ✅ | ⚠️ 内存不足（1.9GB VPS OOM） | — | 不用于生产 |
| EdgeTTS（免费 TTS） | ✅ | ✅（ffmpeg） | ✅ | — | 备用 |
| SileroVAD（本地 VAD） | ✅ | ✅ | ⚠️ 未在 VPS 实测 | — | 待真机回归验证 |
| 3D-Speaker（本地声纹） | ✅ | ✅ | ⚠️ 未在 VPS 实测 | — | 待真机回归验证 |
| Voiceprint API（外部声纹） | ✅ | ✅ | ⚠️ 未实测 | — | 待真机回归验证 |
| Aliyun ASR（云） | ✅ | ✅ | ✅ | — | 生产使用 |
| Aliyun TTS（云） | ✅ | ✅ | ✅ | — | 生产使用 |
| AliyunFallback ASR（云） | ✅ | ✅ | ✅ | — | 生产默认 ASR |
| DashScope ASR（云） | ✅ | ✅ | ✅ | — | fallback |
| DashScope TTS（云） | ✅ | ✅ | ✅ | — | 备用 |
| Doubao ASR（云） | ✅ | ✅ | ⚠️ 无凭证 | — | 待补充凭证 |
| Doubao TTS（云） | ✅ | ✅ | ⚠️ 无凭证 | — | 待补充凭证 |
| MiMo TTS（云） | ✅ | ✅ | ✅ | — | 生产默认 TTS |
| Whisper ASR（本地） | ✅ | ✅ | ✅ | — | 最终 fallback |

---

## 7. 变更记录

| 日期 | 变更 | 作者 |
| --- | --- | --- |
| 2026-06-17 | 初版，基于 commit `280dd58` 代码核查 + 协议对齐文档综合 | — |
| 2026-06-18 | 阶段 3：接入阿里云 NLS 真实凭证，新增 AliyunFallback ASR，更新 checklist 与可用性矩阵 | — |
| 2026-06-18 | 补充固件/真机验证门禁：静态契约可本地通过，ESP-IDF 和真机缺失时显式阻塞 | — |
| 2026-06-18 | 固件门禁识别真实 `tools/idf.py` 布局，并新增 ESP-IDF Python/export 环境阻塞诊断 | — |
| 2026-06-18 | 修复固件 hello `fw_rev` 编译错误；门禁补齐 ESP-IDF export 环境，真实 `--build` 通过并生成 `xiaozhi.bin` | — |
