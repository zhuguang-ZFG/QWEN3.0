# 小智官方云 + DLC 核心文档中心

> 来源基础：`https://xiaozhi.dev/docs/` 官方文档缓存 + `D:/QWEN3.0` 本地设计/实测文档
> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，以小智官方云承载语音/对话/LLM，以 DLC 核心承载写字/绘图/路径/设备控制。**

---

## 1. 这套文档是干什么的

这套文档用于支撑 LiMa 从“大而全的 AI 路由平台”收缩为“**小智官方云 + DLC 绘图/写字核心**”的工程重构。

目标架构：

```text
用户语音
  → ESP32 U8（小智固件）
  → 小智官方云（ASR / TTS / 普通对话 / LLM）
  → MCP tools/call
  → dlc_mcp / dlc_api / dlc_core
  → U8 → Edge-D UART → U1 Grbl
```

文档职责：

- 统一主路线，避免“独立新仓”和“LiMa 内瘦身”两条路线并存。
- 把 P0 已验证事实、P1~P4 设计、未决问题、官方资料缓存分开管理。
- 为后续服务端、固件端、小程序端、双云部署改造提供唯一入口。

---

## 2. 当前权威路线

### 主路线（当前执行）

**在 `D:/QWEN3.0` 内瘦身：**

- 新增/演进 `dlc_core/`
- 新增/演进 `dlc_api/`
- 新增/演进 `dlc_mcp/`
- 保留 `xiaozhi_drawing/` 算法资产
- 逐步把 LiMa 收缩为“小智官方云 + DLC 核心”

### 历史/备选路线（不再作为当前默认）

- `docs/superpowers/specs/2026-07-04-xiaozhi-dlc-server-migration-design.md`
- 该路线以 `D:\xiaozhi-dlc-server` 独立新仓为主，现已降级为**历史/备选方案**。

---

## 3. 阅读顺序（必须按这个顺序）

### A. 先看总入口与路线

1. `docs/xiaozhi-cloud/README.md`（本文件）
2. `docs/xiaozhi-cloud/00-roadmap.md`

### B. 再看已验证事实与未决事项

3. `docs/xiaozhi-cloud/09-p0-evidence.md`
4. `docs/xiaozhi-cloud/10-p1-evidence.md`
5. `docs/xiaozhi-cloud/08-open-questions.md`
6. `docs/xiaozhi-cloud/p1-mcp-smoke-commands.md`（当前 P1 实测与命令）
7. `docs/xiaozhi-cloud/p0-mcp-smoke-commands.md`（P0 历史命令，已不适用）

### C. 再看总设计与专业分册

8. `docs/xiaozhi-cloud/lima-slimdown-design.md`（当前最完整总设计稿）
9. `docs/xiaozhi-cloud/01-architecture.md`
10. `docs/xiaozhi-cloud/02-service-refactor.md`
11. `docs/xiaozhi-cloud/03-firmware-refactor.md`
12. `docs/xiaozhi-cloud/04-miniprogram-refactor.md`
13. `docs/xiaozhi-cloud/05-deployment-and-ops.md`
14. `docs/xiaozhi-cloud/06-failure-and-safety.md`
15. `docs/xiaozhi-cloud/07-validation-and-acceptance.md`

### D. 最后看参考资料与历史文档

16. `docs/xiaozhi-cloud/references/02-mcp-usage.md`
17. `docs/xiaozhi-cloud/references/03-mcp-protocol.md`
18. `docs/xiaozhi-cloud/references/04-websocket-protocol.md`
19. `docs/xiaozhi-cloud/references/05-mqtt-udp-protocol.md`
20. `docs/xiaozhi-cloud/references/06-faq.md`
21. `docs/superpowers/specs/2026-07-04-xiaozhi-dlc-server-migration-design.md`（历史路线，仅做对照）

---

## 4. 文档分层说明

### 4.1 权威设计稿

- `docs/xiaozhi-cloud/lima-slimdown-design.md`
  - 当前最完整总设计稿。
  - 覆盖：架构、双云分工、图库、状态、并发、失败恢复、防呆、接口草案。
  - **注意**：后续会逐步拆分，不应无限继续膨胀。

### 4.2 P0 实测证据

- `docs/xiaozhi-cloud/p0-mcp-smoke-commands.md`
  - 当前保存了：
    - `dlc_api` 最小服务启动方式
    - `dlc_mcp` stdio server 冒烟方式
    - 官方云 MCP endpoint 接入与 discovery 验证方式
    - 已知限制：`draw_generated` 目前受图像生成链路限制

### 4.3 官方资料缓存

这些文件不是项目设计，而是**证据来源**，已统一移入 `references/` 子目录，避免与专业分册的数字前缀冲突：

