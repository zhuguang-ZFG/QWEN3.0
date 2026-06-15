# Edge-C route_policy 硬契约实施计划

> **状态：已关闭（2026-06-15）**
>
> 关闭证据见 `progress.md` 的「2026-06-15 Edge-C route_policy 硬契约」和 `findings.md` 的同名条目。已完成 Edge-C schema required 化、固件 DeviceServer `route_policy` 补全、云端 `xiaozhi_compat` 补全、回归测试和 `esp32S_XYZ` 子模块指针更新至 `a4cab61`。
>
> 下方 checkbox 为实施时的历史执行轨迹，不表示当前待办。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Edge-C motion_task schema 的 route_policy 从软约束提升为硬约束（required），并修复固件 DeviceServer 与云端 xiaozhi_compat 两条 Edge-C 下行链路，使"设备收到的下行帧必带 route_policy"成为不可违反的契约。

**Architecture:** 跨仓库两阶段——固件子模块（esp32S_XYZ）先行，主仓库（QWEN3.0）后行并更新 submodule 指针。固件 DeviceServer 复制纯函数 `generate_route_policy`（语义对齐云端 `resolve_device_route_policy`），透传优先、缺失才生成；云端 xiaozhi_compat 复用 `resolve_device_route_policy` 单一真相源。edge_b 全程不动。

**Tech Stack:** Python 3.10（主仓库 + 固件 DeviceServer）、JSON Schema draft 2020-12、pytest、ruff。

**关联 spec:** `docs/superpowers/specs/2026-06-15-edge-c-route-policy-hard-contract-design.md`

---

## 文件结构总览

### 固件子模块（esp32S_XYZ）—— 在 `D:\QWEN3.0\esp32S_XYZ` 仓库内提交

| 文件 | 操作 | 职责 |
|------|------|------|
| `docs/schemas/edge_c/motion_task.schema.json` | 修改 | 顶层 required 追加 route_policy |
| `docs/schemas/edge_c/examples/motion_task.downlink.json` | 修改 | 补 device_control route_policy |
| `server/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/motionHandle.py` | 修改 | 复制 generate_route_policy + 下行帧补 route_policy |
| `tools/fake_lima_u8/tests/test_route_policy.py` | 新建 | 守护 route_policy 必含与透传语义 |

### 主仓库（QWEN3.0）—— 在 `D:\QWEN3.0` 仓库内提交

| 文件 | 操作 | 职责 |
|------|------|------|
| `routes/xiaozhi_compat/gateway.py` | 修改 | build_gateway_task 补 route_policy |
| `tests/test_xiaozhi_compat_route_policy.py` | 新建 | 守护 gateway task 含合法 route_policy |
| `esp32S_XYZ`（submodule 指针） | 修改 | 指向固件新 commit |
| `STATUS.md` / `progress.md` / `findings.md` | 修改 | 记录关闭证据 |

---

## 阶段 A：固件子模块（先行，必须在主仓库之前完成并推送）

### Task A1: 固件 schema required 化 + example 补字段

**仓库:** `D:\QWEN3.0\esp32S_XYZ`（固件子模块，独立 git 仓库）

**Files:**
- Modify: `docs/schemas/edge_c/motion_task.schema.json:7`
- Modify: `docs/schemas/edge_c/examples/motion_task.downlink.json`

- [ ] **Step 1: 修改 edge_c schema required**

打开 `D:\QWEN3.0\esp32S_XYZ\docs\schemas\edge_c\motion_task.schema.json`，把第 7 行：
```json
  "required": ["type", "task_id", "device_id", "capability"],
```
改为：
```json
  "required": ["type", "task_id", "device_id", "capability", "route_policy"],
```

- [ ] **Step 2: 给 edge_c downlink example 补 route_policy**

