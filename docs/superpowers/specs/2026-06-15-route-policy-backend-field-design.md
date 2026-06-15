# route_policy backend 字段贯通设计

> 日期: 2026-06-15
> 范围: 阶段 2 子项目 #5——修复 route_policy 缺 backend 字段的断点
> 关联路线图: `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` 阶段 2 + 阶段 3
> 策略: route_policy 携带单 backend 字符串，向后兼容（schema 可选）

## 背景与动机

`route_policy` 是设备任务的路由证据对象。当前它只描述"要什么类型的路由"（route_role/strategy），**不描述"选了哪个后端"（backend）**。这导致一条断点链：

1. `_policy()`（`device_gateway/model_routing.py:281`）生成的 route_policy 只有 4 字段（route_role/model_required/primary_strategy/artifact_required），**无 backend**
2. `tasks.py:135` `backend = route_policy.get("backend", "unknown")` → 永远取到 `"unknown"`
3. `record_route_decision(device_id, "unknown", True)` → 粘性记忆 `device_route_memory` 的 `preferred_backends` 永远是 `["unknown"]`，**功能存在但失效**
4. `record_route_evidence`（`artifact_recorder.py:33`）有独立 `backend` 参数，但 `resolve_device_route_policy`（model_routing.py:149）调用时没传，JSONL 日志的 backend 字段一直空

关键发现：`get_preferred_backend(route_role)`（model_routing.py:112）**已存在且能选 backend**（返回 `DEVICE_ROLE_PREFERENCES[role][0]`），但 `resolve_device_route_policy` 从不调用它——这是缺失的环节。

本子项目让 route_policy 携带本次任务选中的 backend，使粘性路由记忆生效、下游审计完整，并为后续子项目 #1（注册表统一）铺路。

## 设计决策

### 决策 1：单字符串 backend（非候选列表）

route_policy 的 backend 字段是**单个字符串**（本次选中的那一个），不是候选列表。

- 符合 route_policy"本次路由决策证据"的语义
- 候选列表由既有的 `get_route_role_alternatives(route_role)` 单独提供（fallback 用），职责分离
- 改动最小，为 #1 留好接口

### 决策 2：复用 get_preferred_backend（不新写选择逻辑）

`resolve_device_route_policy` 确定 route_role 后，调用既有 `get_preferred_backend(route_role)` 取首选 backend，写入 policy。该函数已存在（model_routing.py:112），只是从没被生产代码调用。

### 决策 3：backend 字段在 schema 可选（向后兼容）

route_policy.backend **不加入 schema required**。既有不带 backend 的帧仍合法；`_policy()` 的 backend 默认空串，既有直接构造 `_policy(...)` 的代码不崩。

### 决策 4：backend 值分两类——真实后端 vs 本地标记

`DEVICE_ROLE_PREFERENCES` 里的 backend 值分两类：
- **真实后端**：`dashscope_wanx`/`dashscope_flux`（在 `backends_registry.py:242-243` 注册，有真实阿里云 API URL/key，`admission: device_draw_candidate`）
- **本地标记**：`deterministic`（本地解析器，无 LLM/API）、`opencv_contour`（本地 OpenCV 轮廓检测，无 API）

粘性记忆记这两类都**有效**——`dashscope_wanx` 意味着"该设备偏好阿里云图生"，`deterministic` 意味着"偏好本地确定性路径"。下游消费时需区分两类（真实后端可做健康检查/预算管理，本地标记不会失败也不消耗预算）。spec 记录此不变量。

> 注：`dashscope_wanx` 在 `backends_registry.py:242` 注册为真实后端，但通过 `from backends_registry import BACKENDS` 查询 `'dashscope_wanx' in BACKENDS` 返回 False 的现象待查（可能 env/动态组装机制），不影响本设计——backend 字段只携带值，不校验是否在 BACKENDS。

## 改动清单

### 固件子模块仓库（esp32S_XYZ）——先行

| 文件 | 改动 |
|------|------|
| `docs/schemas/edge_c/motion_task.schema.json` | route_policy.properties 加可选 `backend`（type:string, minLength:0），**不加入 required**。`additionalProperties:false` 要求显式声明 |
| `docs/schemas/edge_b/motion_task.schema.json` | 同步加可选 `backend`（保持双端 route_policy 子结构一致，edge_b 顶层仍软约束） |
| `docs/schemas/edge_c/examples/motion_task.downlink.json` | home 控制类 route_policy 补 `"backend": "deterministic"` |

### 主仓库（QWEN3.0）——后行

| 文件 | 改动 |
|------|------|
| `device_gateway/model_routing.py` | `_policy()` 加 `backend: str = ""` 参数；`resolve_device_route_policy` 在确定 route_role 后调 `get_preferred_backend(policy["route_role"])` 填充 `policy["backend"]`；`record_route_evidence` 调用处补 `backend=policy["backend"]` |
| `tests/test_device_gateway_model_routing.py` | `test_route_policy_matrix_for_hot_device_families` 的 4 个 expected dict 各补 backend 字段（home→deterministic, write_text→deterministic, draw_generated 画猫→dashscope_wanx, draw_generated SVG→opencv_contour） |
| `tests/test_route_policy_backend_field.py`（新增） | 4 个测试：resolve 含 backend / backend 匹配 DEVICE_ROLE_PREFERENCES / **粘性记忆记真实 backend**（preferred_backends[0]==dashscope_wanx，不再是 unknown）/ 控制类 backend 是 deterministic 标记 |
| `esp32S_XYZ`（submodule 指针） | 更新指向固件新 commit |
| `STATUS.md` / `progress.md` / `findings.md` | 记录关闭证据 |

