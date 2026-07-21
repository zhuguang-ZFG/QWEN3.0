# Findings（仅近期）

> 更早 findings / AUDIT 已删除；需要时查 git history。
> 五问法：现象？复现？根因？修复？如何预防？

## 2026-07-21 文档编码损坏（docs/README）

- **现象**：`docs/README.md` 中文乱码（UTF-8 被当 ANSI 写回）。
- **根因**：清理 trailing whitespace 时用 `WriteAllText` 未指定 UTF-8。
- **修复**：整文件 UTF-8 重写；后续写中文 md 用工具默认 UTF-8。
- **预防**：PowerShell 写 md 使用 UTF8Encoding(false) 或由 `write` 工具落盘。

## 2026-07-21 bare registry 误标 complete（已修 `80fd0749`）

- **现象**：`register_device_profile` 空 `profile_id` 会使 `complete=True`，打开路由门控。
- **修复**：complete 需非空 `profile_id` + 正有限 workspace；shadow 永不 complete。
- **预防**：profile 接线 hello 前保持该判定。

## 2026-07-21 工作区 0 轴被接受（已修）

- **现象**：zero workspace 进入 path gen 后 normalize 才炸。
- **修复**：`_as_workspace` / `workspace_axes_ok` 拒绝 ≤0 / 非有限；explicit 须三轴齐全。

## 2026-07-09 静态分析门禁

- pyright venv 配置 + pytest P13 跳过 node_modules 断链；当时 pyright 0 errors / pytest 绿。

## 2026-07-06 设备网关 WSS 投递

- 曾结论「无存量设备」；**2026-07-21 起 M1/M2 已实现** DLC 侧 WSS 投递，真机联调仍为 P0-3。勿再按「已退役」理解当前代码。
