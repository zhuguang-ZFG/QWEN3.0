# device_app_voice TDD 证据

来源：小程序语音 M0/M1/M2 后端（2026-07-02 设计，2026-07-10 加固）。

## 用户旅程

1. 按住说话上传 WAV → `POST /device/v1/app/voice/transcribe` → 获得 `text` + `intent`。
2. 实时流换取 ticket → `WS /v1/voice` 或 `/device/v1/app/voice/ws` → 边说边显 `transcript` → `stop` 得最终文本。
3. 用户确认后由小程序调用现有任务 API 派发（本模块不创建任务）。

## 实现文件

| 文件 | 职责 |
|------|------|
| `routes/device_app_voice.py` | REST transcribe + ticket |
| `routes/device_app_voice_ws.py` | WS 流式 ASR + legacy `/v1/voice` |
| `device_voice/` | ASR provider、音频格式、streaming session |
| `voice_app_ws_ticket.py` | 单次 ticket（绑定 account_id） |
| `dlc_api/device_app_router.py` | 路由挂载 |

## 验证

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_device_app_voice.py tests/test_device_app_voice_ws.py tests/test_device_voice_*.py tests/test_voice_e2e_probe.py -q
.venv310\Scripts\ruff.exe check device_voice routes/device_app_voice.py routes/device_app_voice_ws.py
$env:LIMA_VOICE_E2E_STRICT='1'; .venv310\Scripts\python.exe scripts/run_voice_e2e_production.py
```

## 保证

| # | 保证 | 测试 / 探针 | 结果 |
|---|------|-------------|------|
| 1 | 未鉴权 transcribe → 401 | `test_transcribe_unauthorized` / E2E | PASS |
| 2 | transcribe 返回 intent | `test_transcribe_draw_intent` / strict E2E | PASS |
| 3 | ticket 单次消费 | `test_voice_ticket_binds_account` | PASS |
| 4 | WS 两路径 alias | `test_legacy_v1_voice_alias` / E2E | PASS |
| 5 | 最短 PCM 拒绝 | `test_transcribe_too_short_audio` | PASS |
| 6 | ping/pong 保活 | `test_voice_ws_ping_pong` | PASS |
| 7 | 流式 pacing 分帧 | `test_iter_pcm_frames_splits_by_1280` | PASS |
| 8 | 生产 strict 6 项 | `run_voice_e2e_production.py` | PASS（2026-07-10） |

## 未覆盖（backlog）

- 真机小程序录音 → 物理设备运动（P0-3）
- WS stop 返回 `intent`、Doubao ASR、`/voice/parse`（P1-5 可选）
