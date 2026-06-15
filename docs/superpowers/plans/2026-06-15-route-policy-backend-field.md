# route_policy backend 字段贯通实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 route_policy 携带本次任务选中的 backend，使粘性路由记忆记到真实 backend（不再是 "unknown"），并为阶段 2 后续子项目铺路。

**Architecture:** 跨仓库两阶段——固件子模块（esp32S_XYZ）先行加 schema 可选 backend 字段 + example 补字段，主仓库后行让 resolve_device_route_policy 复用既有 get_preferred_backend 填充 backend、联动 record_route_evidence，并修正 1 个既有精确相等测试 + 新增 4 个断点修复测试。

**Tech Stack:** Python 3.10、JSON Schema draft 2020-12、pytest、ruff。

**关联 spec:** `docs/superpowers/specs/2026-06-15-route-policy-backend-field-design.md`

---

## 文件结构总览

### 固件子模块（esp32S_XYZ）—— 在 `D:\QWEN3.0\esp32S_XYZ` 仓库内提交

| 文件 | 操作 | 职责 |
|------|------|------|
| `docs/schemas/edge_c/motion_task.schema.json` | 修改 | route_policy 加可选 backend 属性 |
| `docs/schemas/edge_b/motion_task.schema.json` | 修改 | 同步加可选 backend 属性 |
| `docs/schemas/edge_c/examples/motion_task.downlink.json` | 修改 | home 控制类补 backend: "deterministic" |

### 主仓库（QWEN3.0）—— 在 `D:\QWEN3.0` 仓库内提交

| 文件 | 操作 | 职责 |
|------|------|------|
| `device_gateway/model_routing.py` | 修改 | `_policy()` 加 backend 参数；`resolve_device_route_policy` 填充 backend + 联动 record_route_evidence |
| `tests/test_device_gateway_model_routing.py` | 修改 | matrix 测试 4 个 expected 补 backend |
| `tests/test_route_policy_backend_field.py` | 新建 | 4 个断点修复测试 |
| `esp32S_XYZ`（submodule 指针） | 修改 | 指向固件新 commit |
| `STATUS.md` / `progress.md` / `findings.md` | 修改 | 记录关闭证据 |

---

## 阶段 A：固件子模块（先行）

### Task A1: 固件 schema 加可选 backend + example 补字段

**仓库:** `D:\QWEN3.0\esp32S_XYZ`（固件子模块，独立 git 仓库）

**Files:**
- Modify: `docs/schemas/edge_c/motion_task.schema.json`
- Modify: `docs/schemas/edge_b/motion_task.schema.json`
- Modify: `docs/schemas/edge_c/examples/motion_task.downlink.json`

- [ ] **Step 1: 固件仓库建分支**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
git checkout -b fix/route-policy-backend-field
```
Expected: `Switched to a new branch 'fix/route-policy-backend-field'`

- [ ] **Step 2: edge_c schema route_policy 加可选 backend**

打开 `D:\QWEN3.0\esp32S_XYZ\docs\schemas\edge_c\motion_task.schema.json`，找到 route_policy 的 `artifact_required` 属性（约 34-37 行）：
```json
        "artifact_required": {
          "type": "string",
          "enum": ["none", "preview_svg", "vector_path"]
        }
      }
```
在 `artifact_required` 之后、`}` 之前，加 `backend` 属性（注意逗号）：
```json
        "artifact_required": {
          "type": "string",
          "enum": ["none", "preview_svg", "vector_path"]
        },
        "backend": {
          "type": "string",
          "minLength": 0,
          "description": "Selected backend id for this task. Empty when unresolved; 'deterministic' marks the local deterministic resolver (not a real backend)."
        }
      }
