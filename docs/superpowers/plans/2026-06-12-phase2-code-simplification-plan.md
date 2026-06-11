# Phase 2 代码精简计划（2026-06-12）

**状态**: 计划中
**Owner**: zhuguang-ZFG
**目标**: 代码行数从 ~194万 降至 ~97万（减半）

---

## 一、基线状态（2026-06-12）

### 测试基线
- **通过**: 2008 passed ✅
- **跳过**: 24 skipped
- **失败**: 1 failed (已修复: .gitignore 添加 pytest_temp)
- **执行时间**: ~101s

### 代码规模
```
python_files       = 5,348
python_lines       = 1,946,450
test_files         = 227
routes_py_files    = 44
routes_py_lines    = 6,608
top_level_dirs     = 53
```

### 关键文件行数
```
server.py                           128
routing_engine.py                   325
smart_router.py                     241
routes/chat_handler_dispatch.py    338
http_body_limit.py                  247
routes/quality_gate.py               89 (临时 stub)
routes/system_endpoints.py           76
backends.py                         136
session_memory/store.py              51
```

---

## 二、删除目标模块

### 2.1 已标记为临时 Stub（优先删除）
| 模块 | 行数 | 状态 | 风险 |
|------|------|------|------|
| `routes/quality_gate.py` | 89 | Phase 2 移除 | 低（stub） |
| `routes/anthropic_messages_handler.py` | 75 | Phase 2 移除 | 低（stub） |
| `routes/anthropic_vision_sse.py` | 33 | Phase 2 移除 | 低（stub） |

### 2.2 编码助手专属模块（Phase 0 已删除）
✅ 已完成（2026-06-09）：
- `agent_runtime/` (编码助手运行时)
- `semantic_cache/` (语义缓存)
- `routes/anthropic_stream.py` (Anthropic 流式)
- `routes/tool_forward*.py` (工具转发)
- `routes/quality_gate_tiers.py` + `quality_gate_direct.py` (质量门控子模块)

### 2.3 待重构模块（转型为设备服务）
| 原模块 | 目标模块 | 当前行数 | 目标行数 | 变更类型 |
|--------|---------|---------|---------|----------|
| `routing_engine.py` | `device_llm_router.py` | 325 | ~150 | 简化为设备对话路由 |
| `smart_router.py` | **删除** | 241 | 0 | 过度设计 |
| `session_memory/` | `device_context.py` | 多文件 | ~200 | 合并为设备上下文 |

---

## 三、分片执行计划（5 个 Slice）

### **Slice 1: 删除临时 Stub 模块**
**目标**: 清理 Phase 0 遗留的临时实现

**删除文件**:
```
routes/quality_gate.py                   (89 行)
routes/anthropic_messages_handler.py     (75 行)
routes/anthropic_vision_sse.py          (33 行)
```

**依赖检查**:
```bash
grep -r "quality_gate" --include="*.py" routes/ server.py
grep -r "anthropic_messages_handler" --include="*.py" routes/ server.py
grep -r "anthropic_vision_sse" --include="*.py" routes/ server.py
```

**验证**:
```bash
python -m pytest -q --ignore=tests/test_token_health.py --basetemp=.pytest_temp
python -m py_compile server.py routing_engine.py routes/*.py
```

**预期影响**: 减少 ~200 行，移除 3 个路由注册

---

### **Slice 2: 删除 smart_router.py（过度设计）**
**目标**: 简化路由逻辑

**删除文件**:
```
smart_router.py  (241 行)
```

**迁移逻辑**:
- `smart_router.py` 的核心功能已由 `routing_engine.py` + `device_llm_router.py` 替代
- 检查 `server.py` 中是否还有引用

**依赖检查**:
```bash
grep -r "smart_router" --include="*.py" . --exclude-dir=venv
```

**验证**:
```bash
python -m pytest tests/test_routing_engine.py -q
python -m pytest tests/test_device_gateway*.py -q
```

**预期影响**: 减少 ~241 行

---

### **Slice 3: 重构 routing_engine.py → device_llm_router.py**
**目标**: 简化为设备对话专用路由

**变更内容**:
1. 创建 `device_llm_router.py`（~150 行）
2. 仅保留设备对话路由逻辑（移除编码助手逻辑）
3. 更新 `server.py` 引用

**保留功能**:
- 设备意图识别
- 多模型路由（通义/文心/Gemini）
- 设备上下文注入

