# LiMa 遗留项待办规划

- **日期**: 2026-07-02
- **状态**: 待用户按优先级逐项决定
- **背景**: 系统瘦身 + 语音控制（M0/M1/M2）完成后的真实遗留项汇总。每项均经核实（非基于可能有误的审查报告）。

---

## P0 —— 阻塞性 / 安全 / 真功能缺陷（应尽快处理）

### BACKLOG-P0-1 部署脚本不支持京东云主生产节点

- **事实**：`deploy_unified.py` 的 `LIMA_SERVER` 默认 `47.112.162.80`（阿里云 pilot），但公网入口在京东云 `117.72.118.95`。脚本对京东云零支持（`grep` 返回 0）。本次语音端点部署误打到阿里云，公网 404，后手动 SSH+sftp 到京东云才修好。
- **影响**：每次主生产部署都有误打阿里云的风险；且无自动化备份/回滚（本次手动 cp 备份）。
- **建议**：给 `deploy_unified.py` 加 `--target {aliyun,jdcloud}` 参数，或更新默认 `LIMA_SERVER` 为京东云。京东云用 root 密码认证（非 SSH key），连接逻辑需适配。
- **工作量**：0.5–1 天
- **凭据**：京东云 117.72.118.95 root 密码已记录于 `D:\Downloads\VPS.txt`（不入库）。

### BACKLOG-P0-2 U8 固件音频协议矛盾（待硬件决策）

- **事实**（已核实）：`websocket_protocol.cc:233` hello 帧声明 `format:"pcm"`，但 `audio_service.cc:417` 永远 `esp_opus_enc_process`（OPUS 编码）。后端 `_ensure_wav` 对 opus 返回 None（无 OPUS 解码）。
- **影响**：设备实时语音/声纹若走 OPUS 路径，后端无法解码，静默失败。
- **决策点**（需你定）：① 改固件发 PCM（带宽 +10x）② 后端加 opuslib 依赖（新依赖）。
- **工作量**：修法①0.5 天 / 修法②1 天
- **关联**：findings.md 已记录。

### BACKLOG-P0-3 真机端到端验证（语音功能）

- **事实**：语音 M0/M1/M2 的测试全用 mock ASR；前端 type-check 通过；已上传微信 v3.8.0；后端已部署京东云。但**真实录音 → 真实 ASR → 真实派发到物理设备**这条链从未真机验证过。
- **影响**：frameSize、ASR 真实格式、意图识别质量、确认对话框交互都可能在真机暴露问题（本次检修已证明 mock 测试测不出 frameSize 错误）。
- **建议**：在真设备上测：①按住说话"画一只猫"→确认→绘图机执行 ②"写你好"→确认→写字机执行 ③实时流同上。
- **工作量**：0.5 天（需设备 + 微信开发者工具）

### BACKLOG-P0-4 微信审核提交

- **事实**：v3.8.0 已上传微信平台（含修复后的构建），但**未在 mp.weixin.qq.com 提交审核**，未发布。
- **建议**：你登录 mp.weixin.qq.com 提交审核。**注意**：提交前先完成 P0-3 真机验证，避免发布后才发现语音不工作。

---

## P1 —— 低风险但应做（质量/一致性）

### BACKLOG-P1-1 语音设计文档状态标记过期

- **事实**：`docs/superpowers/specs/2026-07-02-mini-program-voice-draw-design.md:4` 仍标「待审批 → 执行」，但 M0/M1/M2 已全部执行完毕。
- **建议**：改为「已完成（M0+M1+M2 已部署+上传）」，补执行结果摘要 + 已知问题（frameSize 等）。
- **工作量**：10 分钟

### BACKLOG-P1-2 16 个生产路径静默降级（违反硬规则）

- **事实**（已核实，精确扫描）：生产路径共 16 个 `except: pass/continue` 静默降级点，分布在：
  - `routes/voice_pipeline_ws.py`(2)、`device_gateway/mqtt_client.py`(2)、`session_memory/store_voiceprint.py`(2)
  - 另外 10 个文件各 1 个
- **影响**：违反 AGENTS.md 硬规则「禁止静默降级」。部分可能是 retry/stream 循环里的合理 continue，需逐一审查。
- **建议**：逐一审查 16 个点，合理的加注释说明，不合理的补 `logger.warning`。
- **工作量**：0.5 天

### BACKLOG-P1-3 7 个 retired 代码文件在 docs 树

- **事实**：`docs/archive/retired/` 下有 7 个文件（gitee_mirror*.py / push_dual_remotes.*），代码文件不该在 docs 树。
- **建议**：① 删除（Gitee 镜像已彻底退役，git 历史可恢复）② 或移到 `archive/code/`。
- **决策点**：删 or 移，需你定。
- **工作量**：15 分钟

### BACKLOG-P1-4 8 个 agent 配置树合并（Ponytail/ECC 重复 6 处/4 处）

- **事实**（审查）：~9300 行 agent 指令跨 8 个配置树（skills/.agent/.claude/.kimi-code/.cursor/.joycode/andrej-karpathy-skills/根），Ponytail 规则重复 6 处。
- **风险**：审查报告有 5 处误判前科，**此结论未逐一核实**。建议先核实再合并。
- **工作量**：1 天（含核实）

---

## P2 —— 中风险重构（需 TDD + 产品确认，审查结论未验证）

### BACKLOG-P2-1 小程序 UI 重构（create.vue 嵌套 tab / 3 首页 / settings）

- **事实**：审查报告说 create.vue 937 行嵌套两层 tab、3 个首页重叠、settings 744 行杂物。但瘦身审查报告有 5 处误判前科，**这些 UI 结论尚未真机核实**。
- **建议**：先真机/预览核实哪些页面真冗余，再决定合并/删除。不要按可能有误的清单盲改。
- **工作量**：核实 0.5 天 + 重构 2–3 天
- **前置**：需你确认产品方向（哪些页面保留）。

---

## 不做（无价值或已验证非问题）

- ❌ progress.md 截断：审查建议截断到近 30 天，但**核实发现全部内容在近 3 天内**，截断无意义。
- ❌ routing_engine 包归拢：核查发现 facade 已存在、文件符合尺寸规则、直接 import 子模块的多是单元测试（合理实践），强行改性价比低。
- ❌ 删 speculative_policy.py：标了 DEPRECATED 但是热路径依赖（已改标记而非删除）。
- ❌ 删 98MB node_modules：在 .gitignore，从未入库，非仓库问题。

---

## 执行顺序建议

```
立即：P0-4 微信审核前先做 P0-3 真机验证
本周：P0-1 部署脚本修京东云支持
本周：P1-1 文档状态标记（10分钟顺手做）
排期：P0-2 U8 音频 bug（需硬件决策）
排期：P1-2 静默降级审查
排期：P1-3 retired 文件处置（需你定删or移）
按需：P1-4 agent 树合并（先核实）
按需：P2-1 小程序 UI（先核实+产品确认）
```