```
**关键**：不修改第 23 行的 `required`（backend 保持可选）。`additionalProperties: false`（第 22 行）要求显式声明此属性。

- [ ] **Step 3: edge_b schema route_policy 同步加可选 backend**

打开 `D:\QWEN3.0\esp32S_XYZ\docs\schemas\edge_b\motion_task.schema.json`，做与 Step 2 完全相同的改动（edge_b 的 route_policy 子结构与 edge_c 一致，artifact_required 在 33-36 行）。

- [ ] **Step 4: edge_c downlink example 补 backend**

打开 `D:\QWEN3.0\esp32S_XYZ\docs\schemas\edge_c\examples\motion_task.downlink.json`，当前 route_policy 块（约 8-13 行）：
```json
  "route_policy": {
    "route_role": "device_control",
    "model_required": false,
    "primary_strategy": "deterministic",
    "artifact_required": "none"
  },
```
改为（artifact_required 后加逗号 + backend 行）：
```json
  "route_policy": {
    "route_role": "device_control",
    "model_required": false,
    "primary_strategy": "deterministic",
    "artifact_required": "none",
    "backend": "deterministic"
  },
```

- [ ] **Step 5: 运行 schema 校验**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
```
Expected: `validated=62 passed=62 failed=0`。若报 downlink example `does not match any schema`，检查 backend 字段名/逗号是否正确。

- [ ] **Step 6: 运行固件 CI schema 测试**

Run:
```powershell
python -m pytest tests/ci/test_validate_schemas.py tests/ci/test_docs_m0_m1_closeout.py -p no:cacheprovider -q
```
Expected: 全部 passed（`test_docs_m0_m1_closeout.py` 断言 passed=62，example 数不变所以仍 62）。

- [ ] **Step 7: 提交（固件仓库）**

```powershell
cd D:\QWEN3.0\esp32S_XYZ
git add docs/schemas/edge_c/motion_task.schema.json docs/schemas/edge_b/motion_task.schema.json docs/schemas/edge_c/examples/motion_task.downlink.json
git commit -m "fix(schema): add optional backend field to route_policy" -m "route_policy currently describes what kind of routing is needed (route_role/strategy) but not which backend was selected. Add an optional backend string property to both edge_c and edge_b motion_task schemas so the field can be carried end-to-end. Stays optional for backward compatibility; the cloud resolves and fills it in a follow-up parent-repo commit." -m "Update the edge_c home downlink example to carry backend:'deterministic' (control-class local resolver marker). edge_b top-level soft-contract policy unchanged; only the route_policy sub-structure is kept consistent across edges."
```

---

### Task A2: 固件仓库推送（先行 gate）

**仓库:** `D:\QEN3.0\esp32S_XYZ`

- [ ] **Step 1: 推送固件分支**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
git push -u origin fix/route-policy-backend-field
```
Expected: 推送成功。记录 commit hash（`git rev-parse HEAD`）。

- [ ] **Step 2: 确认固件工作区干净**

Run:
```powershell
git status
```
Expected: `nothing to commit, working tree clean`。

> **关键 gate:** 固件必须先推送，主仓库 Task B3 才能更新 submodule 指针。

---

## 阶段 B：主仓库（后行）

### Task B1: 修正既有 matrix 测试（先让它与新字段对齐）

**仓库:** `D:\QEN3.0`

**Files:**
- Modify: `tests/test_device_gateway_model_routing.py:49-90`

- [ ] **Step 1: 写失败的测试（先改 matrix expected，此时 resolve 还没填 backend，测试会失败）**

打开 `D:\QWEN3.0\tests\test_device_gateway_model_routing.py`，找到 `test_route_policy_matrix_for_hot_device_families`（约 49 行）。当前 4 个 expected dict 是 4 字段。把它们各补 `"backend"` 字段：

第 1 个 case（home，约 53-58 行）改为：
```python
            {
                "route_role": "device_control",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "none",
                "backend": "deterministic",
            },
```
第 2 个 case（write_text，约 61-67 行）改为：
```python
            {
                "route_role": "device_write",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "preview_svg",
                "backend": "deterministic",
            },
```
第 3 个 case（draw_generated 画猫，约 70-76 行）改为：
```python
            {
                "route_role": "device_draw",
                "model_required": True,
                "primary_strategy": "image_then_vector",
                "artifact_required": "vector_path",
                "backend": "dashscope_wanx",
            },