打开 `D:\QWEN3.0\esp32S_XYZ\docs\schemas\edge_c\examples\motion_task.downlink.json`，当前内容：
```json
{
  "type": "motion_task",
  "task_id": "550e8400-e29b-41d4-a716-446655440003",
  "device_id": "dev_SN001",
  "account_id": 42,
  "capability": "home",
  "source": "client",
  "request_id": "req-001",
  "trace_id": "trace-001",
  "params": {},
  "constraints": { "timeout_ms": 30000, "safety_level": "strict" }
}
```
在 `capability` 之后、`source` 之前插入 route_policy（capability=home 是控制类，对应 device_control/deterministic/none，与 `docs/schemas/examples/device_control.json` 一致）：
```json
{
  "type": "motion_task",
  "task_id": "550e8400-e29b-41d4-a716-446655440003",
  "device_id": "dev_SN001",
  "account_id": 42,
  "capability": "home",
  "route_policy": {
    "route_role": "device_control",
    "model_required": false,
    "primary_strategy": "deterministic",
    "artifact_required": "none"
  },
  "source": "client",
  "request_id": "req-001",
  "trace_id": "trace-001",
  "params": {},
  "constraints": { "timeout_ms": 30000, "safety_level": "strict" }
}
```

- [ ] **Step 3: 运行 schema 校验，确认 example 匹配 schema**

Run（在固件子模块根目录）：
```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
```
Expected: 无 error 输出（exit 0）。如果报 `motion_task.downlink.json does not match any schema`，说明 route_policy 字段名/值有误，回 Step 2 核对。

- [ ] **Step 4: 运行固件 CI schema 测试**

Run:
```powershell
python -m pytest tests/ci/test_validate_schemas.py tests/ci/test_docs_m0_m1_closeout.py -v
```
Expected: 全部 PASS。`test_docs_m0_m1_closeout.py` 断言 `passed=62 failed=0`——因为 example 数量没变（只补了字段），总数应仍是 62。若 passed 变成 61 或 63，检查是否误删/误增了 example 文件。

- [ ] **Step 5: 提交（固件仓库）**

```powershell
cd D:\QWEN3.0\esp32S_XYZ
git checkout -b fix/edge-c-route-policy-required
git add docs/schemas/edge_c/motion_task.schema.json docs/schemas/edge_c/examples/motion_task.downlink.json
git commit -m "fix(schema): make route_policy required on edge_c motion_task

Promote route_policy from soft to hard constraint on the Edge-C
motion_task schema (DeviceServer -> U8 WSS downlink). The cloud
device_gateway main path already attaches route_policy on every task
path (covered by test_device_gateway_route_policy_retention.py); this
makes the contract explicit at the schema layer.

edge_b stays soft (BusinessServer/Java link not yet generating
route_policy). Update the home downlink example to carry the
device_control route_policy so it matches the hardened schema."
```

---

### Task A2: 固件 DeviceServer 复制 generate_route_policy + 下行帧补全

**仓库:** `D:\QWEN3.0\esp32S_XYZ`

**Files:**
- Modify: `server/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/motionHandle.py`
- Test: `tools/fake_lima_u8/tests/test_route_policy.py`（新建）

- [ ] **Step 1: 写失败的测试**

创建 `D:\QWEN3.0\esp32S_XYZ\tools\fake_lima_u8\tests\test_route_policy.py`：

> **import 方式说明（确定，非猜测）：** motionHandle.py 所在路径 `server/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/` 上没有任何 `__init__.py`，且目录名含连字符（不是合法 Python 包名），因此**必须**用 `importlib.util` 按文件路径加载，不能用普通 `import`。固件既有 `test_app.py` 也是用 `sys.path.insert` 加载同目录包，这里同理。

