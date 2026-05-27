# Gemini Live 视频通话方案

> 创建: 2026-05-22
> 目标: 用 Gemini Live API 实现实时视频通话 AI（类豆包体验）

---

## 架构

```
浏览器 (voice-call.html)
  ├─ getUserMedia({video, audio})
  ├─ AudioWorklet → PCM 16kHz → WebSocket
  ├─ Canvas 截帧 (1 FPS JPEG) → WebSocket
  └─ 接收音频流 → AudioContext 播放
         ↕ WebSocket
Gemini Live API (wss://generativelanguage.googleapis.com/...)
```

**零服务器负载** — 浏览器直连 Google。

## API 规格

- Endpoint: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`
- Auth: `?key=GOOGLE_AI_KEY` query param
- Model: `gemini-2.0-flash-live-001`
- Input: PCM 16-bit 16kHz audio + JPEG frames (≤1 FPS)
- Output: PCM 16-bit 24kHz audio stream

## 协议流程

1. 连接时发 setup message:
```json
{"setup": {"model": "models/gemini-2.0-flash-live-001",
           "generationConfig": {"responseModalities": ["AUDIO"],
                                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}}}}
```

2. 发送音频: `{"realtimeInput": {"mediaChunks": [{"mimeType": "audio/pcm;rate=16000", "data": "<base64>"}]}}`

3. 发送视频帧: `{"realtimeInput": {"mediaChunks": [{"mimeType": "image/jpeg", "data": "<base64>"}]}}`

4. 接收音频: `{"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": "<base64>"}}]}}}`

5. 打断: 用户说话时 Gemini 自动停止输出 (barge-in)

## 改动清单

| 文件 | 动作 |
|------|------|
| /var/www/chat/voice-call.html | **重写** — Gemini Live 客户端 |
| /opt/lima-router/server.py | 新增 `/api/live-key` 端点返回 key |
| nginx chat.conf | 无需改动 (纯前端直连 Google) |
| voice_gateway.py:8091 | 可停止 (Gemini 替代) |

## 安全考虑

- API Key 通过 `/api/live-key` 动态获取，不硬编码在 HTML 中
- 免费额度有 Google 侧限流，无滥用风险
- 摄像头/麦克风权限由浏览器 Permission API 管理

## 执行步骤

1. server.py 加 `/api/live-key` 端点
2. 重写 voice-call.html (Gemini Live 客户端)
3. 部署到服务器
4. 端到端验证
