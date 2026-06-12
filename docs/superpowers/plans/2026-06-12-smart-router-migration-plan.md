# smart_router.py 迁移计划

**日期**: 2026-06-12
**状态**: 计划中
**优先级**: P1 - 技术债务治理
**预计周期**: 3-5 天

---

## 一、背景

### 1.1 为什么要迁移

**问题**:
- `smart_router.py` 是遗留兼容层（legacy facade），包含 241 行代码
- 核心功能已经拆分到专门模块，但仍有 23+ 个文件依赖它
- 维护两套接口增加了理解成本和维护负担

**收益**:
- 减少代码冗余（~241 行）
- 统一导入路径，降低认知负担
- 清晰的模块职责边界

### 1.2 为什么要谨慎

**风险**:
- 涉及 **23 个文件**、**60+ 处引用**
- 包括生产路由、管理后台、测试代码
- 错误迁移可能导致路由失败或功能降级

**策略**:
- **分阶段执行**（5 个子 Slice）
- **每个 Slice 独立测试和提交**
- **保持功能等价**（不改变行为）

---

## 二、完整依赖分析

### 2.1 按符号统计（前20）

| 符号 | 引用数 | 迁移目标模块 | 难度 |
|------|--------|-------------|------|
| `BACKENDS` | 18 | `backends.BACKENDS` | 简单 |
| `analyze` | 5 | `router_classifier.analyze` | 简单 |
| `call_api` | 4 | `http_caller.call_api` | 中等 |
| `route` | 3 | `routing_engine.route` | 简单 |
| `detect_image_intent` | 3 | `router_image.detect_image_intent` | 简单 |
| `cb_status` | 3 | `router_circuit_breaker.cb_status` | 简单 |
| `call_local` | 2 | **删除**（本地模型已弃用） | 中等 |
| `DEBUG` | 2 | `os.environ.get("LIMA_DEBUG")` | 简单 |
| `DISTILL_QUEUE_DIR` | 2 | `distill_scheduler.DISTILL_QUEUE_DIR` | 简单 |
| `VISION_BACKENDS` | 2 | `backends.VISION_BACKENDS` | 简单 |
| `_has_vision_content` | 2 | `vision_handler.detect_vision_request` | 简单 |
| `warmup_router_model` | 1 | **删除**（本地模型已弃用） | 简单 |
| `detect_thinking_intent` | 1 | `router_intent.detect_thinking_intent` | 简单 |
| `get_thinking_backend` | 1 | `router_intent.get_thinking_backend` | 简单 |
| `cb_allow` | 1 | `router_circuit_breaker.cb_allow` | 简单 |
| `_log_to_distill_queue` | 1 | `distill_scheduler.log_to_distill_queue` | 中等 |

### 2.2 按文件统计（前10）

| 文件 | 符号数 | 类型 | 迁移优先级 |
|------|--------|------|-----------|
| `routes/chat_support.py` | 7 | 生产 | P0 |
| `auto_retrain.py` | 5 | 工具 | P2 |
| `orchestrate.py` | 4 | 生产 | P0 |
| `routes/system_endpoints.py` | 4 | 生产 | P0 |
| `routes/chat_handler_dispatch.py` | 3 | 生产 | P0 |
| `routes/admin_api.py` | 2 | 管理 | P1 |
| `tests/test_backend_registry.py` | 2 | 测试 | P2 |
| `tests/test_vision_routing.py` | 2 | 测试 | P2 |
| `server.py` | 1 | 启动 | P0 |
| `routes/admin_backends.py` | 1 | 管理 | P1 |

---

## 三、迁移映射表

### 3.1 简单替换（直接映射）

