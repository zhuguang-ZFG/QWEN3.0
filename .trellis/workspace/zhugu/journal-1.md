# Journal - zhugu (Part 1)

> AI development session journal
> Started: 2026-07-14

---


## Session 1: P2 代码审查 + A2A 舰队复核修复 + 60+ 存量落盘

**Date**: 2026-07-16
**Task**: P2 代码审查 + A2A 舰队复核修复 + 60+ 存量落盘
**Package**: root
**Branch**: `fix/code-review-p2-hardening`

### Summary

A2A 8-agent 对 working-tree diff 复核出 8 findings（7 CONFIRMED + 1 REFUTED）。修复 7 处：idempotency L1 无界泄漏(惰性清扫+4096 上限，保留 recovery barrier)、status WS 槽泄漏(accept 移入 try/finally)、voice WS 三处 wait_for 超时未捕获、admin 订阅者被静默过滤(补 role)、status WS 轮询阻塞(to_thread)、notifications N+1(to_thread)、dlc_mcp 静默吞异常。测试驱动修正了 idempotency 方案(初选释放 L1 破坏 recovery barrier，改惰性清扫)。随后落盘 60+ 会话前存量改动(队列抽取/认证 fail-closed/部署门禁/voice 链/infra)，10 commit 分主题提交，全量 1780 passed。submodule manifest 文案优化一并 bump pin。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `d873b917` | (see git log) |
| `4f7e2aa0` | (see git log) |
| `2f1ee951` | (see git log) |
| `f7089f1a` | (see git log) |
| `1ad558d6` | (see git log) |
| `bfc44c46` | (see git log) |
| `e8f1588d` | (see git log) |
| `2e7745f1` | (see git log) |
| `3f4f06b9` | (see git log) |
| `248ba3cc` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

---


## Session 2: 00-bootstrap-guidelines — 填充 esp32S_XYZ 固件后端规范

**Date**: 2026-07-16
**Task**: 00-bootstrap-guidelines (P1 Trellis 引导任务)
**Package**: esp32S_XYZ
**Branch**: `main`

### Summary

完成 Trellis bootstrap 引导任务，为 esp32S_XYZ 双 MCU 固件子模块填充实质开发规范（此前 `backend/` 为空、包级 index 仅写「沿用上游、不加规则」）。后台 Explore agent 深度调查 7 维度（U1 Grbl/U8 xiaozhi 固件、4 通信边界 schema、测试体系、上游约定、docs、工具链），据此撰写 4 份 backend 规范。核心原则遵循 PRD「document reality, not ideals」——4 轮批量核实所有承重事实（版本号/文件路径/GPIO 常量/schema 枚举/章节号），逐一对真实代码库比对。

### Main Changes

- `backend/index.md`：双 MCU 架构、技术栈版本表、改动边界铁律（U1 只改机型头 `dlc_motor_control_p1.h` / U8 只改板目录 `dlc-motor-control-p1-ai/`，上游代码不改）、make 命令速查
- `backend/u1-grbl.md`：Grbl_Esp32 clang-format（ColumnLimit 140/Indent 4）、机型文件结构、运动能力现状表、strapping pin {0,3,45,46} 风险、真实代码示例、FluidNC 迁移方向
- `backend/u8-xiaozhi.md`：xiaozhi camelCase 方法名约定（与 U1 snake_case 不同）、cJSON/NVS/HTTPS 强制/OTA A/B/超时禁 0 红线、未落地项（抬笔/独立急停/龙门矫正）
- `backend/edge-d-contract.md`：Edge-D `@{json}\n` 帧、11 cmd/7 state 枚举、alarm_code(E001-E009) vs error_code(恒 null) 区分、字段演进铁律（先改 schema→fake→固件→test_edge_d_firmware_static.py）、工具链
- 修订 `spec/esp32S_XYZ/index.md`：去掉过时的「xiaozhi-esp32-server 上游/主仓库不加规则」，指向 backend/
- 勾选 PRD 两项完成

### 核验修正（document reality 的价值）

- agent 转述的 `STEPPERS_ALWAYS_ENABLED` 不存在 → 真实是 `DEFAULT_STEPPER_IDLE_LOCK_TIME=25`（ms，`Stepper.cpp` `*1000` 转 μs，停止后释放使能让 Z 弹簧回 pen-up）
- agent 转述的 `MotorClass.h` 不存在 → 真实为基类 `Motor.h` + 工厂 `Motors.cpp`
- agent 混淆 `alarm_code`/`error_code` → 契约文档精确区分
- 宏形态 `GPIO_NUM_46`（非 `GPIO46_`）
- 8 个架构文档章节号引用（§5.4/§10bis.7/9/10/12/§14/§15.4/§16.5）逐一对 111KB 主纲核对，全部语义匹配

### Git Commits

| Hash | Message |
|------|---------|
| `8589c6e6` | docs(esp32S_XYZ): 填充固件后端开发规范 |
| `8715d89c` | chore(task): archive 00-bootstrap-guidelines |

### Testing

- [OK] 纯 docs 改动，无代码变更；事实核验通过 4 轮批量比对 + 章节号逐条核对

### Status

[OK] **Completed** — bootstrap 任务归档至 `archive/2026-07/`

### Next Steps

- 后续新开发者将获得 `00-join-<slug>` onboarding 任务（非 bootstrap）
- 固件规范里标注的未落地项（抬笔保护/独立急停/龙门矫正）为独立实施任务
