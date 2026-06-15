# esp32s_adapter route_policy 语义统一

**日期**: 2026-06-15
**状态**: 已关闭
**父计划**: [`2026-06-15-code-quality-governance-plan.md`](../plans/2026-06-15-code-quality-governance-plan.md) Q1

## 问题

`esp32s_adapter/protocol.py` 内联 `generate_route_policy()` 将 `run_path` 映射为 `device_write`，与权威源 `device_gateway.model_routing.resolve_device_route_policy()`（`device_vector`）不一致。

## 决策

1. **权威源**：`device_gateway.model_routing.resolve_device_route_policy`
2. **适配层**：`esp32s_adapter.protocol.generate_route_policy(capability)` 仅构造 `{"capability": capability}` 并委托 resolve；不传 `device_id`，避免副作用性 route evidence
3. **删除**：本地 `CONTROL_CAPABILITIES` 副本
4. **测试**：`run_path` 期望 `route_role == "device_vector"`

## 范围外

- 不修改 `esp32S_XYZ` 固件（已在 a4cab61 对齐）
- 不统一 `MODEL_REGISTRY`（路线图阶段 2）

## 验证

```powershell
python -m pytest tests/test_esp32s_adapter_protocol.py tests/test_device_gateway_model_routing.py -q
```