## 各角色 backend 取值（来自 DEVICE_ROLE_PREFERENCES model_routing.py:87-104）

| route_role | capability 触发 | backend | 类型 |
|------------|----------------|---------|------|
| device_control | home/pause/resume/stop/estop/get_device_info | `deterministic` | 确定性标记 |
| device_write | write_text | `deterministic` | 确定性标记 |
| device_draw | draw_generated（非 SVG prompt） | `dashscope_wanx` | 真实后端 |
| device_vector | run_path / draw_generated（SVG prompt） | `opencv_contour` | 确定性标记（本地 OpenCV） |
| device_unknown | 其他 | `deterministic` | 确定性标记 |

## 既有测试影响评估

| 测试 | 影响 |
|------|------|
| `test_route_policy_matrix_for_hot_device_families`（精确相等 `== expected`） | ❌ 必失败 → 修正 expected 补 backend |
| 其余 29 个 model_routing 测试（单字段断言 / 手构 policy 调 validator） | ✅ 不受影响 |

`validate_route_policy`（path_validator.py:116）只校验特定字段，不拒绝额外字段（无 additionalProperties 检查），带 backend 的 policy 原样通过。

## 验证命令

**固件子模块（先行）**：
```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m pytest tests/ci/test_validate_schemas.py tests/ci/test_docs_m0_m1_closeout.py -p no:cacheprovider -q
```

**主仓库（后行）**：
```powershell
cd D:\QWEN3.0
set LIMA_DEVICE_TASK_STORE=memory
python -m pytest tests/test_route_policy_backend_field.py tests/test_device_gateway_model_routing.py tests/test_device_gateway_route_policy_retention.py tests/test_device_gateway_routes.py -p no:cacheprovider -q
python -m ruff check device_gateway/model_routing.py tests/test_route_policy_backend_field.py tests/test_device_gateway_model_routing.py
```

**断点修复证据**：
```powershell
set LIMA_DEVICE_TASK_STORE=memory
python -c "from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests; from device_gateway.device_route_memory import get_route_memory, reset_route_memory_for_tests; reset_tasks_for_tests(); reset_route_memory_for_tests(); t=create_task_from_transcript('dev-1','draw cat'); m=get_route_memory('dev-1'); print('backend:', t['route_policy']['backend']); print('preferred:', m.get('preferred_backends'))"
```
预期：`backend: dashscope_wanx` / `preferred: ['dashscope_wanx']`（不再是 unknown）。

## 跨仓库提交顺序

```
步骤1（先行）: 固件子模块 esp32S_XYZ
  - edge_c/edge_b schema route_policy 加可选 backend
  - edge_c downlink example 补 backend
  - 固件 CI schema 门通过 → commit + push 固件 origin

步骤2（后行）: 主仓库 QWEN3.0
  - 更新 esp32S_XYZ submodule 指针
  - model_routing.py: _policy() 加 backend + resolve 填充 + record_route_evidence 联动
  - 修正 matrix 测试 + 新增 backend_field 测试
  - ruff + pytest 通过 → commit + push 主仓库 origin
```

固件必须先 push，主仓库才能安全更新 submodule 指针。

## 回滚策略

- **风险等级：低**。backend 是新增可选字段，不改变既有字段语义。下游对 backend 缺失已有 `"unknown"` 兜底，回滚后回到原状态，无破坏性。
- **回滚顺序**：先 revert 主仓库（步骤2），再 revert 固件（步骤1），避免 submodule 指针悬空。
- **粘性记忆无持久化**：`device_route_memory` 是内存态，回滚后进程重启即清空，无遗留脏数据。

## 明确不做的事（YAGNI）

- ❌ 不统一 MODEL_REGISTRY 与 DEVICE_ROLE_PREFERENCES（子项目 #1）
- ❌ 不给 deterministic 创建真实后端注册（确定性标记是语义标记，非后端 ID）
- ❌ 不改 validate_route_policy 增加 backend 校验（backend 是描述字段非约束字段）
- ❌ 不评估 defer 角色（子项目 #3）
- ❌ 不做 AI 图生真实评测（子项目 #2）
- ❌ 不动 edge_b 顶层软约束（只同步 route_policy 子结构）

## 关闭标准

1. 固件 schema/example 改动通过固件 CI 门，已 push
2. 主仓库：route_policy 含 backend + 粘性记忆记真实 backend + matrix 测试修正 + 新测试通过 + ruff clean
3. 跨仓库：固件先 push，主仓库后更新 submodule 指针并 push
4. 断点修复证据：`preferred_backends[0] == "dashscope_wanx"`（不再是 unknown）
5. 文档：STATUS/progress/findings 记录关闭证据
6. 仅暂存相关文件，conventional commit，推送到 origin
