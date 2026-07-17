# LiMa / DLC 项目状态

> 更新日期：2026-07-17
> 生产版本：`dlc-drawing 0.4.0-p3`（`main` @ `d0d15df1`+）
> 公网入口：`https://chat.donglicao.com` → 京东云 `117.72.118.95`（`server_dlc` :8081）

> 根目录 `STATUS.md` 与本文件内容保持同步（供 CI/人类速览）。

---

## 当前架构（摘要）

```text
server_dlc.py (:8081)
  → dlc_api/          /dlc/*、device_app_router
  → dlc_core/         绘图/写字/下发
  → device_gateway/   Redis（任务队列/小程序路径为主；自托管 WSS→ESP32 已退役）
  → device_voice/     小程序语音 ASR（REST + WS）
小智 MCP → dlc_mcp/
小程序   → /device/v1/app/*、/v1/voice?ticket=…
```

**已退役**：`routing_engine*`、旧 `server.py` 聊天栈、`voice_pipeline_ws` 完整对话管道 — 见 `docs/archive/`。

---

## 已完成（近期）

| 里程碑 | 状态 | 证据 |
|--------|------|------|
| 小程序语音 M0/M1/M2 后端 | ✅ | `device_voice/`、`routes/device_app_voice*.py` |
| 语音加固 + strict E2E | ✅ | `e64ac48f`；2026-07-17 复核 6/6 PASS |
| jdcloud 默认部署 | ✅ | `deploy_unified.py --target jdcloud` |
| nginx `/v1/voice` → :8081 | ✅ | `deploy/nginx/chat.donglicao.com.conf` |
| 文档同步 | ✅ | `docs/`、`docs-site/api/voice.md` |
| A–E 优化计划 | ✅ | A/B/D 完成；C 验证后删除（`7eed9aac`）；E 原语 + draw 接线（`ff80dff6`/`2793f190`） |
| 优雅关停 + `/health` Redis 依赖检查 | ✅ | `caed1111`；已部署京东云 |
| logrotate `/etc/logrotate.d/lima-dlc` | ✅ | 已落 VPS（零代码） |
| 安全审查 P0/HIGH/MEDIUM/LOW | ✅ | `cd1780d4`/`ba6544f2`/`9974bec4`/`1592c882`；固件 `91cb4ea`/`4de9ae9`；已部署京东云 |
| device_app_tasks 拆分 ≤300 行 | ✅ | `f122c3a7`；Atom 实现；已部署京东云 |
| Aliyun 安全/版本对齐 | ✅ | 2026-07-12：`0.4.0-p3` + redis task_store；关键安全文件 md5 与本地一致 |
| Ponytail 硬门禁（4 长函数≤50） | ✅ | `d0d15df1`；ruff + pytest 绿 |
| fz Host SIL（standard/deep/firmware） | ✅ | 2026-07-17；G0 PIO + G1 + release_smoke 全绿 |
| pytest 全量 | ✅ | 2026-07-17；1784 passed / 3 skipped |

---

## 待办（阻塞上线）

| ID | 项 | 阻塞 |
|----|-----|------|
| P0-3 | 真机 E2E：录音 → 确认 → 物理设备运动 | 真机 |
| P0-4 | 微信审核发布（v3.8.0 已上传未提审） | 运营/提审 |
| P0-2 | U8 OPUS/PCM（仅设备直连语音） | 产品排期 |
| E-2 | ESP32 端到端验证 `LIMA_AUTO_FALLBACK` draw 路径 | **暂无真机**（2026-07-12 挂起；有机后再验） |
| G3 | HIL 纸路/BT 串口证据 | 真机 + `hil_to_gate --port COMx` |

详见 [`superpowers/specs/2026-07-02-backlog-planning.md`](superpowers/specs/2026-07-02-backlog-planning.md)。

---

## 语音生产（摘要）

```env
LIMA_VOICE_ENABLED=1
LIMA_VOICE_ASR_PROVIDER=dashscope
DASHSCOPE_ASR_MODEL=qwen3-asr-flash
```

```powershell
$env:LIMA_VOICE_E2E_STRICT='1'
python scripts/run_voice_e2e_production.py
```

- ticket TTL：**30 秒**（`voice_app_ws_ticket.TTL_SECONDS`）
- WS 仅返回 `transcript`，不含 `intent`（intent 走 REST transcribe）

---

## PC 仿真门禁（摘要）

```powershell
$env:FZ_ROOT='D:\Users\zhugu\fz'
$env:GRBL_ROOT='D:\Users\Grbl_Esp32'
$env:QWEN_ROOT='D:\QWEN3.0'
python $env:FZ_ROOT\scripts\agent_gate.py --profile firmware
```

- Host SIL ≠ 真机纸路/BT；发版前仍需 G3 HIL
- 报告：`fz/results/agent_gate_last.json`、`release_honesty_last.json`

---

## 部署

```powershell
python scripts/deploy_unified.py --target jdcloud --slice core
python scripts/deploy_unified.py --target jdcloud --files device_voice/ routes/device_app_voice.py routes/device_app_voice_ws.py voice_app_ws_ticket.py
```

| 项 | 值 |
|----|-----|
| 远程路径 | `/opt/dlc-drawing/` |
| 备份 | `/opt/dlc-drawing/backups/` |
| systemd | `dlc-drawing` |

---

## 关键文档

| 文档 | 用途 |
|------|------|
| [`../AGENTS.md`](../AGENTS.md) | Cursor 入口 |
| [`AGENTS_REFERENCE_CN.md`](AGENTS_REFERENCE_CN.md) | 完整规范 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 架构 |
| [`../docs-site/api/voice.md`](../docs-site/api/voice.md) | 语音 API |
| [`testing/device_app_voice.tdd.md`](testing/device_app_voice.tdd.md) | 语音 TDD |
