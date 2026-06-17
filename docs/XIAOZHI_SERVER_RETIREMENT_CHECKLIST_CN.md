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
| 兼容 REST 层（OpenAPI 28/29） | ✅ 28/29 上线，13 集成测试通过 | 否（差 1 端点） |
| 语音管线骨架（ASR/VAD/TTS/声纹） | ✅ 骨架完整 | 否 |
| **生产级云 ASR/TTS provider** | ✅ **4 个已接入真实 SDK/REST** | 否（待冒烟验证） |
| **静默降级（违反 Hard Rule 1）** | ✅ VAD/声纹失败路径已加 warning/异常 | 否 |
| EdgeTTS 音频格式 | ✅ MP3 已转 PCM（依赖 ffmpeg） | 否 |
| OpenAPI 最后 1 端点 | ⚠️ 28/29 | 否（P1） |
| 真机端到端回归 | ❌ 未执行 | **是（P0）** |
| VPS 运行时依赖验证 | ❌ 未执行 | **是（P0）** |

**当前判定**：小智服务器**仍不能退役**。阶段 2 已完成云 ASR/TTS SDK 接入与单元测试，但尚未用真实凭证跑通冒烟脚本，真机端到端回归与 VPS 运行时验证也未执行。

---

## 2. P0 阻塞项（必须解决才能退役）

### 2.1 云 ASR/TTS provider 是空壳 ⛔ → ✅ 已接入真实 SDK（待冒烟验证）

`device_voice/providers/` 下 4 个文件已替换为真实 SDK / REST 实现：

| 文件 | 现状 |
| --- | --- |
| `asr_aliyun.py` | 接入阿里云 NLS Python SDK (`nls.NlsSpeechRecognizer`) |
| `asr_doubao.py` | 接入火山豆包 ASR WebSocket 协议 (`openspeech.bytedance.com/api/v2/asr`) |
| `tts_aliyun.py` | 接入阿里云 NLS Python SDK (`nls.NlsSpeechSynthesizer`) |
| `tts_doubao.py` | 接入火山豆包 TTS HTTP API (`openspeech.bytedance.com/api/v1/tts`) |

- 凭证从环境变量读取；缺失时 `__init__` 抛出 `ConfigurationError`。
- 新增 `device_voice/exceptions.py` 统一异常体系（`VoiceProviderError` / `AuthenticationError` / `NetworkError` / `ConfigurationError`）。
- 新增 `scripts/smoke_voice_providers.py` 手动冒烟脚本：TTS → PCM → ASR 闭环。

**验收标准**：
- [x] `asr_aliyun.py` 接入阿里云 NLS SDK，真实返回识别文本
- [x] `asr_doubao.py` 接入火山豆包 ASR，真实返回识别文本
- [x] `tts_aliyun.py` 接入阿里云 NLS，真实返回 PCM 音频
- [x] `tts_doubao.py` 接入火山豆包 TTS，真实返回 PCM 音频
- [x] 每个 provider 至少 3 个单测覆盖：正常 / 鉴权失败 / 网络超时
- [ ] 手动冒烟脚本跑通（依赖真实凭证）
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

从未在真 ESP32 设备上跑通完整链路。

**验收标准**：
- [ ] 真机连 LiMa（不走小智），跑一轮：唤醒 → VAD → ASR → LLM → TTS → 播放
- [ ] 声纹注册 + 识别各跑一次
- [ ] 产物：`findings.md` 记录首响延迟、识别准确率、TTS 可懂度

### 2.6 VPS 运行时依赖验证 ⛔

FunASR / SileroVAD / 3D-Speaker 依赖 `torch` / `funasr` / `modelscope` / `onnxruntime`，模型体积大（200MB+），首次下载耗时。VPS 是否装得下、首响延迟是否可接受，**均未验证**。

**验收标准**：
- [ ] VPS（47.112.162.80）实测安装依赖、下载模型
- [ ] 记录内存占用与冷启动首响延迟
- [ ] 若不可行，明确改走纯云 provider 路线（补齐 2.1 后此条自动满足）

---

## 3. P1 项（退役后短期内补齐）

### 3.1 OpenAPI 最后 1/29 端点

当前 28/29（见 `xiaozhi_lima_protocol_alignment.md` §3）。剩余端点需核对后补齐或显式标注不实现。

- [ ] 核对剩余 1 端点（疑似 Supply 或 SelfCheck 历史查询）
- [ ] 补齐实现或显式标注"LiMa 不承接，原小智也不使用"

### 3.2 协议对齐文档 P0 项复核

`xiaozhi_lima_protocol_alignment.md` §7 列出的 P0 项（Auth register/sms-verification/me、Device register/list/detail/unbind、Task list/detail），需复核当前实现状态（文档日期 2026-06-10，距今有增量）。

- [ ] 逐项核对 §7 P0 清单当前实现状态
- [ ] 更新本文档或对齐文档，反映 28/29 的具体构成

---

## 4. P2 项（运营/长期，不阻塞退役）

- [ ] Transfer 全套接口（申请/待处理/接受/取消）
- [ ] Supply 查询/更新 + 设备上报 schema
- [ ] Voiceprint 删除接口
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

| Provider | 代码完整 | 依赖就绪 | 真机验证 | 结论 |
| --- | --- | --- | --- | --- |
| FunASR（本地 ASR） | ✅ | ❓ | ❓ | 待验证 |
| EdgeTTS（免费 TTS） | ✅ | ❓ | ❓ | 待验证（含 PCM 转码问题） |
| SileroVAD（本地 VAD） | ✅ | ❓ | ❓ | 待验证（含静默降级问题） |
| 3D-Speaker（本地声纹） | ✅ | ❓ | ❓ | 待验证 |
| Voiceprint API（外部声纹） | ✅ | ❓ | ❓ | 待验证 |
| Aliyun ASR（云） | ❌ stub | — | — | 阻塞 |
| Aliyun TTS（云） | ❌ stub | — | — | 阻塞 |
| Doubao ASR（云） | ❌ stub | — | — | 阻塞 |
| Doubao TTS（云） | ❌ stub | — | — | 阻塞 |

---

## 7. 变更记录

| 日期 | 变更 | 作者 |
| --- | --- | --- |
| 2026-06-17 | 初版，基于 commit `280dd58` 代码核查 + 协议对齐文档综合 | — |
