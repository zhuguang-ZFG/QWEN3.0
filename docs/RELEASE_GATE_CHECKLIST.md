# AI 到运动发布门清单

> 日期: 2026-06-12
> 范围: 从用户请求到终端运动事件的端到端发布门
> 状态: Phase 5 实现

## 发布门概述

每个发布必须通过以下检查清单。健康的 VPS 不能证明安全的运动。
部署证据与硬件证据必须分开存储。

## 门 A：服务器健康（部署证据）

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| `/health` 返回 200 | ⬜ | `curl -sf https://chat.donglicao.com/health` |
| `/device/v1/health` 返回 200 | ⬜ | `curl -sf https://chat.donglicao.com/device/v1/health` |
| 无 critical alerts | ⬜ | 检查 `/v1/ops/summary` |
| 路由引擎正常 | ⬜ | `python -m pytest tests/test_routing_engine.py -q` |
| 设备网关正常 | ⬜ | `python -m pytest tests/test_device_gateway_*.py -q` |

## 门 B：设备协议验证（假 U8/U1）

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| 假 U8 hello 握手 | ⬜ | WebSocket 连接 + hello 消息 |
| 假 U8 heartbeat 响应 | ⬜ | 心跳消息返回 ack |
| 假 U8 transcript 接受 | ⬜ | 语音转文字消息处理 |
| 假 U8 motion_event 接收 | ⬜ | 运动事件消息处理 |
| 路由策略在 motion_task 中传递 | ⬜ | 验证 route_policy 字段存在 |
| 假 U1 运动执行 | ⬜ | 运动指令执行 + 结果返回 |

## 门 C：任务生命周期验证

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| 控制任务（home） | ⬜ | `python -m pytest tests/test_device_gateway_model_routing.py::test_control_command_uses_no_model_route -v` |
| 写字任务（write_text） | ⬜ | `python -m pytest tests/test_device_gateway_model_routing.py::test_write_text_uses_device_write_route -v` |
| 绘图任务（draw_generated） | ⬜ | `python -m pytest tests/test_device_gateway_model_routing.py::test_generated_drawing_uses_device_draw_route -v` |
| 矢量任务（SVG 路径） | ⬜ | `python -m pytest tests/test_device_gateway_model_routing.py::test_svg_like_generated_drawing_uses_vector_route_without_model -v` |
| 验证失败任务 | ⬜ | `python -m pytest tests/test_device_gateway_model_routing.py::test_validate_route_policy_rejects_unknown_role -v` |
| 策略阻断任务 | ⬜ | `python -m pytest tests/test_device_gateway_protocol.py::test_policy_blocks_unsafe_task -v` |
| 断开恢复 | ⬜ | WebSocket 断开后重连恢复 |

## 门 D：路由策略验证

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| route_policy 在所有任务路径中保留 | ⬜ | 4 个角色路由矩阵测试 |
| 路由策略验证拒绝无效组合 | ⬜ | 12 个验证测试 |
| 路由证据记录完整 | ⬜ | 证据包含 route_role, policy_decision, sim_risk_score |
| 固件不兼容阻断 | ⬜ | fw_incompatible 错误码返回 |

## 门 E：安全验证

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| 设备安全策略生效 | ⬜ | `python -m pytest tests/test_device_gateway_protocol.py -q` |
| 路径验证拒绝越界坐标 | ⬜ | `python -m pytest tests/test_device_gateway_path_validator.py -q` |
| 工作区边界检查 | ⬜ | `python -m pytest tests/test_device_gateway_profiles.py::test_unknown_device_gets_conservative_profile -v` |
| 风险评分阻断高风险任务 | ⬜ | `python -m pytest tests/test_device_gateway_protocol.py::test_high_risk_task_requires_approval -v` |

## 门 F：可观测性验证

| 检查项 | 状态 | 验证命令 |
|--------|------|---------|
| 路由决策事件记录 | ⬜ | 检查 `agent_events` 记录 |
| 设备账本事件记录 | ⬜ | `task_created`, `task_dispatched`, `motion_event`, `task_terminal` |
| 路由证据制品记录 | ⬜ | `route_evidence` 制品存在 |
| 简化决策记录 | ⬜ | `simplification` 日志存在 |

## 物理设备证据模板

每次物理设备发布必须记录以下信息：

```markdown
## 物理设备发布证据

### 设备信息
- **板版本**: [板版本号]
- **U8 固件版本**: [固件版本]
- **U1 固件版本**: [固件版本]
- **工作区尺寸**: [宽度]mm × [高度]mm
- **材料**: [材料类型]
- **校准状态**: [已校准/未校准]

### 发布内容
- **提示词**: [用户提示词]
- **生成制品哈希**: [SHA-256]
- **路径点数**: [点数]
- **运行时间估计**: [秒]
- **预期笔画数**: [笔画数]

### 验证结果
- **终端结果**: [成功/失败]
- **实际运行时间**: [秒]
- **笔画质量**: [良好/一般/差]
- **操作员笔记**: [备注]

### 发布信息
- **发布日期**: [YYYY-MM-DD]
- **操作员**: [操作员]
- **环境**: [开发/测试/生产]
- **VPS 部署版本**: [commit hash]
```

## 验证命令

```powershell
# 运行所有设备网关测试
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py tests/test_device_gateway_routes.py tests/test_device_gateway_store.py tests/test_device_gateway_path_validator.py tests/test_device_gateway_profiles.py -q

# 运行路由引擎测试
python -m pytest tests/test_routing_engine.py tests/test_routing_pipeline_authority.py -q

# 运行全量 CI 检查
python scripts/run_pre_commit_check.py --full

# 检查服务器健康
curl -sf https://chat.donglicao.com/health
curl -sf https://chat.donglicao.com/device/v1/health
```

## 发布流程

1. **本地验证**: 运行所有测试，确保通过
2. **部署验证**: 部署到 VPS，验证健康检查
3. **设备验证**: 使用假 U8/U1 验证协议和任务生命周期
4. **安全验证**: 验证安全策略和路径验证
5. **可观测性验证**: 验证日志和指标记录
6. **记录证据**: 填写发布门清单，存储到 `docs/release_evidence/`
7. **发布**: 执行发布操作

## 证据存储

- **部署证据**: `STATUS.md`, `progress.md`
- **硬件证据**: `docs/release_evidence/YYYY-MM-DD-*.md`
- **测试证据**: pytest 输出
- **健康证据**: `/health` 和 `/device/v1/health` 响应
