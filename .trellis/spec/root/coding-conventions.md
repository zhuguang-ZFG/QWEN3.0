# Coding Conventions — 编码约定

## 1. Ponytail 第一（最高优先级）

本仓库所有 agent 行为的第一优先级是「最小变更」（细则：`docs/AGENTS_PONYTAIL.md`）：

- 写代码前过决策阶梯：YAGNI → stdlib → 框架 → 已有依赖 → 一行实现 → 最小实现。
- 优先复用仓库已有模块（先查 `guides/code-reuse-thinking-guide.md` 的思路），禁止平行实现。
- ESP32 / 固件 / 小程序改动前必须先加载对应 skill（`esp32`、`esp-idf-handling`、`esp-pio-handling`、uni-app/Vue）。

Ponytail 不得绕过的边界：信任边界输入验证（`access_guard.py`、`identity_guard.py`）、防数据丢失的错误处理、安全措施、测试门禁、文档同步。

## 2. 大小约束（硬门禁）

- 单文件 ≤300 行，单函数 ≤50 行。
- 检查：`python scripts/check_code_size.py`。
- 超限文件按职责拆分，参考已完成的 `device_app_tasks` 拆分（`STATUS.md`，commit `f122c3a7`）。

## 3. 类型与模块头

- Python 3.10 目标（ruff `target-version = py310`），类型注解必填；ruff 行宽 120。
- 本地惯用法（证据：`server_dlc.py`、`device_voice/asr.py`）：
  - 模块顶部一行 docstring 说明职责；
  - `from __future__ import annotations`；
  - 门面模块显式声明 `__all__`（见 `device_voice/asr.py`）。

## 4. 新能力默认关闭（特性开关）

新能力必须 env flag 门控，默认关闭；未配置时**显式报错**，不做静默 fallback。

证据：

- `device_voice/asr.py:26` — `if not VOICE.enabled: raise AsrNotConfiguredError(...)`
- `server_dlc.py` — `LIMA_STRUCTURED_LOGGING=1` 才切结构化日志，否则走 `logging.basicConfig`

配置读取走 `config/` 模块的设置对象（如 `config/voice_settings.py` 的 `VOICE`），不要在业务模块里散落 `os.environ.get`。

## 5. 文档语言

文档类产物默认中文；代码标识符、API 字段、路径保留英文（`docs/AGENTS_REFERENCE_CN.md`「文档语言」）。

## 6. 文档先行

非平凡变更先在 `docs/` 写设计说明，再动代码；完成后同步 `STATUS.md` / `progress.md` / `findings.md`。
