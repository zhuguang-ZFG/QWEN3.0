# Edge-C motion_task route_policy 硬契约设计

> 日期: 2026-06-15
> 范围: 设备路由契约阶段 1 收尾——缺口 A（schema 硬约束 route_policy）
> 关联路线图: `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` 阶段 1
> 策略: 仅云端严格化（edge_c 硬约束，edge_b 保留软约束）

## 背景与动机

`route_policy` 是设备任务下行的路由证据对象，包含 4 个字段：

```json
{
  "route_role": "device_control|device_write|device_draw|device_vector|device_unknown",
  "model_required": "bool",
  "primary_strategy": "deterministic|image_then_vector|svg_vector|provided_path|planner_required",
  "artifact_required": "none|preview_svg|vector_path"
}
```

阶段 1「设备路由契约」的目标是"每个设备任务都能解释为什么选择了该路由"。经亲自验证，阶段 1 的 5 个步骤实质已完成（4✅ 1🟡），云端 `device_gateway/` 主路径已 100% 在所有任务路径（含成功/阻止/失败/固件不兼容）上附加 route_policy，并由 `tests/test_device_gateway_route_policy_retention.py` 守护。

但 **schema 层面 route_policy 是软约束**——`edge_c/motion_task.schema.json` 顶层 `required` 不含 `route_policy`，允许不带 route_policy 的任务通过校验。本设计把 Edge-C 契约从软约束提升为硬约束，使"设备真正收到的下行帧必带路由证据"成为不可违反的契约。

## 设计决策

### 决策 1：仅 edge_c 严格化，edge_b 保留软约束

**排查结论**：把 route_policy 加入 required 会暴露三处违约：
1. 2 个 edge_c/edge_b example 夹具缺 route_policy（home 控制类）
2. 云端 `routes/xiaozhi_compat/gateway.py:build_gateway_task` 不生成 route_policy
3. 整条 Java BusinessServer + Python DeviceServer 生产链路从头不生成 route_policy

**选择**：仅对 edge_c（DeviceServer→U8 WSS 下行帧）严格化，edge_b（BusinessServer→DeviceServer HTTP）保留软约束。

**理由**：edge_c 是"设备真正收到的帧"，让这一层硬约束即达成阶段 1 核心价值；edge_b 涉及 Java 跨语言改动，范围过大，留待后续周期。本次同步修复 edge_c 链路上的两处 Python 漏点（motionHandle.py、xiaozhi_compat gateway）+ 2 个 edge_c example，使 edge_c 链路自洽。

### 决策 2：固件侧复制 `generate_route_policy` 纯函数

`esp32S_XYZ` 是独立 git submodule 仓库，固件 CI 必须能在无主仓库情况下独立运行。因此固件侧 `motionHandle.py` 内复制一份 `generate_route_policy`（与 `esp32s_adapter/protocol.py:10-32` 一致的 32 行纯函数），不跨仓库 import。

**复制可接受的依据**：纯函数、无外部依赖、极少变化（capability→policy 静态映射）。在 docstring 标注"须与 `esp32s_adapter/protocol.py:generate_route_policy` 保持同步"，双端测试守护一致性。

### 决策 3：云端复用 `resolve_device_route_policy`（单一真相源）

主仓库内 `xiaozhi_compat/gateway.py` 直接 import `device_gateway.model_routing.resolve_device_route_policy`，与 `device_gateway/tasks.py:62` 主路径完全一致，不复制。

### 决策 4：DeviceServer 透传优先、缺失才生成

`motionHandle.build_motion_task_websocket_message` 优先透传 body 里已有的 route_policy（尊重上游决策），仅在缺失时用 `generate_route_policy` 补全。DeviceServer 是"契约补全者"而非"决策覆盖者"。

## 改动清单

### 固件子模块仓库（esp32S_XYZ）——先行

| 文件 | 改动 |
|------|------|
| `docs/schemas/edge_c/motion_task.schema.json` | 第 7 行 `required` 数组末尾追加 `"route_policy"` |
| `docs/schemas/edge_c/examples/motion_task.downlink.json` | 补 `route_policy` 对象：`{route_role:"device_control", model_required:false, primary_strategy:"deterministic", artifact_required:"none"}`（home 控制类，与 device_control.json 示例一致） |
| `server/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/motionHandle.py` | 新增 `CONTROL_CAPABILITIES` 常量 + `generate_route_policy(capability)` 纯函数（复制自 esp32s_adapter/protocol.py）；`build_motion_task_websocket_message` 增加 route_policy：body 已含则透传，否则生成 |
| `tools/fake_lima_u8/tests/test_route_policy.py`（新增） | `test_route_policy_always_present`（home/run_path/未知三种 body 必含合法 route_policy）+ `test_route_policy_passthrough`（body 自带不被覆盖） |

**edge_b 完全不动**：`edge_b/motion_task.schema.json`、`edge_b/examples/motion_task.request.json` 均不改（保留软约束）。

### 主仓库（QWEN3.0）——后行