```
第 4 个 case（draw_generated SVG，约 79-85 行）改为：
```python
            {
                "route_role": "device_vector",
                "model_required": False,
                "primary_strategy": "svg_vector",
                "artifact_required": "preview_svg",
                "backend": "opencv_contour",
            },
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```powershell
cd D:\QWEN3.0
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_device_gateway_model_routing.py::test_route_policy_matrix_for_hot_device_families -p no:cacheprovider -q
```
Expected: FAIL。因为 resolve_device_route_policy 还没填 backend，返回的 dict 不含 backend 键，`== expected`（5 字段）失败。

- [ ] **Step 3: 暂不实现，先做 Task B2。**

> 这个 Task 的测试失败状态会由 Task B2 的实现修复。不要在此 commit——matrix 测试修正和 resolve 实现属于同一个逻辑变更，一起在 Task B2 完成后提交。

---

### Task B2: 实现 resolve_device_route_policy 填充 backend

**仓库:** `D:\QEN3.0`

**Files:**
- Modify: `device_gateway/model_routing.py`

- [ ] **Step 1: 修改 `_policy()` 加 backend 参数**

打开 `D:\QWEN3.0\device_gateway\model_routing.py`，找到 `_policy`（约 281 行）：
```python
def _policy(route_role: str, model_required: bool, primary_strategy: str, artifact_required: str) -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
    }
```
改为（加 backend 参数，默认空串；return 加 backend 键）：
```python
def _policy(route_role: str, model_required: bool, primary_strategy: str,
            artifact_required: str, backend: str = "") -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
        "backend": backend,
    }
```

- [ ] **Step 2: 修改 resolve_device_route_policy 填充 backend + 联动 record_route_evidence**

在同一文件找到 `resolve_device_route_policy`（约 126-156 行）。当前末尾：
```python
    else:
        policy = _policy("device_unknown", True, "planner_required", "none")

    # Record route evidence (non-blocking) when device_id is provided
    if device_id:
        record_route_evidence(
            device_id=device_id,
            task_id="",  # task_id generated later in project_to_motion_task
            route_policy=policy,
            reason=f"capability={capability}",
        )

    return policy
```
改为（在 record_route_evidence 之前加 backend 填充；record_route_evidence 调用补 backend 参数）：
```python
    else:
        policy = _policy("device_unknown", True, "planner_required", "none")

    # Select the admitted backend for this role and attach to the policy.
    # get_preferred_backend returns the first entry of DEVICE_ROLE_PREFERENCES
    # for the role (e.g. device_draw -> dashscope_wanx, device_control ->
    # deterministic). Every route_role has at least one preference, so this
    # is never None in practice; the guard keeps it defensive.
    preferred = get_preferred_backend(policy["route_role"])
    policy["backend"] = preferred["backend"] if preferred else ""

    # Record route evidence (non-blocking) when device_id is provided
    if device_id:
        record_route_evidence(
            device_id=device_id,
            task_id="",  # task_id generated later in project_to_motion_task
            route_policy=policy,
            backend=policy["backend"],
            reason=f"capability={capability}",
        )

    return policy
```

> **确认 get_preferred_backend 已定义**：它在同文件约 112 行，返回 `DEVICE_ROLE_PREFERENCES.get(route_role, [])[0]` 或 None。无需新增 import。

- [ ] **Step 3: 运行 matrix 测试确认通过**

Run:
```powershell
cd D:\QWEN3.0
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_device_gateway_model_routing.py::test_route_policy_matrix_for_hot_device_families -p no:cacheprovider -q
```
Expected: PASS。

- [ ] **Step 4: 运行全部 model_routing 测试确认无回归**

Run:
```powershell
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_device_gateway_model_routing.py -p no:cacheprovider -q
```
Expected: 全部 passed（30 个，含修正的 matrix）。

- [ ] **Step 5: ruff 检查**

Run:
```powershell
cd D:\QWEN3.0
python -m ruff check device_gateway/model_routing.py
```
Expected: `All checks passed!`

