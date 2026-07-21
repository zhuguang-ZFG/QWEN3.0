# Progress（仅近期）

> 更早条目已删除；需要时查 git history（`ac230614` 前含完整 progress 归档）。

## 2026-07-21 CR 跟进 W1–W4（draw 顺序 / hello 三轴 / production env）

- 描图：optimize → validate → precheck（避免 raw 像素路径在缩放前被拒）。
- hello `workspace_mm` 须 x/y/z 齐全，否则 product 300。
- 部署约定：`LIMA_RUNTIME_ENV=production`；readiness 提示公网探测只看本地 env。
- 测试：`test_draw_svg_stage`、`test_hello_workspace_complete`。

## 2026-07-21 CR 剩余项：draw workspace / hello profile / B1 / P0-3 清单

- draw：`draw_svg_stage` 用 `resolve_workspace_mm` 作 validate/optimize 目标（去 200/180 硬编码）。
- hello：`register_device_profile(profile_from_hello_frame)`；默认 product 画布，可带 workspace_mm。
- B1：生产禁止 `LIMA_WS_REGISTERED_DEVICE_FALLBACK` 除非 `LIMA_WS_FALLBACK_ALLOW_PRODUCTION=1`（启动 fail）。
- P0-3：`docs/DEVICE_E2E_CHECKLIST_CN.md` + `scripts/check_device_delivery_readiness.py`（云端预检；真机仍需人）。

## 2026-07-21 CR 跟进 W1/W5/W2

- W1：`try_deliver_and_classify` — offline=`queued_no_delivery`，在线 drain 失败=`queued`，成功=`sent`；异常打 warning 日志。
- W5：`check_code_size` 排除 `.tmp` / `_tmp*` 脚本。
- W2：`safe_point`/`validate_run_path_params` 支持 `workspace_mm`；coordinator 校验传入 complete profile。

## 2026-07-21 文档再检查与第三轮清理

- 修死链：ONLINE_DISTRIBUTIONS / xiaozhi_api_openapi / system-slimdown / JDCLOUD_NEWAPI。
- `JDCLOUD_RUNTIME_STATUS`、`lima-slimdown-design`、`XIAOZHI_INTEGRATION_GAP`、写字机稳定性计划压成现行摘要。
- docs-site：首页/getting-started/chat/images/认证改为 DLC 定位；chat completions 标退役。

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
