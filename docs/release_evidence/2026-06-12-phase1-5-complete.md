# AI → Motion 阶段 1-5 发布证据

> 本文件为 `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md` 在阶段 1-5 的
> 实例化产物，也是 `tests/device_gateway_profile/test_device_gateway_profile_release_gates.py`
> 断言其存在的发布证据。后续切片请复制新日期文件并刷新下表。
>
> 权威清单：[`../RELEASE_GATE_CHECKLIST.md`](../RELEASE_GATE_CHECKLIST.md)
> 准入报告：[`../model_admission/2026-06-12-device-drawing-writing.md`](../model_admission/2026-06-12-device-drawing-writing.md)

## 元数据

| 字段 | 值 |
|------|-----|
| 发布日期 | 2026-06-12 |
| 切片 / 里程碑 | 阶段 1-5 — AI → Motion 全链路打通 |
| 操作员 / Agent | lima-agent |
| 环境 | `local` + `staging`（生产真机证据见下方物理设备节） |

## 变更摘要

- **用户可见行为**：语音/文字「画 X」「写 Y」→ 生成路径 → 设备执行。
- **触及模块**：`device_gateway/`（intent、draw、write、path_pipeline）、`dlc_api/`、`xiaozhi_drawing/`。
- **非目标**：未改 U1/U8 固件运动栈、未改聊天热路径。

---

## 门 A：服务器健康（部署证据）

| 检查项 | 证据 |
|--------|------|
| `GET /health` → 200 | 本地 + staging 验证通过 |
| 设备网关聚焦门 | 见下方「测试结果汇总」 |

---

## 门 B：设备协议（假 U8 / 假 U1）

| 检查项 | 证据 |
|--------|------|
| 假 U8 hello 握手 | `test_fake_u8_hello_heartbeat_transcript_motion_event_loop` |
| transcript → 任务创建 | `task_created` 事件 |
| motion_event 上行 | `motion_event_ack` + phase 序列 |

---

## 门 C：任务生命周期

| capability | route_role | pytest |
|------------|-----------|--------|
| `write_text` | `device_write` | `test_write_text_uses_device_write_route` |
| `draw_generated` | `device_draw` | `test_generated_drawing_uses_device_draw_route` |
| SVG / `run_path` | `device_vector` | `test_svg_like_generated_drawing_uses_vector_route_without_model` |

---

## 门 D：路由策略与 Profile

| 检查项 | 证据 |
|--------|------|
| `route_policy` 全路径保留 | `test_route_policy_matrix_for_hot_device_families` |
| 无效组合被拒绝 | route_policy 验证套件 |
| `backend` 与 `model_routing` 一致 | `test_route_policy_backend_field.py` |

---

## 门 E：安全与几何

| 检查项 | 证据 |
|--------|------|
| 路径越界拒绝 | `tests/test_device_gateway_path_validator.py` |
| 点数上限 | `device_gateway/safety.py` `MAX_PATH_POINTS` |
| 无静默降级 | AGENTS.md #0；相关路径 `logger.warning` |

---

## 门 F：可观测性

| 检查项 | 证据 |
|--------|------|
| 设备账本事件 | `task_created`, `task_dispatched`, `motion_event`, `task_terminal` |
| `route_evidence` 可查询 | `GET /device/v1/devices/{id}/history?artifact_type=route_evidence` |

---

## 测试结果汇总

```powershell
python -m pytest tests/test_device_gateway_model_routing.py -q
python -m pytest tests/test_device_gateway_path_pipeline.py -q
python -m pytest tests/test_device_gateway_protocol.py tests/test_device_gateway_path_validator.py -q
```

阶段 1-5 聚焦门结果：全部通过（详见各次 CI run 的 `test` job 摘要）。

---

## 发布决策

| 维度 | 结论 |
|------|------|
| 门 A 部署 | ✅ 通过 |
| 门 B–F 自动化 | ✅ 通过 |
| 物理设备 | ⬜ 生产发布前补真机证据 |
| **总体建议** | 仅测试环境 / 待真机证据后生产可发布 |

**回滚方案**：回退到上一个通过的 git tag；密钥/配置不动。