| 旧接口 | 新接口 | 说明 |
|--------|--------|------|
| `smart_router.BACKENDS` | `backends.BACKENDS` | 后端配置字典 |
| `smart_router.VISION_BACKENDS` | `backends.VISION_BACKENDS` | 视觉模型列表 |
| `smart_router.GFW_BACKENDS` | `backends.GFW_BACKENDS` | GFW 后端列表 |
| `smart_router.THINKING_BACKENDS` | `backends.THINKING_BACKENDS` | 思维链后端 |
| `smart_router.analyze` | `router_classifier.analyze` | 意图分析 |
| `smart_router.route` | `routing_engine.route` | 路由入口 |
| `smart_router.detect_image_intent` | `router_image.detect_image_intent` | 图片意图检测 |
| `smart_router.detect_thinking_intent` | `router_intent.detect_thinking_intent` | 思维链检测 |
| `smart_router.get_thinking_backend` | `router_intent.get_thinking_backend` | 思维链后端选择 |
| `smart_router.cb_status` | `router_circuit_breaker.cb_status` | 熔断器状态 |
| `smart_router.cb_allow` | `router_circuit_breaker.cb_allow` | 熔断器检查 |
| `smart_router._has_vision_content` | `vision_handler.detect_vision_request` | 视觉内容检测 |

### 3.2 需要适配（参数变化）

| 旧接口 | 新接口 | 变化 |
|--------|--------|------|
| `smart_router.call_api` | `http_caller.call_api` | 参数顺序可能不同 |
| `smart_router._log_to_distill_queue` | `distill_scheduler.log_to_distill_queue` | 可能需要适配参数 |

### 3.3 需要删除（已弃用功能）

| 旧接口 | 处理方式 | 说明 |
|--------|---------|------|
| `smart_router.call_local` | **删除调用**，改为远程 API | 本地模型加载已弃用 |
| `smart_router.warmup_router_model` | **删除调用** | 本地模型预热已弃用 |
| `smart_router._local_model*` | **删除引用** | 本地模型状态已弃用 |
| `smart_router.LOCAL_ROUTER_MODEL` | **删除引用** | 本地模型路径已弃用 |

### 3.4 环境变量替换

| 旧接口 | 新接口 |
|--------|--------|
| `smart_router.DEBUG` | `os.environ.get("LIMA_DEBUG", "") == "1"` |
| `smart_router.PUBLIC_MODEL_NAME` | `os.environ.get("PUBLIC_MODEL_NAME", "LiMa")` |
| `smart_router.DISTILL_QUEUE_DIR` | `distill_scheduler.DISTILL_QUEUE_DIR` |

---

## 四、分阶段执行计划（5 个 Slice）

### Slice 1: 后端配置迁移（18 处 BACKENDS）

**范围**: 将所有 `smart_router.BACKENDS` 替换为 `backends.BACKENDS`

**影响文件**:
- `routes/admin_api.py`
- `routes/admin_api_extra.py` (4 处)
- `routes/admin_backends.py`
- `routes/system_endpoints.py`
- `routes/chat_support.py`
- `orchestrate.py`
- `tests/test_backend_registry.py`
- 其他 10+ 文件

**执行步骤**:
1. 批量替换：`import smart_router` → `import backends`
2. 批量替换：`smart_router.BACKENDS` → `backends.BACKENDS`
3. 同时处理 `VISION_BACKENDS`、`GFW_BACKENDS`、`THINKING_BACKENDS`
4. 运行测试：`pytest tests/test_backend*.py tests/test_admin*.py -q`
5. Git commit

**验证命令**:
```bash
python -m pytest tests/test_backend_registry.py tests/test_admin_api.py -q
grep -r "smart_router\.BACKENDS\|smart_router\.VISION_BACKENDS" --include="*.py" . | wc -l  # 应为 0
```

**预期减少引用**: ~20 处

---

### Slice 2: 路由分类器迁移（5 处 analyze + 3 处 route）

**范围**: 迁移意图分析和路由入口

**影响文件**:
- `orchestrate.py`
- `routes/chat_handler_dispatch.py`
- `routes/chat_support.py`
- 测试文件 3 个

