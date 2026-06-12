# 发布证据：优化路线图阶段 1-5 完成

> 日期: 2026-06-12
> 范围: 设备路由优化路线图全部 5 个阶段
> 状态: 已完成

## 门 A：服务器健康（部署证据）✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| `/health` 返回 200 | ✅ | 公网验证通过 |
| `/device/v1/health` 返回 200 | ✅ | 公网验证通过 |
| 无 critical alerts | ✅ | `/v1/ops/summary` 正常 |
| 路由引擎正常 | ✅ | 46 passed (test_routing_engine.py) |
| 设备网关正常 | ✅ | 109 passed (test_device_gateway_*.py) |

## 门 B：设备协议验证（假 U8/U1）✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 假 U8 hello 握手 | ✅ | `test_fake_u8_hello_heartbeat_transcript_motion_event_loop` |
| 假 U8 heartbeat 响应 | ✅ | 同上 |
| 假 U8 transcript 接受 | ✅ | 同上 |
| 假 U8 motion_event 接收 | ✅ | 同上 |
| 路由策略在 motion_task 中传递 | ✅ | `test_route_policy_matrix_for_hot_device_families` |
| 假 U1 运动执行 | ⬜ | 待假 U1 工具实现 |

## 门 C：任务生命周期验证 ✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 控制任务（home） | ✅ | `test_control_command_uses_no_model_route` |
| 写字任务（write_text） | ✅ | `test_write_text_uses_device_write_route` |
| 绘图任务（draw_generated） | ✅ | `test_generated_drawing_uses_device_draw_route` |
| 矢量任务（SVG 路径） | ✅ | `test_svg_like_generated_drawing_uses_vector_route_without_model` |
| 验证失败任务 | ✅ | `test_validate_route_policy_rejects_unknown_role` |
| 策略阻断任务 | ✅ | `test_policy_blocks_unsafe_task` |
| 断开恢复 | ✅ | WebSocket 重连测试通过 |

## 门 D：路由策略验证 ✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| route_policy 在所有任务路径中保留 | ✅ | 4 个角色路由矩阵测试 |
| 路由策略验证拒绝无效组合 | ✅ | 12 个验证测试 |
| 路由证据记录完整 | ✅ | 证据包含 route_role, policy_decision, sim_risk_score |
| 固件不兼容阻断 | ✅ | `test_fw_incompatible_blocks_task_creation` |

## 门 E：安全验证 ✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 设备安全策略生效 | ✅ | `test_device_gateway_protocol.py` 全部通过 |
| 路径验证拒绝越界坐标 | ✅ | `test_device_gateway_path_validator.py` 全部通过 |
| 工作区边界检查 | ✅ | `test_unknown_device_gets_conservative_profile` |
| 风险评分阻断高风险任务 | ✅ | `test_high_risk_task_requires_approval` |

## 门 F：可观测性验证 ✅

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 路由决策事件记录 | ✅ | `agent_events` 记录存在 |
| 设备账本事件记录 | ✅ | `task_created`, `task_dispatched`, `motion_event`, `task_terminal` |
| 路由证据制品记录 | ✅ | `route_evidence` 制品存在 |
| 简化决策记录 | ✅ | `simplification` 日志存在 |

## 测试结果汇总

```
155 passed (device_gateway_*.py + routing_*.py)
```

## 部署证据

- **VPS 状态**: 健康
- **公网端点**: `https://chat.donglicao.com`
- **设备网关**: `/device/v1/health` 返回 200
- **路由引擎**: `routing_engine.route()` 作为权威入口

## 硬件证据

- **假 U8 测试**: 通过
- **假 U1 测试**: 待实现
- **物理设备测试**: 待执行

## 发布决策

- **部署证据**: ✅ 通过
- **硬件证据**: ⚠️ 部分通过（假 U8 通过，假 U1 待实现）
- **发布建议**: 可发布到测试环境，生产环境需假 U1 验证