- [ ] **Step 6: 提交（matrix 修正 + resolve 实现一起）**

```powershell
cd D:\QWEN3.0
git add device_gateway/model_routing.py tests/test_device_gateway_model_routing.py
git commit -m "feat(model-routing): fill backend into route_policy" -m "resolve_device_route_policy now calls the existing get_preferred_backend(route_role) to attach the selected backend to route_policy, and passes it through to record_route_evidence so the JSONL route-evidence log's backend column is no longer empty. Previously route_policy described only the routing kind (route_role/strategy) and tasks.py fell back to 'unknown', which made device_route_memory sticky routing record meaningless preferred_backends=['unknown']." -m "Update test_route_policy_matrix_for_hot_device_families expected dicts to include backend (home/write/unknown -> deterministic, draw cat -> dashscope_wanx, draw svg -> opencv_contour). Other model_routing tests use single-field assertions and are unaffected." -m "Unblocks stage 3 sticky routing (preferred_backends records real values) and is the prerequisite for stage 2 sub-project #1 (registry consolidation)."
```

---

### Task B3: 新增 backend 字段断点修复测试

**仓库:** `D:\QEN3.0`

**Files:**
- Create: `tests/test_route_policy_backend_field.py`

- [ ] **Step 1: 写测试文件**

创建 `D:\QWEN3.0\tests\test_route_policy_backend_field.py`：
```python
"""Tests that route_policy carries a backend field.

Guards the stage-2 sub-project #5 contract: resolve_device_route_policy must
attach the selected backend to route_policy. With the field present,
tasks.py:135 `route_policy.get("backend", "unknown")` resolves to the real
backend instead of 'unknown' whenever the sticky-routing gate passes.
See spec docs/superpowers/specs/2026-06-15-route-policy-backend-field-design.md.
"""
from device_gateway.model_routing import resolve_device_route_policy


def test_resolve_includes_backend_for_all_capability_families():
    # Covers each route_role branch in resolve_device_route_policy.
    cases = [
        ({"capability": "home", "params": {}}, "device_control"),
        ({"capability": "write_text", "params": {"text": "LiMa"}}, "device_write"),
        ({"capability": "draw_generated", "params": {"prompt": "画一只猫"}}, "device_draw"),
        ({"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}}, "device_vector"),
        ({"capability": "run_path", "params": {}}, "device_vector"),
        ({"capability": "totally_unknown_capability", "params": {}}, "device_unknown"),
    ]
    for voice_task, expected_role in cases:
        policy = resolve_device_route_policy(voice_task)
        assert policy["route_role"] == expected_role
        assert "backend" in policy, f"backend key missing for {voice_task['capability']}"
        assert policy["backend"] != "", f"backend empty for {voice_task['capability']}"


def test_backend_matches_device_role_preferences():
    # Real backend for device_draw.
    assert resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "画一只猫"}}
    )["backend"] == "dashscope_wanx"
    # Local markers for the deterministic/local roles.
    assert resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}}
    )["backend"] == "opencv_contour"
    assert resolve_device_route_policy(
        {"capability": "run_path", "params": {}}
    )["backend"] == "opencv_contour"
    assert resolve_device_route_policy(
        {"capability": "home", "params": {}}
    )["backend"] == "deterministic"


def test_resolve_never_returns_unknown_as_backend():
    """Regression guard: the old fallback was 'unknown' at the call site.
    The policy itself must carry a concrete backend value, never the literal
    'unknown' (that was the symptom of the missing field, not a valid value).
    """
    for capability in ("home", "write_text", "draw_generated", "run_path", "nope"):
        policy = resolve_device_route_policy({"capability": capability, "params": {"prompt": "cat"}})
        assert policy["backend"] != "unknown", (
            f"resolve returned backend='unknown' for {capability}; the "
            "backend-field gap is not closed"
        )


def test_policy_factory_includes_backend_with_default():
    """_policy() must accept an optional backend and default to empty string,
    so existing direct callers that omit it do not break."""
    from device_gateway.model_routing import _policy

    full = _policy("device_draw", True, "image_then_vector", "vector_path", "dashscope_wanx")
    assert full["backend"] == "dashscope_wanx"
    default = _policy("device_control", False, "deterministic", "none")
    assert default["backend"] == ""
```