**执行步骤**:
1. `import router_classifier` 和 `import routing_engine`
2. 替换：`smart_router.analyze` → `router_classifier.analyze`
3. 替换：`smart_router.route` → `routing_engine.route`
4. 运行路由测试：`pytest tests/test_routing*.py tests/test_chat*.py -q`
5. Git commit

**验证命令**:
```bash
python -m pytest tests/test_routing_engine.py tests/test_router_classifier.py -q
grep -r "smart_router\.analyze\|smart_router\.route" --include="*.py" . | wc -l  # 应为 0
```

**预期减少引用**: ~8 处

---

### Slice 3: 意图检测迁移（3 处 image + 1 处 thinking）

**范围**: 迁移图片和思维链意图检测

**影响文件**:
- `routes/chat_handler_dispatch.py`
- `routes/chat_stream.py`
- `routes/chat_support.py`

**执行步骤**:
1. `import router_image` 和 `import router_intent`
2. 替换：`smart_router.detect_image_intent` → `router_image.detect_image_intent`
3. 替换：`smart_router.detect_thinking_intent` → `router_intent.detect_thinking_intent`
4. 替换：`smart_router.get_thinking_backend` → `router_intent.get_thinking_backend`
5. 运行聚焦测试：`pytest tests/test_router_image.py tests/test_router_intent.py -q`
6. Git commit

**验证命令**:
```bash
python -m pytest tests/test_router_image.py tests/test_chat_handler_dispatch.py -q
grep -r "smart_router\.detect_.*_intent" --include="*.py" . | wc -l  # 应为 0
```

**预期减少引用**: ~4 处

---

### Slice 4: HTTP 调用和熔断器迁移（4 处 call_api + 3 处 cb_*）

**范围**: 迁移 HTTP 调用和熔断器

**影响文件**:
- `orchestrate.py`
- `routes/chat_support.py`
- `routes/system_endpoints.py`
- `routes/admin_api.py`
- `tests/test_vision_routing.py`

**执行步骤**:
1. `import http_caller` 和 `import router_circuit_breaker`
2. 替换：`smart_router.call_api` → `http_caller.call_api`（**检查参数兼容性**）
3. 替换：`smart_router.cb_status` → `router_circuit_breaker.cb_status`
4. 替换：`smart_router.cb_allow` → `router_circuit_breaker.cb_allow`
5. 运行 HTTP 测试：`pytest tests/test_http_caller.py tests/test_circuit_breaker.py -q`
6. Git commit

**⚠️ 注意**:
- `call_api` 参数顺序可能不同，需要逐个检查
- 熔断器接口可能有状态依赖

**验证命令**:
```bash
python -m pytest tests/test_http_caller.py tests/test_routing_executor.py -q
grep -r "smart_router\.call_api\|smart_router\.cb_" --include="*.py" . | wc -l  # 应为 0
```

**预期减少引用**: ~7 处

---

### Slice 5: 清理遗留引用和删除 smart_router.py

**范围**: 处理边缘引用、删除文件

**影响文件**:
- `server.py` (warmup_router_model)
- `auto_retrain.py` (本地模型相关)
- `routes/chat_post_closeout.py` (_log_to_distill_queue)
- `vision_handler.py`、`distill_scheduler.py` 等注释引用

**执行步骤**:
1. 删除 `server.py` 中的 `warmup_router_model()` 调用（已弃用）
2. 修复 `auto_retrain.py` 本地模型引用（或标记为已弃用）
3. 迁移 `_log_to_distill_queue` 到 `distill_scheduler`
4. 清理所有注释中的 `smart_router` 引用
5. **删除 `smart_router.py` 文件**
6. 运行全量测试：`pytest -q --ignore=tests/test_token_health.py`
7. Git commit

**验证命令**:
```bash
python -m pytest -q --ignore=tests/test_token_health.py --basetemp=.pytest_temp
grep -r "smart_router" --include="*.py" . --exclude-dir=venv | grep -v "^[^:]*:#" | wc -l  # 应为 0
ls smart_router.py  # 应报错 "No such file"
```

