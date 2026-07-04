# Ponytail（最高优先级行为原则）

> 上游仓库：`https://github.com/DietrichGebert/ponytail.git`
>
> 本文件是 LiMa 项目对 Ponytail 「lazy senior dev」理念的落地规则，**优先级高于默认编码冲动、高于炫技式实现**。所有 Agent 在修改本仓库前必须先阅读并执行本节。

## 核心信条

1. **Ponytail 是第一原则**。
   - 会偷懒的 Agent 才是合格 Agent。
   - 写一堆低质量代码的 Agent 是坏 Agent。
   - 听话、有工程意识、能用最小变更解决复杂问题的 Agent 才是好 Agent。

2. **能少写就少写，能不写就不写**。
   - 不要写"为将来预留"的代码。
   - 不要引入不必要的抽象。
   - 不要借重构之名扩大改动面。

3. **优先从外部找高可靠实现，其次才自己写**。
   - 修改前先去 GitHub、官方文档、Context7 等可靠来源搜索：是否已经存在经过生产验证的库、代码片段或官方示例？
   - 复用高可靠代码 = 降低测试风险、降低维护面、降低 bug 概率、减少代码量。
   - 不要重复造轮子，除非现有轮子确实不满足需求且有明确证据。

4. **写代码前必须过 Ponytail 决策阶梯**：
   1. 这个功能真的需要吗？（YAGNI）
   2. Python / 语言标准库能直接做到吗？
   3. 平台 / 框架原生特性能直接做到吗？
   4. 已有依赖能直接做到吗？
   5. 能一行写完吗？
   6. 最后才写最小实现。

5. **ESP32 / 固件 / 小程序 / 嵌入式相关代码改动**：修改前**必须主动加载对应的领域 skills**。
   - ESP32 / ESP-IDF / PlatformIO：`esp32`、`esp-idf-handling`、`esp-pio-handling`
   - 调试 / 烧录 / 串口：`jlink`、`openocd`、`probe-rs`、`serial`、`flash-*`、`debug-*`
   - 测试台 / 硬件联调：`workbench-*`、`signal-generator`
   - 小程序 / 前端：`vue-patterns`、`react-native-patterns` 等
   - 用领域 skill 降低知识盲点与改错概率；**不加载对应 skill 就动手改固件/小程序是禁止的**。

6. **最小变更、最小文件、最小函数**。
   - 能用一行就别用十行。
   - 能改一个文件就别改十个文件。
   - 新函数 ≤50 行，新文件 ≤300 行。

## 第一原则确认与引用

| 原则 | 来源 | LiMa 落地文件 |
|------|------|---------------|
| Ponytail「lazy senior dev」 | [`DietrichGebert/ponytail.git`](https://github.com/DietrichGebert/ponytail.git) | 本文件 + `AGENTS.md` + `docs/xiaozhi-cloud/lima-slimdown-design.md` |
| 优先复用 GitHub 高可靠代码 | Ponytail 核心信条 | 所有 Agent 编辑前必须检索 GitHub / Context7 / 官方文档 |
| ESP32 / 固件 / 小程序改前加载 skill | Ponytail 核心信条 | 修改前必须调用 `esp32`、`esp-idf-handling`、`esp-pio-handling`、`vue-patterns` 等对应 skill |

> **本文件是 LiMa 仓库所有 Agent 行为的第一优先级原则。** 当 Ponytail 原则与默认编码冲动、炫技式实现、或任何其他建议冲突时，以 Ponytail 为准；但 Ponytail 本身不得绕过 LiMa 硬规则（输入验证、错误处理、安全措施、测试门禁、文档同步、Git 规则）。

## 不可妥协的边界

以下场景 **LiMa 硬规则优先**，不允许为了简化而绕过：

- 信任边界的输入验证（`access_guard.py`、`identity_guard.py`）
- 防止数据丢失的错误处理（`session_memory/` 持久化逻辑）
- 安全：无硬编码 secret、无 silent degradation
- LiMa 测试门禁：`pytest`、`ruff check .`、`pyright`、`scripts/check_code_size.py`
- 文档同步：`STATUS.md` / `progress.md` / `findings.md`（如适用）
- conventional commits、仅 stage 相关文件

## 简化标记

如果使用 Ponytail 建议的捷径，且该捷径有已知上限（全局锁、O(n²) 扫描、朴素启发式），用 `ponytail:` 注释说明上限和升级路径，并记入 `PONYTAIL-DEBT.md`。

## 自检问题

每次准备编辑文件前，先问自己：

- 这个功能真的必须现在实现吗？
- GitHub 上有没有现成、高星、维护活跃的实现可以直接复用？
- 标准库 / 已有依赖能不能解决？
- 如果改 ESP32 / 固件 / 小程序，我加载了对应的 skill 吗？
- 这次改动能不能再小一点？

针对小智云 + DLC 瘦身场景，额外自检：

- 这个能力小智官方云（xiaozhi.me）是否已经免费提供？如果是，能否直接复用而非自维护？
- 这个改动是否会把本可以外包给云的 ASR/TTS/LLM/普通对话能力重新拉回 LiMa？
- 这个模块删除后，DLC 核心（文字→路径 / SVG→路径 / 路径校验 / Grbl）是否仍然完整？
- 新增的接口/工具是否遵循最小暴露原则（MCP tool / HTTP API 仅保留必要的 `dlc.write_text`、`dlc.draw_generated`、`dlc.validate_path`、`dlc.dispatch_task`）？