```python
"""Tests for route_policy generation in motionHandle.build_motion_task_websocket_message.

Guards the Edge-C hard contract: every downlink motion_task must carry
a valid route_policy. Semantics must stay aligned with the cloud-side
device_gateway/model_routing.py:resolve_device_route_policy.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

# motionHandle.py lives under a non-package path (hyphenated dirs, no
# __init__.py), so load it by file path.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = (
    _REPO_ROOT / "server" / "xiaozhi-esp32-server" / "main"
    / "xiaozhi-server" / "core" / "handle" / "motionHandle.py"
)
_spec = importlib.util.spec_from_file_location("motionHandle", _MODULE_PATH)
motionHandle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motionHandle)

build_motion_task_websocket_message = motionHandle.build_motion_task_websocket_message
generate_route_policy = motionHandle.generate_route_policy

_VALID_ROLES = {
    "device_control", "device_write", "device_draw",
    "device_vector", "device_unknown",
}
_VALID_STRATEGIES = {
    "deterministic", "image_then_vector", "svg_vector",
    "provided_path", "planner_required",
}
_VALID_ARTIFACTS = {"none", "preview_svg", "vector_path"}


def _assert_valid_route_policy(testcase, policy):
    testcase.assertIsInstance(policy, dict)
    testcase.assertIn(policy["route_role"], _VALID_ROLES)
    testcase.assertIsInstance(policy["model_required"], bool)
    testcase.assertIn(policy["primary_strategy"], _VALID_STRATEGIES)
    testcase.assertIn(policy["artifact_required"], _VALID_ARTIFACTS)


class TestGenerateRoutePolicy(unittest.TestCase):
    def test_control_capability_is_device_control(self):
        for cap in ("home", "pause", "resume", "stop", "estop", "get_device_info"):
            policy = generate_route_policy(cap)
            self.assertEqual(policy["route_role"], "device_control")
            self.assertFalse(policy["model_required"])
            self.assertEqual(policy["primary_strategy"], "deterministic")
            self.assertEqual(policy["artifact_required"], "none")

    def test_run_path_is_device_vector(self):
        policy = generate_route_policy("run_path")
        self.assertEqual(policy["route_role"], "device_vector")
        self.assertEqual(policy["primary_strategy"], "provided_path")

    def test_unknown_capability_is_device_unknown(self):
        policy = generate_route_policy("nonsense_cap")
        self.assertEqual(policy["route_role"], "device_unknown")
        self.assertTrue(policy["model_required"])
        self.assertEqual(policy["primary_strategy"], "planner_required")


class TestBuildMotionTaskRoutePolicy(unittest.TestCase):
    def _base_body(self, capability):
        return {
            "task_id": "task-1",
            "device_id": "dev-1",
            "capability": capability,
        }

    def test_route_policy_always_present_for_home(self):
        msg = build_motion_task_websocket_message(self._base_body("home"))
        self.assertEqual(msg["type"], "motion_task")
        _assert_valid_route_policy(self, msg["route_policy"])
        self.assertEqual(msg["route_policy"]["route_role"], "device_control")

    def test_route_policy_always_present_for_run_path(self):
        msg = build_motion_task_websocket_message(self._base_body("run_path"))
        _assert_valid_route_policy(self, msg["route_policy"])
        self.assertEqual(msg["route_policy"]["route_role"], "device_vector")

    def test_route_policy_always_present_for_unknown(self):
        msg = build_motion_task_websocket_message(self._base_body("weird"))
        _assert_valid_route_policy(self, msg["route_policy"])
        self.assertEqual(msg["route_policy"]["route_role"], "device_unknown")

    def test_route_policy_passthrough_not_overwritten(self):
        body = self._base_body("run_path")
        body["route_policy"] = {
            "route_role": "device_draw",
            "model_required": True,
            "primary_strategy": "image_then_vector",
            "artifact_required": "vector_path",
        }
        msg = build_motion_task_websocket_message(body)
        self.assertEqual(msg["route_policy"]["route_role"], "device_draw",
                         "upstream route_policy must be passed through, not regenerated")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
python -m pytest tools/fake_lima_u8/tests/test_route_policy.py -v
```
Expected: FAIL，`ImportError`/`AttributeError: module 'motionHandle' has no attribute 'generate_route_policy'`（因为 motionHandle.py 还没加这个函数，且产出帧还没 route_policy 键）。

- [ ] **Step 3: 在 motionHandle.py 实现 generate_route_policy + 补全逻辑**

打开 `D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server\main\xiaozhi-server\core\handle\motionHandle.py`。当前全文：
```python
"""M2.4：motion_task 下行至设备 WebSocket 的负载构造与派发（仅 DeviceServer 侧）。"""

from __future__ import annotations

from typing import Any, Mapping


def build_motion_task_websocket_message(body: Mapping[str, Any]) -> dict[str, Any]:
    """与实施计划 v2 §M2.4 一致：WSS 帧 type=motion_task。"""
    params = body.get("params")
    constraints = body.get("constraints")
    return {
        "type": "motion_task",
        "task_id": body.get("task_id"),
        "device_id": body.get("device_id"),
        "account_id": body.get("account_id"),
        "capability": body.get("capability"),
        "source": body.get("source"),
        "request_id": body.get("request_id"),
        "trace_id": body.get("trace_id"),
        "params": params if isinstance(params, dict) else {},
        "constraints": constraints if isinstance(constraints, dict) else {},
    }
```