**预期减少引用**: 剩余所有引用

---

## 五、风险评估与缓解

### 5.1 高风险点

| 风险 | 影响范围 | 缓解措施 |
|------|---------|----------|
| **call_api 参数不兼容** | HTTP 调用失败 | Slice 4 前仔细比对参数签名 |
| **循环导入** | 模块加载失败 | 按依赖顺序迁移，避免交叉引用 |
| **测试覆盖不足** | 隐藏的 bug | 每个 Slice 运行相关测试 + 全量测试 |
| **生产路由失败** | 用户请求失败 | 本地全量验证后再部署 VPS |

### 5.2 回滚策略

每个 Slice 独立提交，出现问题可以：
1. **单独回滚**：`git revert <commit-hash>`
2. **快速修复**：在当前 Slice 基础上修复
3. **暂停后续**：停止未执行的 Slice

---

## 六、验证清单

### 6.1 每个 Slice 验证

- [ ] 编译检查：`python -m py_compile <modified_files>`
- [ ] 聚焦测试：运行相关模块的测试
- [ ] Ruff 检查：`python scripts/run_ruff_check.py`
- [ ] Git diff 检查：`git diff --check`
- [ ] 依赖残留检查：`grep -r "smart_router\.XXX"`

### 6.2 最终验证（Slice 5）

- [ ] 全量测试：`pytest -q --basetemp=.pytest_temp`
- [ ] 测试通过：≥ 2000 passed
- [ ] 无 smart_router 引用：`grep -r "smart_router" --include="*.py" . | grep -v "#"`
- [ ] 文件已删除：`ls smart_router.py` 报错
- [ ] VPS 本地验证：部署前在 VPS 本地运行测试
- [ ] 公网烟雾测试：`/health`、`/v1/chat/completions` HTTP 200

---

## 七、执行时间估算

| Slice | 预计时间 | 累计时间 |
|-------|---------|----------|
| Slice 1: BACKENDS 迁移 | 1-2 小时 | 1-2h |
| Slice 2: 路由分类器迁移 | 1 小时 | 2-3h |
| Slice 3: 意图检测迁移 | 1 小时 | 3-4h |
| Slice 4: HTTP/熔断器迁移 | 2-3 小时 | 5-7h |
| Slice 5: 清理和删除 | 1-2 小时 | 6-9h |
| **总计** | **6-9 小时** | - |

**分摊到天数**: 2-3 天（每天 3-4 小时）

---

## 八、成功标准

### 8.1 功能标准

- ✅ 所有 smart_router 引用已迁移
- ✅ smart_router.py 文件已删除
- ✅ 全量测试通过（≥2000 passed）
- ✅ VPS 部署成功，公网烟雾测试通过

### 8.2 质量标准

- ✅ 代码减少 ~241 行
- ✅ 模块职责更清晰
- ✅ 导入路径统一（直接从底层模块导入）
- ✅ 无性能退化（路由延迟 <10ms 增加）

### 8.3 文档标准

- ✅ 更新 CLAUDE.md 移除 smart_router 说明
- ✅ 更新 STATUS.md 记录迁移完成
- ✅ 创建迁移完成报告

---

## 九、下一步行动

### 立即开始（Slice 1）

```bash
# 1. 创建工作分支（可选）
git checkout -b feat/smart-router-migration

# 2. 执行 Slice 1: BACKENDS 迁移
grep -r "smart_router.BACKENDS" --include="*.py" . --exclude-dir=venv

# 3. 批量替换（手动确认每个文件）
# ...

# 4. 测试验证
python -m pytest tests/test_backend_registry.py tests/test_admin_api.py -q

# 5. 提交
git add <modified_files>
git commit -m "refactor: Slice 1 - migrate smart_router.BACKENDS to backends.BACKENDS"
```

---

**准备好开始 Slice 1 了吗？**