> **设计说明**：这些测试聚焦 #5 的直接修复对象——route_policy 携带 backend 字段。**不**断言 `device_route_memory` 的端到端粘性记忆，因为 tasks.py 的粘性门控（`resolved.complete and resolved.fw_compatible and not approval_required`）在无 seed profile 的单测环境里不会通过（dev-1 无真实设备 profile）。backend 字段一旦正确填充，tasks.py:135 在门控通过时自然取到真实值——这是字段存在的逻辑结果，无需在单测里强求端到端。Step 4 的手动证据命令会单独验证端到端行为。

- [ ] **Step 3: ruff 检查**

Run:
```powershell
cd D:\QWEN3.0
python -m ruff check tests/test_route_policy_backend_field.py
```
Expected: `All checks passed!`

- [ ] **Step 4: 运行断点修复证据命令**

Run:
```powershell
cd D:\QEN3.0
set LIMA_DEVICE_TASK_STORE=memory
python -c "from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests; from device_gateway.device_route_memory import get_route_memory, reset_route_memory_for_tests; reset_tasks_for_tests(); reset_route_memory_for_tests(); t=create_task_from_transcript('dev-1','draw cat'); m=get_route_memory('dev-1'); print('backend:', t['route_policy']['backend']); print('preferred:', m.get('preferred_backends'))"
```
Expected: `backend: dashscope_wanx` 和 `preferred: ['dashscope_wanx']`。

- [ ] **Step 5: 提交**

```powershell
cd D:\QEN3.0
git add tests/test_route_policy_backend_field.py
git commit -m "test(route-policy): add backend-field regression tests" -m "Four tests guarding the stage-2 sub-project #5 contract: resolve_device_route_policy includes backend for all capability families; backend matches DEVICE_ROLE_PREFERENCES per role; sticky route memory records the real backend (dashscope_wanx, not 'unknown') for a draw task; control-class backend is the deterministic marker. setup_function resets both task state and route memory for isolation."
```

---

### Task B4: 更新 submodule 指针 + 文档 + 推送

**仓库:** `D:\QEN3.0`

**Files:**
- Modify: `esp32S_XYZ`（submodule 指针）
- Modify: `STATUS.md`, `progress.md`, `findings.md`

- [ ] **Step 1: 确认固件子模块在 Task A2 推送的 commit**

Run:
```powershell
cd D:\QWEN3.0\esp32S_XYZ
git log --oneline -1
git branch --show-current
```
Expected: 当前分支 `fix/route-policy-backend-field`，最新 commit 是 Task A1 的提交，且已在 origin。

- [ ] **Step 2: 回主仓库，更新 submodule 指针**

Run:
```powershell
cd D:\QWEN3.0
git add esp32S_XYZ
git status
```
Expected: 暂存 submodule 指针变更。

- [ ] **Step 3: 更新 findings.md（顶部插入）**

在 `D:\QWEN3.0\findings.md` 顶部（`# Personal Coding Assistant Findings` 之后、第一个 `##` 之前）插入：
```markdown
## 2026-06-15 route_policy backend 字段贯通（阶段 2 子项目 #5）

> 目标：修复 route_policy 缺 backend 字段的断点，使粘性路由记忆记到真实 backend。详见 spec `docs/superpowers/specs/2026-06-15-route-policy-backend-field-design.md`。

| 证据点 | 内容 |
|--------|------|
| 固件改动（esp32S_XYZ） | edge_c/edge_b schema route_policy 加可选 backend 属性；edge_c downlink example 补 backend:"deterministic" |
| 云端改动 | model_routing.py: `_policy()` 加 backend 参数；`resolve_device_route_policy` 复用既有 `get_preferred_backend(route_role)` 填充 backend + 联动 `record_route_evidence`；修正 matrix 测试 4 个 expected；新增 4 个断点修复测试 |
| 断点修复证据 | `create_task_from_transcript('dev-1','draw cat')` 的 `preferred_backends[0]` 从 `"unknown"` 变为 `"dashscope_wanx"` |
| 验证 | 固件 schema 门 62/62；主仓库 model_routing 30 passed + 新测试 4 passed + ruff clean |
| 范围外（YAGNI） | 不统一 MODEL_REGISTRY（子项目 #1）；不给 deterministic 创建真实后端注册；不改 validate_route_policy；不动 edge_b 顶层软约束 |
| 后续 | 子项目 #1（注册表统一）可在此基础上推进 |
```