替换为（新增 CONTROL_CAPABILITIES + generate_route_policy，build 函数补 route_policy 透传/补全逻辑）：
```python
"""M2.4：motion_task 下行至设备 WebSocket 的负载构造与派发（仅 DeviceServer 侧）。"""

from __future__ import annotations

from typing import Any, Mapping

# Control capabilities that never need a model or path planning.
# 须与 device_gateway/model_routing.py:resolve_device_route_policy 语义保持同步。
CONTROL_CAPABILITIES = frozenset({
    "home", "pause", "resume", "stop", "estop", "get_device_info",
})


def generate_route_policy(capability: str) -> dict[str, Any]:
    """Generate route_policy for an Edge-C motion_task from its capability.

    Semantics MUST stay aligned with the cloud-side
    device_gateway/model_routing.py:resolve_device_route_policy so the
    Edge-C downlink frame's route_role is consistent whether the policy
    is resolved in the cloud or filled in here at the DeviceServer.
    """
    if capability in CONTROL_CAPABILITIES:
        return {
            "route_role": "device_control",
            "model_required": False,
            "primary_strategy": "deterministic",
            "artifact_required": "none",
        }
    if capability == "run_path":
        return {
            "route_role": "device_vector",
            "model_required": False,
            "primary_strategy": "provided_path",
            "artifact_required": "preview_svg",
        }
    return {
        "route_role": "device_unknown",
        "model_required": True,
        "primary_strategy": "planner_required",
        "artifact_required": "none",
    }


def build_motion_task_websocket_message(body: Mapping[str, Any]) -> dict[str, Any]:
    """与实施计划 v2 §M2.4 一致：WSS 帧 type=motion_task。

    Edge-C 硬契约：每个下行帧必带 route_policy。若 body 已含则透传
    （尊重上游决策），否则按 capability 生成。
    """
    params = body.get("params")
    constraints = body.get("constraints")
    route_policy = body.get("route_policy")
    if not isinstance(route_policy, dict):
        route_policy = generate_route_policy(str(body.get("capability", "")))
    return {
        "type": "motion_task",
        "task_id": body.get("task_id"),
        "device_id": body.get("device_id"),
        "account_id": body.get("account_id"),
        "capability": body.get("capability"),
        "source": body.get("source"),
        "route_policy": route_policy,
        "request_id": body.get("request_id"),
        "trace_id": body.get("trace_id"),
        "params": params if isinstance(params, dict) else {},
        "constraints": constraints if isinstance(constraints, dict) else {},
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```powershell
python -m pytest tools/fake_lima_u8/tests/test_route_policy.py -v
```
Expected: 7 个测试全部 PASS（3 个 generate_route_policy + 4 个 build_motion_task）。

- [ ] **Step 5: 运行既有 fake_lima_u8 测试，确认未破坏**

Run:
```powershell
python -m pytest tools/fake_lima_u8/tests/ -v
```
Expected: 全部 PASS（既有 test_app.py + 新 test_route_policy.py）。

- [ ] **Step 6: 运行固件单测（motion_task 相关）**

Run:
```powershell
python -m unittest tests.ci.test_validate_schemas -v
```
Expected: PASS。

- [ ] **Step 7: 提交（固件仓库）**

```powershell
cd D:\QWEN3.0\esp32S_XYZ
git add server/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/motionHandle.py tools/fake_lima_u8/tests/test_route_policy.py
git commit -m "feat(device-server): attach route_policy to Edge-C downlink frame

DeviceServer now guarantees every motion_task WSS downlink frame
carries a route_policy, satisfying the hardened Edge-C schema. If the
upstream body already provides one it is passed through untouched;
otherwise generate_route_policy(capability) fills it in.

generate_route_policy semantics align with the cloud-side
device_gateway/model_routing.py:resolve_device_route_policy (run_path
-> device_vector), NOT the legacy esp32s_adapter copy (which used
device_write). Docstring records the must-stay-in-sync invariant.