| 文件 | 改动 |
|------|------|
| `routes/xiaozhi_compat/gateway.py` | `build_gateway_task` 构造 task 前调 `resolve_device_route_policy({"capability":capability,"params":sanitized}, device_id=device_id)`，task 字典加 `"route_policy": route_policy` |
| `tests/test_xiaozhi_compat_route_policy.py`（新增） | `test_build_gateway_task_includes_route_policy`（run_path/home 返回 task 含合法 route_policy）+ `test_build_gateway_task_route_policy_matches_capability`（run_path→device_vector，home→device_control） |
| `esp32S_XYZ`（submodule 指针） | 更新指向固件仓库新 commit |
| `STATUS.md` / `progress.md` / `findings.md` | 记录关闭证据 |

## 语义对齐说明（设计不变量）

xiaozhi_compat gateway 的 capability 经 `gateway_capability` 映射后，route_policy 解析结果：

| intent | 映射 capability | route_role | primary_strategy | 说明 |
|--------|----------------|-----------|------------------|------|
| run_path | run_path | device_vector | provided_path | 与主路径一致 |
| home | home | device_control | deterministic | 控制类 |
| calibrate | home | device_control | deterministic | 同 home |
| draw_image | run_path | device_vector | provided_path | gateway 既有降级语义（draw_image→run_path），本次不修正为 device_draw |

**副作用（正向）**：gateway 调用 `resolve_device_route_policy` 会顺带触发 `record_route_evidence` 写设备级路由证据 JSONL，使 xiaozhi_compat 路径与 device_gateway 主路径在路由证据记录上对齐（之前 gateway 路径完全无路由证据）。

## 测试矩阵

| 仓库 | 测试文件 | 类型 | 断言 |
|------|---------|------|------|
| 固件 | `tools/fake_lima_u8/tests/test_route_policy.py`（新） | 单元 | route_policy 必含且合法；passthrough 不覆盖 |
| 固件 | `tests/ci/test_validate_schemas.py`（既有） | CI 门 | example 补字段后 `errors==[]` |
| 固件 | `tests/ci/test_docs_m0_m1_closeout.py`（既有） | CI 门 | `passed=62 failed=0` 仍成立 |
| 主仓库 | `tests/test_xiaozhi_compat_route_policy.py`（新） | 单元 | gateway task 含合法 route_policy；role 匹配 capability |
| 主仓库 | `tests/test_device_gateway_route_policy_retention.py`（既有） | 回归 | 5 个 retention 测试仍通过 |
| 主仓库 | `tests/test_device_gateway_model_routing.py`（既有） | 回归 | 主路径未破坏 |

## 验证命令

**固件子模块（先行）**：
```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m pytest tests/ci/test_validate_schemas.py tests/ci/test_docs_m0_m1_closeout.py -v
python -m pytest tools/fake_lima_u8/tests/ -v
python -m unittest tests.ci.test_validate_schemas -v
```

**主仓库（后行）**：
```powershell
cd D:\QWEN3.0
python -m pytest tests/test_xiaozhi_compat_route_policy.py tests/test_device_gateway_route_policy_retention.py tests/test_device_gateway_model_routing.py -v
python -m ruff check routes/xiaozhi_compat/gateway.py
```

## 跨仓库提交顺序（遵循路线图原则#6）

```
步骤1（先行）: 固件子模块仓库 esp32S_XYZ
  - edge_c schema required 化
  - edge_c example 补 route_policy
  - motionHandle.py 复制 generate_route_policy + 补全逻辑
  - 新增 test_route_policy.py
  - ruff/pytest 通过后 commit + push 固件 origin

步骤2（后行）: 主仓库 QWEN3.0
  - 更新 esp32S_XYZ submodule 指针（指向步骤1的 commit）
  - xiaozhi_compat/gateway.py 补 route_policy
  - 新增 test_xiaozhi_compat_route_policy.py
  - ruff/pytest 通过后 commit + push 主仓库 origin
```

**关键约束**：步骤1 必须先完成并推送，步骤2 才能更新 submodule 指针，否则指针指向未推送的 commit 导致他人 clone 失败。

## 回滚策略

- **风险等级：低**。本次无运行时行为变化——schema 校验只在 CI 文档层；固件运行时不校验 schema；route_policy 对固件（C++ grbl）和假 U8 都是软消费（缺失时跳过证据记录，不崩溃）。
- **回滚顺序**：先 revert 主仓库（步骤2），再 revert 固件子模块（步骤1），避免主仓库 submodule 指针悬空。
- **不触及**：U1 运动固件（C++ grbl）——路线图阶段 1 晋升规则明确"本阶段不更改 U1 运动固件"。

## 明确不做的事（YAGNI）

- ❌ edge_b schema/example 不改（Java/Python BusinessServer 链路保留软约束）
- ❌ 不给 Java `DeviceServerMotionGatewayImpl` 加 route_policy（跨语言、范围外）
- ❌ 不"修正" gateway 的 draw_image→run_path 降级语义
- ❌ 不动 U1 运动固件
- ❌ 不加运行时 jsonschema 校验门（契约文档/CI 门严格化即可，运行时拦截留待阶段 5 发布门）

## 关闭标准

1. 固件子模块：schema/example/motionHandle/test 改动通过固件 CI 门（validate_schemas + m0_m1_closeout + fake_lima_u8 测试）
2. 主仓库：gateway + test 通过 ruff + pytest；retention/model_routing 回归测试通过
3. 跨仓库：步骤1 先 push，步骤2 后更新 submodule 指针并 push
4. 文档：STATUS.md / progress.md / findings.md 记录关闭证据
5. 仅暂存相关文件，conventional commit，推送到 origin
