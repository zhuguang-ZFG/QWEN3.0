# Progress（仅近期）

> 更早条目已删除；需要时查 git history（`ac230614` 前含完整 progress 归档）。

## 2026-07-21 文档深度精简（第二轮）

- 删除 `docs/reference/`、`research/`、`plans/`、过期 ops（NewAPI/审计）、dated model_admission、dated release_evidence、大部分 superpowers specs/plans、xiaozhi-cloud 长篇编号设计。
- 保留：STATUS/架构/设备/部署/语音设计+backlog/TDD/发布模板/xiaozhi-cloud 瘦身入口。
- 修复 `docs/README.md` 编码损坏；本文件与 `findings.md` 截断为近期。

## 2026-07-21 文档清理 + 工作区 profile 收紧

- 删除整个 `docs/archive/` 与归档桩文档。
- 同步 STATUS / ARCHITECTURE / 设备入口至 WSS 投递 M1+M2 + workspace profile（`80fd0749`）。
- complete：`profile_id` + 正有限 workspace；shadow/bare registry incomplete。

## 2026-07-21 W1/W2 profile 收紧（`80fd0749`）

- `is_complete_profile` + workspace 轴校验；invalid/partial explicit 忽略。
- 测试：path workspace + profile resolution 绿。

## 2026-07-21 device_id 工作区贯通修复（`f95b7589`）

- resolve_profile 按 device registry / KNOWN.device_id；draw/coordinator 透传 device_id。

## 2026-07-21 设备投递 M1+M2 + 工作区 profile 贯通（`bec7c567` 及前序）

- M1 WSS hello/drain/online push；M2 delivery_reaper。
- path_workspace / DEFAULT 300×300×80 产品画布。

## 2026-07-17 语音 / Host SIL / pytest

- 语音 strict E2E 6/6；fz agent_gate standard/deep/firmware；pytest 全量绿（当时快照）。

## 2026-07-15 任务队列幽灵/双入队残留

- free-text / approve 路径修复（见 findings 同期）。