Tests cover all three capability branches plus passthrough."
```

---

### Task A3: 固件仓库推送（先行推送，主仓库才能引用）

**仓库:** `D:\QWEN3.0\esp32S_XYZ`

- [ ] **Step 1: 推送固件分支**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
git push -u origin fix/edge-c-route-policy-required
```
Expected: 推送成功。记录固件新 commit hash（`git rev-parse HEAD`）。

- [ ] **Step 2: 确认固件仓库工作区干净**

Run:
```powershell
git status
```
Expected: `nothing to commit, working tree clean`。

> **关键 gate:** 固件必须先推送完成，主仓库 Task B2 才能更新 submodule 指针。在此暂停，确认固件 origin 上已有这个 commit。

---

## 阶段 B：主仓库（后行，固件推送完成后）

### Task B1: 云端 xiaozhi_compat/gateway.py 补 route_policy

**仓库:** `D:\QWEN3.0`（主仓库）

**Files:**
- Modify: `routes/xiaozhi_compat/gateway.py:62-79`
- Test: `tests/test_xiaozhi_compat_route_policy.py`（新建）

- [ ] **Step 1: 写失败的测试**

创建 `D:\QWEN3.0\tests\test_xiaozhi_compat_route_policy.py`：
```python
"""Tests that xiaozhi_compat gateway tasks always carry a valid route_policy.

Guards the Edge-C hard contract on the cloud side: build_gateway_task
must attach route_policy so the downlink frame is contract-compliant
regardless of which entry path produced the task.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routes.xiaozhi_compat.gateway import build_gateway_task

_VALID_ROLES = {
    "device_control", "device_write", "device_draw",
    "device_vector", "device_unknown",
}
_VALID_STRATEGIES = {
    "deterministic", "image_then_vector", "svg_vector",
    "provided_path", "planner_required",
}
_VALID_ARTIFACTS = {"none", "preview_svg", "vector_path"}


def _assert_valid_route_policy(policy):
    assert isinstance(policy, dict)
    assert policy["route_role"] in _VALID_ROLES
    assert isinstance(policy["model_required"], bool)
    assert policy["primary_strategy"] in _VALID_STRATEGIES
    assert policy["artifact_required"] in _VALID_ARTIFACTS


def test_run_path_task_has_device_vector_route_policy():
    task, err = build_gateway_task(
        device_id="dev-1",
        intent="run_path",
        params={"path": [{"x": 0, "y": 0}, {"x": 10, "y": 10}], "feed": 600},
        source="client",
        request_id="req-1",
    )
    assert err is None, f"unexpected error: {err}"
    assert task is not None
    _assert_valid_route_policy(task["route_policy"])
    assert task["route_policy"]["route_role"] == "device_vector"


def test_home_task_has_device_control_route_policy():
    task, err = build_gateway_task(
        device_id="dev-1",
        intent="home",
        params={},
        source="client",
        request_id="req-2",
    )
    assert err is None, f"unexpected error: {err}"
    assert task is not None
    _assert_valid_route_policy(task["route_policy"])
    assert task["route_policy"]["route_role"] == "device_control"
    assert task["route_policy"]["primary_strategy"] == "deterministic"
```

> **注意：** `build_gateway_task` 内部调 `policy_engine.decide(fw_rev="")`、`simulate_motion`、`workflow.register/advance`、`task_store.create_task_state`——这些是模块级副作用。如果测试因这些副作用报错（如 workflow 状态冲突、store 未初始化），在测试顶部加 fixture 隔离，或在 `build_gateway_task` 调用前重置 workflow/store。优先用最小补丁让它跑通；若 `task_store` 需要 Redis，设环境变量 `LIMA_DEVICE_TASK_STORE=memory`。先运行 Step 2 看实际报什么，再决定加多少 fixture。

- [ ] **Step 2: 运行测试确认失败**

Run:
```powershell
cd D:\QWEN3.0
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_xiaozhi_compat_route_policy.py -v
```
Expected: FAIL，`KeyError: 'route_policy'`（task 字典里没有 route_policy 键）。若因 workflow/store 副作用报其他错，按 Step 1 的注意事项加 fixture。

- [ ] **Step 3: 修改 build_gateway_task 补 route_policy**

