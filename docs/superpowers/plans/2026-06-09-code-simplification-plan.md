# LiMa 代码精简计划（战略转型）

**日期**: 2026-06-09
**状态**: 执行中
**优先级**: P0 - 战略转型关键步骤
**Owner**: zhuguang-ZFG

---

## 一、背景

根据 [`2026-06-09-lima-strategic-pivot-to-smart-devices.md`](./2026-06-09-lima-strategic-pivot-to-smart-devices.md)，LiMa 从"个人编码助手后端" → "AI 智能设备统一云端服务"。

**目标**：代码量从 ~110K 行减少到 ~55K 行（减半）。

---

## 二、当前代码统计

| 指标 | 值 |
|------|-----|
| Python 文件 | 5,119 |
| Python 总行数 | ~1,929,038 |
| Routes 文件 | 48 |
| Routes 行数 | 7,214 |
| 测试文件（tests/） | 212 |

---

## 三、待删除模块清单

### 3.1 编码助手专属路由（8 文件，~747 行）

| 文件 | 行数 | 大小(KB) | 说明 |
|------|-----:|--------:|------|
| `routes/anthropic_messages_handler.py` | 47 | 1.5 | Anthropic 消息处理 |
| `routes/anthropic_stream.py` | 32 | 1.3 | Anthropic 流式 |
| `routes/anthropic_vision_sse.py` | 14 | 0.6 | Anthropic 视觉 SSE |
| `routes/tool_forward.py` | 86 | 3.2 | 工具转发 |
| `routes/tool_forward_stream.py` | 332 | 13.4 | 工具流式转发 |
| `routes/quality_gate.py` | 88 | 2.8 | 编码质量门控 |
| `routes/quality_gate_direct.py` | 69 | 2.0 | 质量门控直接调用 |
| `routes/quality_gate_tiers.py` | 79 | 2.1 | 质量门控分层 |
| **总计** | **747** | **26.9** | |

### 3.2 语义缓存（1 文件，154 行）

- `semantic_cache.py` (154 行) — 设备场景不需要

### 3.3 Agent 编排（已不存在）

- `agent_runtime/` 目录 — 已在之前删除

### 3.4 相关测试文件（13 文件，~1,698 行）

| 文件 | 行数 | 说明 |
|------|-----:|------|
| `tests/test_lima_code_dev_search_tools.py` | 320 | LiMa Code 开发搜索 |
| `tests/test_tool_gateway.py` | 277 | 工具网关 |
| `tests/test_tool_gateway_adapter.py` | 194 | 工具网关适配器 |
| `tests/test_local_tool_modules.py` | 158 | 本地工具模块 |
| `tests/test_channel_tools.py` | 124 | 频道工具 |
| `tests/test_anthropic_preflight.py` | 110 | Anthropic 预检 |
| `tests/test_anthropic_tool_protocol.py` | 93 | Anthropic 工具协议 |
| `tests/test_tool_forward.py` | 86 | 工具转发 |
| `tests/test_gitee_tools.py` | 86 | Gitee 工具 |
| `tests/test_mcp_tools.py` | 84 | MCP 工具 |
| `tests/test_admin_agent_audit.py` | 73 | Agent 审计 |
| `tests/test_tool_forward_failures.py` | 60 | 工具转发失败 |
| `tests/test_anthropic_format_tools.py` | 33 | Anthropic 格式工具 |
| **总计** | **~1,698** | |

---

## 四、执行计划

### Phase 1：备份与准备（30 分钟）

- [x] 创建任务追踪
- [ ] 生成当前代码统计报告
- [ ] 创建 Git 分支 `feat/code-simplification`
- [ ] 备份当前状态到 `/opt/lima-router/backups/pre-simplification-20260609/`

### Phase 2：删除路由文件（1 小时）

- [ ] 删除 8 个编码助手路由文件
- [ ] 检查 `routes/__init__.py` 是否有引用
- [ ] 检查 `server.py` 路由注册
- [ ] 运行 `py_compile` 验证

### Phase 3：删除语义缓存（30 分钟）

- [ ] 删除 `semantic_cache.py`
- [ ] 检查其他模块是否引用
- [ ] 删除 `data/semantic_cache.db`
- [ ] 更新 `requirements_server.txt`

### Phase 4：删除测试文件（30 分钟）

- [ ] 删除 13 个相关测试文件
- [ ] 运行精简后的测试套件
- [ ] 记录通过/失败数量

### Phase 5：清理引用（1 小时）

- [ ] 搜索并清理所有 import 引用
- [ ] 检查 `routing_engine.py` 是否调用已删除模块
- [ ] 检查 `server.py` 是否注册已删除路由
- [ ] 运行 `ruff check` 和 `pyright`

### Phase 6：文档更新（30 分钟）

- [ ] 更新 `STATUS.md` 记录精简结果
- [ ] 更新 `task_plan.md` 移除编码助手任务
- [ ] 更新 `docs/LIMA_MEMORY.md` 移除编码助手记忆
- [ ] 生成精简后代码统计

### Phase 7：验证与部署（1 小时）

- [ ] 本地运行 pytest（目标通过率 >90%）
- [ ] 本地启动 `server.py` 验证健康检查
- [ ] 提交到 Git
- [ ] 部署到 VPS（可选，等待 Phase 0 完成后）

---

## 五、预期效果

| 指标 | 删除前 | 删除后（预估） | 减少量 |
|------|-------:|-------------:|-------:|
| Routes 文件 | 48 | 40 | -8 |
| Routes 行数 | 7,214 | 6,467 | -747 |
| 核心模块行数 | 154 | 0 | -154 |
| 测试文件 | 212 | 199 | -13 |
| 测试行数 | ~20,000+ | ~18,302 | -1,698 |
| **总计减少** | | | **~2,599 行** |

**注意**：当前统计显示 Python 总行数为 ~1.9M，远超预期的 110K。需要重新评估统计范围（可能包含了 venv、esp32、deepcode-cli 等子模块）。

---

## 六、风险与缓解

| 风险 | 严重度 | 缓解措施 |
|-----|--------|---------|
| 删除后破坏现有功能 | 🟡 中 | 1. 精简前备份；2. 分步验证；3. 保留回滚路径 |
| 其他模块仍依赖已删除代码 | 🟡 中 | 全局搜索 import，逐一清理引用 |
| 测试套件大量失败 | 🟢 低 | 删除的都是编码助手专属测试，核心测试应不受影响 |
| VPS 部署失败 | 🟡 中 | 本地充分验证后再部署；保留 VPS 备份 |

---

## 七、下一步

1. **立即执行**：Phase 1-6（本地精简）
2. **待 Phase 0 完成后**：Phase 7 VPS 部署
3. **后续工作**：
   - 简化 `routing_engine.py` 为设备对话路由
   - 简化 `session_memory/` 为设备上下文
   - 实现新增的 `xiaozhi_drawing/` 和 `xiaozhi_device/` 模块

---

## 八、参考文档

- [战略转型计划](./2026-06-09-lima-strategic-pivot-to-smart-devices.md)
- [Phase 0 启动文档](./2026-06-09-phase0-strategic-confirmation.md)
- [代码质量改进计划](../../CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md)
