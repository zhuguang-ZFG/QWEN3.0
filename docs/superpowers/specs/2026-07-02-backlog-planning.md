# LiMa 遗留项待办规划

- **日期**: 2026-07-02（**2026-07-10 复核**）
- **状态**: 活跃；P0-1 / P1-1 已关闭，语音后端已加固并 strict E2E 通过
- **背景**: 系统瘦身 + 语音控制（M0/M1/M2）完成后的真实遗留项汇总。

---

## 已关闭

### ~~BACKLOG-P0-1~~ 部署脚本不支持京东云主生产节点 ✅

- **关闭日期**: 2026-07-10
- **结果**: `scripts/deploy_unified.py --target jdcloud`（默认 `jdcloud`）；`get_deploy_target()` 支持 aliyun / jdcloud；语音栈已多次成功部署至 `117.72.118.95`，自动备份 + health 等待。

### ~~BACKLOG-P1-1~~ 语音设计文档状态标记过期 ✅

- **关闭日期**: 2026-07-10
- **结果**: `2026-07-02-mini-program-voice-draw-design.md`、`docs-site/api/voice.md`、`STATUS.md` 已同步当前实现与 E2E 证据。

---

## P0 —— 阻塞性 / 安全 / 真功能缺陷（应尽快处理）

### BACKLOG-P0-2 U8 固件音频协议矛盾（待硬件决策）

- **事实**（已核实）：`websocket_protocol.cc` hello 声明 `format:"pcm"`，但 `audio_service.cc` 实际 OPUS 编码；后端无 OPUS 解码。
- **影响**：**设备直连**实时语音/声纹若走 OPUS 路径会失败；**小程序 REST/WS 语音不受影响**（上传 WAV/PCM）。
- **决策点**：① 改固件发 PCM ② 后端加 opuslib
- **工作量**：0.5–1 天

### BACKLOG-P0-3 真机端到端验证（语音功能）

- **事实**：后端 strict E2E（`LIMA_VOICE_E2E_STRICT=1`）已 PASS（transcribe + 两路 WS + `draw_generated` intent）；但**真实小程序录音 → 确认对话框 → 物理设备运动**未验证。
- **建议**：真机测 ①按住说话「画一只猫」②「写你好」③实时流 M2；记录到 `docs/release_evidence/`。
- **工作量**：0.5 天

### BACKLOG-P0-4 微信审核提交

- **事实**：v3.8.0 已上传微信平台，**未提交审核/未发布**。
- **建议**：P0-3 通过后再提审。

---

## P1 —— 低风险但应做（质量/一致性）

### BACKLOG-P1-2 生产路径静默降级审查

- **事实**：部分退役模块（如 `voice_pipeline_ws`）仍有 `except: pass`；当前生产路径 `device_voice/`、`routes/device_app_voice*.py` 已遵守硬规则。
- **建议**：仅审查**仍在 `server_dlc` 热路径**的文件。
- **工作量**：0.5 天

### BACKLOG-P1-3 retired 代码文件在 docs 树

- **事实**：`docs/archive/retired/` 含历史脚本。
- **决策**：删 or 移至 `archive/code/`。

### BACKLOG-P1-4 agent 配置树合并

- **状态**：按需；先核实再合并。

### BACKLOG-P1-5 语音可选后端能力（非阻塞）

| 项 | 说明 |
|----|------|
| `POST /voice/parse` | 编辑文本后重新解析 intent（设计 MVP 暂缓） |
| WS stop 返回 `intent` | 当前仅 `transcript`，M2 需客户端解析 |
| Doubao ASR provider | 配置项存在，`registry` 未实现 |
| 服务端 WS idle 断开 | 当前仅客户端 `ping` → `pong` |

---

## P2 —— 中风险重构（需产品确认）

### BACKLOG-P2-1 小程序 UI 重构

- 先真机核实页面冗余，再决定合并/删除。

---

## 不做（已验证非问题）

- ❌ progress.md 截断（内容仍近期有效）
- ❌ routing_engine 包归拢（facade 已存在）
- ❌ 删 speculative_policy.py（热路径依赖）

---

## 执行顺序建议（2026-07-10）

```
立即：P0-3 真机验证 → P0-4 微信提审
排期：P0-2 U8 音频（仅设备直连语音）
按需：P1-2 静默降级（热路径）
按需：P1-5 语音增强端点
按需：P2-1 小程序 UI
```