打开 `D:\QWEN3.0\routes\xiaozhi_compat\gateway.py`。在第 61 行（`workflow.advance(...)` 之后）与第 62 行（`task = {` 之前）之间，插入 route_policy 解析；并在 task 字典里加 `"route_policy": route_policy,`。

具体：找到这段：
```python
    workflow.advance(task_id, TaskState.WAITING_APPROVAL if needs_approval else TaskState.READY_TO_DISPATCH)
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "source": source,
        "params": sanitized,
        "policy": policy.to_dict(),
        "simulation": sim.to_dict(),
        "workflow_state": TaskState.WAITING_APPROVAL.value if needs_approval else TaskState.READY_TO_DISPATCH.value,
        "compat": {"intent": intent},
    }
```
替换为：
```python
    workflow.advance(task_id, TaskState.WAITING_APPROVAL if needs_approval else TaskState.READY_TO_DISPATCH)
    from device_gateway.model_routing import resolve_device_route_policy

    route_policy = resolve_device_route_policy(
        {"capability": capability, "params": sanitized}, device_id=device_id,
    )
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "source": source,
        "route_policy": route_policy,
        "params": sanitized,
        "policy": policy.to_dict(),
        "simulation": sim.to_dict(),
        "workflow_state": TaskState.WAITING_APPROVAL.value if needs_approval else TaskState.READY_TO_DISPATCH.value,
        "compat": {"intent": intent},
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```powershell
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_xiaozhi_compat_route_policy.py -v
```
Expected: 2 个测试 PASS。

- [ ] **Step 5: ruff 检查**

Run:
```powershell
python -m ruff check routes/xiaozhi_compat/gateway.py tests/test_xiaozhi_compat_route_policy.py
```
Expected: `All checks passed!`

- [ ] **Step 6: 运行回归测试，确认未破坏主路径**

Run:
```powershell
python -m pytest tests/test_device_gateway_route_policy_retention.py tests/test_device_gateway_model_routing.py -v
```
Expected: 全部 PASS（retention 5 个 + model_routing 既有测试）。

- [ ] **Step 7: 提交（主仓库，暂不 push，等 Task B2 submodule 指针一起）**

```powershell
cd D:\QWEN3.0
git add routes/xiaozhi_compat/gateway.py tests/test_xiaozhi_compat_route_policy.py
git commit -m "feat(xiaozhi-compat): attach route_policy to gateway tasks

build_gateway_task was the only cloud path producing a motion_task
without route_policy. It now calls resolve_device_route_policy (the
single source of truth shared with device_gateway/tasks.py) so the
Edge-C downlink contract holds on this path too. run_path -> device_vector,
home -> device_control, matching the main device_gateway path.

Also aligns route evidence recording: resolve_device_route_policy
writes the per-device route_evidence JSONL, so xiaozhi_compat tasks
now leave the same audit trail as main-path tasks."
```

---

### Task B2: 更新 submodule 指针 + 文档 + 推送

**仓库:** `D:\QWEN3.0`（主仓库）

**Files:**
- Modify: `esp32S_XYZ`（submodule 指针）
- Modify: `STATUS.md`, `progress.md`, `findings.md`

- [ ] **Step 1: 确认固件子模块已在 Task A3 推送的 commit**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
git log --oneline -2
git branch --show-current
```
Expected: 当前分支 `fix/edge-c-route-policy-required`，最新 commit 是 Task A1/A2 的两个提交，且已在 origin（Task A3 已推送）。

- [ ] **Step 2: 回主仓库，更新 submodule 指针**

Run:
```powershell
cd D:\QWEN3.0
git add esp32S_XYZ
git status
```
Expected: `modified: esp32S_XYZ (modified content)` 变为已暂存的 submodule 指针变更。

- [ ] **Step 3: 更新 findings.md**