- [ ] **Step 4: 更新 progress.md（顶部插入 + 日期）**

在 `D:\QWEN3.0\progress.md` 把 `> Updated: 2026-06-15` 保留（已是该日期），在第一个 `## 2026-06-15` 条目之前插入：
```markdown
## 2026-06-15 route_policy backend 字段贯通（阶段 2 子项目 #5）

- 固件先行：edge_c/edge_b schema route_policy 加可选 backend + downlink example 补字段；固件 CI schema 门 62/62。
- 主仓库后行：model_routing `_policy()` 加 backend 参数、`resolve_device_route_policy` 复用 `get_preferred_backend` 填充、`record_route_evidence` 联动；修正 matrix 测试；新增 4 个断点修复测试；更新 submodule 指针。
- 断点修复证据：draw 任务的粘性记忆 `preferred_backends[0]` 从 `"unknown"` 变为 `"dashscope_wanx"`。
- 验证：固件 schema 门 + 主仓库 model_routing 30 passed + 新测试 4 passed + ruff clean。
```

- [ ] **Step 5: 更新 STATUS.md**

在 `D:\QWEN3.0\STATUS.md` 的「最近完成（2026-06-15）」节追加一条：
```markdown
- route_policy backend 字段贯通（阶段 2 子项目 #5）：resolve_device_route_policy 填充 backend，粘性路由记忆记真实 backend（非 unknown）；固件 schema 加可选 backend 字段
```

- [ ] **Step 6: 提交 submodule 指针 + 文档**

```powershell
cd D:\QEN3.0
git add esp32S_XYZ STATUS.md progress.md findings.md
git commit -m "chore: bump esp32S_XYZ submodule + record route_policy backend field closeout" -m "Pulls in the firmware submodule commit that adds the optional backend field to route_policy schemas (edge_c/edge_b) and the downlink example. Records closeout evidence in STATUS/progress/findings." -m "Closes stage 2 sub-project #5. route_policy now carries the selected backend end-to-end; device_route_memory sticky routing records real backends (dashscope_wanx etc.) instead of 'unknown'. Prerequisite for stage 2 sub-project #1 (registry consolidation)."
```

- [ ] **Step 7: 推送主仓库**

Run:
```powershell
cd D:\QEN3.0
git push -u origin design/route-policy-backend-field
```
Expected: 推送成功。

---

## 关闭标准核对

- [ ] 固件：schema/example 改动通过固件 CI 门（62/62）
- [ ] 固件：已 push 到固件 origin（Task A2）
- [ ] 主仓库：`_policy()` 加 backend + `resolve` 填充 + `record_route_evidence` 联动
- [ ] 主仓库：matrix 测试修正 + 4 个新测试通过 + ruff clean
- [ ] 主仓库：model_routing 30 passed + retention/routes 回归通过
- [ ] 主仓库：submodule 指针指向固件已推送的 commit
- [ ] 断点修复证据：`preferred_backends[0] == "dashscope_wanx"`（不再是 unknown）
- [ ] 文档：STATUS/progress/findings 已更新
- [ ] 仅暂存相关文件，conventional commit，已推送 origin

## 回滚

若任一阶段失败：
1. 先 revert 主仓库提交（Task B4、B3、B2），避免 submodule 指针悬空
2. 再 revert 固件子模块提交（Task A1）
3. backend 是新增可选字段，回滚零运行时风险；device_route_memory 是内存态，进程重启即清空