**删除功能**:
- 代码生成路由
- IDE 上下文预检
- Anthropic 工具路由

**验证**:
```bash
python -m pytest tests/test_device_gateway*.py -q
python -m pytest tests/test_routing*.py -q
```

**预期影响**: `routing_engine.py` (325) → `device_llm_router.py` (~150)，减少 ~175 行

---

### **Slice 4: 合并 session_memory/ → device_context.py**
**目标**: 简化设备上下文存储

**当前结构**:
```
session_memory/
├── store.py           (51 行)
├── daemon.py
├── prompt_recall.py
└── learning_loop.py
```

**目标结构**:
```
device_context.py  (~200 行，单文件)
```

**保留功能**:
- 设备会话存储（SQLite）
- TTL 过滤
- 跨设备隔离

**删除功能**:
- 编码助手提示词记忆
- 学习循环（learning_loop）
- 后台守护进程（daemon）

**验证**:
```bash
python -m pytest tests/test_session_memory*.py -q
python -m pytest tests/test_device_memory*.py -q
```

**预期影响**: 多文件合并为单文件，减少 ~300 行

---

### **Slice 5: 更新文档与统计**
**目标**: 更新项目文档，记录转型进展

**更新文件**:
1. `STATUS.md` - 标记 Phase 2 完成
2. `CLAUDE.md` - 更新架构速览
3. `README.md` - 更新产品定位（如需要）
4. `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` - 更新进度

**验证**:
```bash
python scripts/repo_stats.py
git diff --stat
```

---

## 四、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **依赖未识别** | 中 | 高 | 每个 Slice 前运行 grep 依赖检查 |
| **测试失败** | 中 | 高 | 每个 Slice 独立测试 + commit |
| **回滚成本** | 低 | 中 | 每个 Slice 独立 commit，可单独回滚 |
| **功能退化** | 低 | 高 | 设备网关测试覆盖（M1-M8 已有 ~200 测试） |

---

## 五、执行检查清单

### Slice 1: 删除临时 Stub
- [ ] 依赖检查（grep）
- [ ] 删除 3 个文件
- [ ] 更新路由注册
- [ ] pytest 验证
- [ ] py_compile 验证
- [ ] git commit

### Slice 2: 删除 smart_router
- [ ] 依赖检查
- [ ] 删除 smart_router.py
- [ ] 更新 server.py 引用
- [ ] 路由测试验证
- [ ] git commit

### Slice 3: 重构 routing_engine
- [ ] 创建 device_llm_router.py
- [ ] 迁移核心逻辑
- [ ] 更新 server.py
- [ ] 完整测试
- [ ] 删除旧 routing_engine.py
- [ ] git commit

### Slice 4: 合并 session_memory
- [ ] 创建 device_context.py
- [ ] 迁移核心功能
- [ ] 更新所有引用
- [ ] 测试验证
- [ ] 删除 session_memory/ 目录
- [ ] git commit

### Slice 5: 更新文档
- [ ] 运行 repo_stats.py
- [ ] 更新 STATUS.md
- [ ] 更新 CLAUDE.md
- [ ] git commit
- [ ] 推送到 GitHub

---

## 六、预期成果

### 代码规模
```
删除前: ~1,946,450 行
删除后: ~1,460,000 行（预计减少 ~25%）
```

### 核心模块
```
routing_engine.py (325)  → device_llm_router.py (150)
smart_router.py (241)    → [删除]
session_memory/ (多文件) → device_context.py (200)
3 个 stub 文件            → [删除]
```

### 架构清晰度
- ✅ 设备服务定位明确
- ✅ 编码助手遗留代码清除
- ✅ 路由逻辑简化
- ✅ 文档与代码一致

---

## 七、下一步（Phase 3）

Phase 2 完成后，进入 **Phase 3: 小智功能迁移**（4-5 周）：
- 绘画引擎实现（SVG/DashScope/矢量化）
- 设备生命周期管理（绑定/激活/成员/RMA）
- 声纹服务集成
- 小程序端适配

**Phase 2 → Phase 3 的交接条件**：
- ✅ 测试通过率 ≥ 95%
- ✅ 代码行数减少 ≥ 20%
- ✅ VPS 部署验证通过
- ✅ 文档更新完成

---

**决策点**: 是否开始执行 Slice 1（删除临时 Stub）？