在 `D:\QWEN3.0\findings.md` 顶部（2026-06-15 路由修复条目之上）插入新条目：
```markdown
## 2026-06-15 Edge-C route_policy 硬契约关闭（阶段 1 缺口 A）

| 证据点 | 内容 |
|--------|------|
| 目标 | 把 Edge-C motion_task schema 的 route_policy 从软约束提升为硬约束 |
| 固件改动 | edge_c schema required 化 + downlink example 补 route_policy + motionHandle.py 复制 generate_route_policy（语义对齐 resolve_device_route_policy，run_path→device_vector）+ 新增 test_route_policy.py（7 测试） |
| 云端改动 | xiaozhi_compat/gateway.py 复用 resolve_device_route_policy 补 route_policy + 新增 test_xiaozhi_compat_route_policy.py（2 测试） |
| 语义统一 | 计划阶段发现 esp32s_adapter/protocol.py 的 run_path→device_write 与权威 resolve（device_vector）不一致；固件复制版以 resolve 为准 |
| 范围外（YAGNI） | edge_b 不改；Java DeviceServerMotionGatewayImpl 不加 route_policy；不动 U1 固件；不加运行时 schema 校验门 |
| 验证 | 固件 validate_schemas + m0_m1_closeout + fake_lima_u8 全过；主仓库 ruff + retention/model_routing 回归全过 |
| 跨仓库顺序 | 固件先 push（Task A3），主仓库后更新 submodule 指针（本 Task） |
```

- [ ] **Step 4: 更新 progress.md**

在 `D:\QWEN3.0\progress.md` 顶部（2026-06-15 路由修复条目之上）插入：
```markdown
## 2026-06-15 Edge-C route_policy 硬契约（阶段 1 缺口 A 收尾）

关闭设备路由契约阶段 1 缺口 A。详见 spec `docs/superpowers/specs/2026-06-15-edge-c-route-policy-hard-contract-design.md`。

- 固件子模块（先行）：edge_c schema required 化、downlink example 补 route_policy、motionHandle.py 复制 generate_route_policy 并对齐 resolve 语义、新增 7 个测试；固件 CI schema 门 + fake_lima_u8 全过；已推送固件 origin。
- 主仓库（后行）：xiaozhi_compat/gateway.py 复用 resolve_device_route_policy 补 route_policy、新增 2 个测试；ruff + retention/model_routing 回归全过；更新 submodule 指针。
- 验证：固件 `validate_schemas.py` + `test_validate_schemas` + `test_docs_m0_m1_closeout` + `fake_lima_u8/tests/` 全过；主仓库 `test_xiaozhi_compat_route_policy` + `test_device_gateway_route_policy_retention` + `test_device_gateway_model_routing` 全过。
```

- [ ] **Step 5: 更新 STATUS.md**

在 `D:\QWEN3.0\STATUS.md` 的「最近完成」或「代码质量」节追加一条（保持该文件既有格式）：
```markdown
- Edge-C motion_task route_policy 硬契约（阶段 1 缺口 A）：schema required 化 + 固件 DeviceServer 与云端 xiaozhi_compat 两条下行链路补 route_policy
```

- [ ] **Step 6: 提交 submodule 指针 + 文档**

```powershell
cd D:\QWEN3.0
git add esp32S_XYZ STATUS.md progress.md findings.md
git commit -m "chore: bump esp32S_XYZ submodule + record edge-c route_policy hard contract

Pulls in the firmware submodule commit that hardens the Edge-C
route_policy contract (schema required + DeviceServer route_policy
generation). Records closeout evidence in STATUS/progress/findings.

Closes roadmap stage 1 gap A."
```

- [ ] **Step 7: 推送主仓库**

Run:
```powershell
git push -u origin design/edge-c-route-policy-hard-contract
```
Expected: 推送成功（主仓库分支 `design/edge-c-route-policy-hard-contract`，含 spec commit + Task B1 commit + 本 Task commit）。

---

## 关闭标准核对

- [ ] 固件：schema/example/motionHandle/test 改动通过固件 CI 门
- [ ] 固件：已 push 到固件 origin（Task A3）
- [ ] 主仓库：gateway + test 通过 ruff + pytest
- [ ] 主仓库：retention/model_routing 回归通过
- [ ] 主仓库：submodule 指针指向固件已推送的 commit
- [ ] 文档：STATUS/progress/findings 已更新
- [ ] 仅暂存相关文件，conventional commit，已推送 origin

## 回滚

若任一阶段失败：
1. 先 revert 主仓库提交（Task B2、B1），避免 submodule 指针悬空
2. 再 revert 固件子模块提交（Task A2、A1）
3. 本次无运行时行为变化（schema 仅 CI 文档层校验，固件软消费 route_policy），回滚零运行时风险
4. 不触及 U1 运动固件