- `references/01-docs-center.md`
- `references/02-mcp-usage.md`
- `references/03-mcp-protocol.md`
- `references/04-websocket-protocol.md`
- `references/05-mqtt-udp-protocol.md`
- `references/06-faq.md`

用途：

- 校对 MCP 交互流程
- 校对设备端 AddTool 约定
- 校对 WebSocket / MQTT 协议细节
- 校对官方 FAQ 与能力边界

### 4.4 历史路线文档

- `docs/superpowers/specs/2026-07-04-xiaozhi-dlc-server-migration-design.md`
  - 保留原因：记录“独立新仓”思路与最早阶段的迁移判断。
  - 当前不作为默认实施路线。

---

## 5. 当前最重要的工程结论

1. **语音 / 对话 / LLM 不再自维护**
   - 交给小智官方云处理。
2. **DLC 核心必须保留在自己手里**
   - 包括：文字→路径、SVG→路径、路径校验、设备状态、任务下发、Grbl 控制闭环。
3. **当前默认是 LiMa 内瘦身，不是另起新仓**
   - `dlc_core / dlc_api / dlc_mcp` 是主线。
4. **P0 已跑通 MCP discovery**
   - 官方云 broker 已成功发现 `dlc.write_text` / `dlc.draw_generated`。
5. **P1 已冻结接口并落地核心 facade**
   - `/write`、`/draw` 已收敛为 `/dlc/tasks/preview` 与 `/dlc/tasks/dispatch`。
   - `dlc_core` 已建立 `write / draw / presets / path_validator / safety / dispatch` 薄封装。
   - 21 个新增/更新测试全部通过，ruff 与 pyright 无新增错误。
6. **P1 仍有一个关键限制**
   - `dlc.draw_generated` 的 AI 生图端到端仍受后端影响，P1 默认降级为预设图形优先；详见 `08-open-questions.md` Q-02。

---

## 6. 文档工作进度

文档收口、专业分册与 P1 接口冻结已全部落地：

| 批次 | 文件 | 状态 |
|------|------|------|
| D1 收口 | `README.md`、`00-roadmap.md` | ✅ 完成 |
| D3 证据 | `09-p0-evidence.md`、`08-open-questions.md`、`10-p1-evidence.md` | ✅ 完成 |
| D2 分册 | `01-architecture.md` ~ `07-validation-and-acceptance.md` | ✅ 完成 |
| D4/P1 实现 | `dlc_core/`、`dlc_api/`、`dlc_mcp/` 接口冻结 + 测试 | ✅ 完成 |

原则：**先收口入口与证据链，再拆专业分册，最后再进入正式实现。**

下一步进入 **P2 固件与小程序接入**（见 `00-roadmap.md` P2 阶段）。

---

## 7. 本目录文件状态表

| 文件 | 状态 | 角色 |
|------|------|------|
| `README.md` | 当前有效 | 总入口 |
| `00-roadmap.md` | 当前有效 | 总路线图（P0~P4） |
| `01-architecture.md` | 当前有效 | 架构与责任边界 |
| `02-service-refactor.md` | 当前有效 | 服务端 dlc_core/dlc_api/dlc_mcp |
| `03-firmware-refactor.md` | 当前有效 | U8/U1 固件改造 |
| `04-miniprogram-refactor.md` | 当前有效 | 小程序改造 |
| `05-deployment-and-ops.md` | 当前有效 | 双云部署与运维 |
| `06-failure-and-safety.md` | 当前有效 | 失败恢复与安全边界 |
| `07-validation-and-acceptance.md` | 当前有效 | 验证矩阵与验收 |
| `08-open-questions.md` | 当前有效 | 未决事项 |
| `09-p0-evidence.md` | 当前有效 | P0 已验证事实 |
| `10-p1-evidence.md` | 当前有效 | P1 已验证事实与接口冻结 |
| `lima-slimdown-design.md` | 当前有效 | 总设计稿（逐步被分册取代） |
| `p1-mcp-smoke-commands.md` | 当前有效 | P1 冒烟命令 |
| `p0-mcp-smoke-commands.md` | 历史归档 | P0 冒烟命令（已不适用） |
| `references/01-docs-center.md` ~ `references/06-faq.md` | 当前有效 | 官方资料缓存 |
| `2026-07-04-xiaozhi-dlc-server-migration-design.md` | 历史/备选 | 旧路线对照 |

---

## 8. 使用约束

- 新增设计优先写到 `docs/xiaozhi-cloud/` 主线分册中。
- 不要再把所有内容继续堆进一个超大文档里。
- 如果某个结论尚未实测，必须明确标注“待验证”，不能写成确定事实。
- 如果引用官方能力，优先回指本目录的官方缓存文档，而不是凭记忆复述。
